package controller

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"reflect"
	"sort"
	"strings"
	"time"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/okf"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// AgentBundleReconciler turns a signed OKF agent bundle (ADR-0564) into UnifAI objects. It never talks to
// UnifAI itself: it emits UnifaiLLM, UnifaiAgent, UnifaiCondition and UnifaiWorkflow resources owned by the
// bundle, and their own controllers push them. An unverified bundle emits nothing and leaves what a
// previously verified version emitted untouched.
type AgentBundleReconciler struct {
	client.Client
	Scheme *runtime.Scheme
	// Fetch pulls the bundle (okf.Fetch by default; replaced in tests).
	Fetch okf.Fetcher
}

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaiagentbundles,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaiagentbundles/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaiagentbundles/finalizers,verbs=update
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaillms;unifaiagents;unifaiconditions;unifaiworkflows;unifaiproviders,verbs=create;delete

// Zuno headers the emitted LLMs send to the model gateway (ADR-0563, ADR-0565).
const (
	headerAgent          = "X-Zuno-Agent"
	headerTask           = "X-Zuno-Task"
	headerClassification = "X-Zuno-Data-Classification"
	headerRunID          = "X-Zuno-Run-Id"
)

// Conditions of the ADR-0564 pipeline, in order.
const (
	ConditionVerified       = "Verified"
	ConditionValid          = "Valid"
	ConditionWithinCeilings = "WithinCeilings"
	ConditionEmitted        = "Emitted"

	entitlementGatewayOnly = "GatewayOnly"
	phaseReady             = "Ready"
)

func (r *AgentBundleReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	cr := &unifaiv1.UnifaiAgentBundle{}
	if err := r.Get(ctx, req.NamespacedName, cr); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	if !cr.DeletionTimestamp.IsZero() {
		return ctrl.Result{}, nil // children are garbage-collected through their owner references
	}
	orig := cr.DeepCopy()
	var requeue time.Duration
	err := r.reconcile(ctx, cr)
	st := &cr.Status
	now := metav1.Now()
	st.LastReconciled = &now
	var perm *PermanentError
	switch {
	case errors.As(err, &perm):
		st.Phase, st.Message = "Error", unifai.Truncate(perm.Error(), 500)
		st.ObservedGeneration = cr.Generation
		requeue = resync
	case err != nil:
		st.Phase, st.Message = "Pending", unifai.Truncate(err.Error(), 500)
		requeue = retry
	default:
		st.Phase, st.ObservedGeneration = phaseReady, cr.Generation
	}
	ready := metav1.ConditionFalse
	if st.Phase == phaseReady {
		ready = metav1.ConditionTrue
	}
	meta.SetStatusCondition(&st.Conditions, metav1.Condition{Type: phaseReady, Status: ready, Reason: st.Phase,
		Message: st.Message, ObservedGeneration: cr.Generation})
	if uerr := r.Status().Patch(ctx, cr, client.MergeFrom(orig)); uerr != nil {
		return ctrl.Result{}, uerr
	}
	return ctrl.Result{RequeueAfter: requeue}, nil
}

func (r *AgentBundleReconciler) reconcile(ctx context.Context, cr *unifaiv1.UnifaiAgentBundle) error {
	st := &cr.Status
	cond := func(typ string, ok bool, reason, msg string) {
		s := metav1.ConditionFalse
		if ok {
			s = metav1.ConditionTrue
		}
		meta.SetStatusCondition(&st.Conditions, metav1.Condition{Type: typ, Status: s, Reason: reason,
			Message: unifai.Truncate(msg, 500), ObservedGeneration: cr.Generation})
	}
	ref := cr.Spec.Source.OCI.Reference
	if _, _, err := okf.SplitDigestRef(ref); err != nil {
		return &PermanentError{Err: err}
	}
	pub, err := r.secretValue(ctx, cr.Namespace, cr.Spec.Verify.PublicKeyRef)
	if err != nil {
		return err
	}
	cred, err := r.pullCredential(ctx, cr)
	if err != nil {
		return err
	}
	fetch := r.Fetch
	if fetch == nil {
		fetch = okf.Fetch
	}

	// 1. Pull the manifest by digest.
	art, err := fetch(ctx, ref, cred)
	if err != nil {
		return fmt.Errorf("pull %s: %w", ref, err)
	}
	st.ResolvedDigest = art.ManifestDigest

	// 2. Verify before any byte of the bundle is parsed.
	digest, err := okf.Digest(art.Files)
	if err == nil {
		err = okf.VerifySignature(digest, art.Signature, []byte(pub))
	}
	st.BundleDigest = digest
	if err != nil {
		st.Verified = false
		cond(ConditionVerified, false, "SignatureInvalid", err.Error())
		return permanent("bundle not verified, nothing emitted: %v", err)
	}
	st.Verified = true
	cond(ConditionVerified, true, "SignatureValid", "bundle digest "+digest)

	// 3. Validate against the embedded OKF schemas, then the mapping's own preconditions.
	if err := okf.ValidateSchemas(art.Files); err != nil {
		cond(ConditionValid, false, "SchemaInvalid", err.Error())
		return permanent("%v", err)
	}
	b, err := okf.Parse(art.Files)
	if err != nil {
		cond(ConditionValid, false, "Invalid", err.Error())
		return permanent("invalid OKF bundle: %v", err)
	}
	st.OKFVersion = b.OKFVersion
	switch b.GraphShape {
	case okf.ShapeRetrieveReasonRespond:
	case "":
		cond(ConditionValid, false, "ShapeMissing", "zuno.graph_shape is not declared")
		return permanent("bundle %s declares no zuno.graph_shape: nothing emitted", b.Name)
	default:
		cond(ConditionValid, false, "ShapeNotImplemented", "no blueprint template for graph shape "+b.GraphShape)
		return permanent("graph shape %q has no blueprint template in this operator: nothing emitted", b.GraphShape)
	}
	if len(b.AccessGroups) > 0 && cr.Spec.Entitlement != entitlementGatewayOnly {
		msg := fmt.Sprintf("zuno.access.groups %v cannot be enforced by UnifAI visibility yet; set spec.entitlement: GatewayOnly to rely on the gateways", b.AccessGroups)
		cond(ConditionValid, false, "EntitlementUnsupported", msg)
		return permanent("%s", msg)
	}
	cond(ConditionValid, true, "Valid", fmt.Sprintf("OKF %s, %d tasks, shape %s", b.OKFVersion, len(b.Tasks), b.GraphShape))

	// 4. A bundle can narrow its ceilings, never widen them.
	if err := checkCeilings(cr, b); err != nil {
		cond(ConditionWithinCeilings, false, "Widening", err.Error())
		return permanent("bundle exceeds spec.ceilings, nothing emitted: %v", err)
	}
	cond(ConditionWithinCeilings, true, "WithinCeilings", "declared tools, knowledge and classification are within spec.ceilings")

	// 5. Emit the owned children.
	desired, tasks, err := renderBundle(cr, b)
	if err != nil {
		return err
	}
	for _, obj := range desired {
		if err := r.upsert(ctx, cr, obj); err != nil {
			cond(ConditionEmitted, false, "EmitFailed", err.Error())
			return err
		}
	}
	if err := r.prune(ctx, cr, desired); err != nil {
		return err
	}
	unmapped := b.Unmapped
	if len(b.AccessGroups) > 0 {
		unmapped = append([]string{fmt.Sprintf("zuno.access.groups %v: enforced by the gateways only (spec.entitlement GatewayOnly)", b.AccessGroups)}, unmapped...)
	}
	st.Agent, st.Tasks, st.Unmapped = b.Name, tasks, unmapped
	st.Children = childNames(desired)
	st.Message = fmt.Sprintf("%d tasks, %d objects emitted", len(tasks), len(desired))
	cond(ConditionEmitted, true, "Emitted", st.Message)
	return nil
}

// checkCeilings refuses any declared tool, knowledge domain or classification outside spec.ceilings.
func checkCeilings(cr *unifaiv1.UnifaiAgentBundle, b *okf.Bundle) error {
	var problems []string
	if extra := outside(b.DeclaredTools(), cr.Spec.Ceilings.ToolCapabilities); len(extra) > 0 {
		problems = append(problems, fmt.Sprintf("tools %v are not in toolCapabilities", extra))
	}
	if extra := outside(b.DeclaredKnowledge(), cr.Spec.Ceilings.KnowledgeDomains); len(extra) > 0 {
		problems = append(problems, fmt.Sprintf("knowledge %v is not in knowledgeDomains", extra))
	}
	floor, err := okf.ParseLevel(cr.Spec.Ceilings.MinClassification)
	if err != nil {
		problems = append(problems, "ceilings.minClassification: "+err.Error())
	} else if b.Classification < floor {
		problems = append(problems, fmt.Sprintf("classification %s is below minClassification %s", b.Classification, floor))
	}
	if len(problems) > 0 {
		return errors.New(strings.Join(problems, "; "))
	}
	return nil
}

func outside(values, allowed []string) []string {
	ok := map[string]bool{}
	for _, a := range allowed {
		ok[a] = true
	}
	var out []string
	for _, v := range values {
		if !ok[v] {
			out = append(out, v)
		}
	}
	return out
}

// renderBundle maps the bundle onto UnifAI objects: one condition, and per task an LLM carrying the Zuno
// headers, a custom agent and a linear workflow (question -> agent -> answer). The primary task's workflow
// takes the bundle's own name.
func renderBundle(cr *unifaiv1.UnifaiAgentBundle, b *okf.Bundle) ([]client.Object, []unifaiv1.BundleTaskStatus, error) {
	common := unifaiv1.CommonSpec{Owner: cr.Spec.Owner, TeamID: cr.Spec.TeamID}
	llmBase, err := rawMap(cr.Spec.LLM.Config)
	if err != nil {
		return nil, nil, err
	}
	agentBase, err := rawMap(cr.Spec.AgentConfig)
	if err != nil {
		return nil, nil, err
	}
	for task := range cr.Spec.ClassificationOverrides {
		if !hasTask(b, task) {
			return nil, nil, permanent("classificationOverrides names unknown task %q", task)
		}
	}
	llmType := cr.Spec.LLM.Type
	if llmType == "" {
		llmType = "openai_compatible"
	}
	cond := cr.Name + "-direct"
	objs := []client.Object{&unifaiv1.UnifaiCondition{ObjectMeta: childMeta(cr, cond), Spec: unifaiv1.UnifaiConditionSpec{
		CommonSpec: common, Type: "router_direct", ConfigSpec: unifaiv1.ConfigSpec{Config: rawJSON(map[string]any{})}}}}
	tasks := make([]unifaiv1.BundleTaskStatus, 0, len(b.Tasks))
	for _, t := range b.Tasks {
		level, err := okf.Effective(b.Classification, cr.Spec.ClassificationOverrides[t.Name])
		if err != nil {
			return nil, nil, permanent("task %s: %v", t.Name, err)
		}
		name := childName(cr.Name, t.Name)
		wfName := name
		if t.Name == b.PrimaryTask {
			wfName = cr.Name
		}

		llm := deepCopyMap(llmBase)
		headers := map[string]any{}
		if h, ok := llm["default_headers"].(map[string]any); ok {
			headers = h
		}
		headers[headerAgent] = b.Name
		headers[headerTask] = t.Name
		headers[headerClassification] = level.String()
		headers[headerRunID] = "{session_id}"
		llm["default_headers"] = headers
		objs = append(objs, &unifaiv1.UnifaiLLM{ObjectMeta: childMeta(cr, name), Spec: unifaiv1.UnifaiLLMSpec{
			CommonSpec: common, Type: llmType,
			ConfigSpec: unifaiv1.ConfigSpec{Config: rawJSON(llm), SecretRefs: cr.Spec.LLM.SecretRefs}}})

		agent := deepCopyMap(agentBase)
		agent["llm"] = "$ref:llm/" + name
		agent["system_message"] = b.SystemMessage(t)
		if _, ok := agent["strategy_type"]; !ok {
			agent["strategy_type"] = "react"
		}
		if len(t.AllowedTools) > 0 && (cr.Spec.MCP != nil || len(cr.Spec.Providers) > 0) {
			refs := []any{}
			if cr.Spec.MCP != nil {
				mcp, err := rawMap(cr.Spec.MCP.Config)
				if err != nil {
					return nil, nil, err
				}
				mcpHeaders := map[string]any{}
				if h, ok := mcp["additional_headers"].(map[string]any); ok {
					mcpHeaders = h
				}
				mcpHeaders[headerAgent] = b.Name
				mcpHeaders[headerTask] = t.Name
				mcpHeaders[headerClassification] = level.String()
				mcpHeaders[headerRunID] = "{session_id}"
				mcp["additional_headers"] = mcpHeaders
				objs = append(objs, &unifaiv1.UnifaiProvider{ObjectMeta: childMeta(cr, name), Spec: unifaiv1.UnifaiProviderSpec{
					CommonSpec: common, Type: "mcp_server",
					ConfigSpec: unifaiv1.ConfigSpec{Config: rawJSON(mcp), SecretRefs: cr.Spec.MCP.SecretRefs}}})
				refs = append(refs, "$ref:provider/"+name)
			}
			for _, p := range cr.Spec.Providers {
				refs = append(refs, "$ref:provider/"+p)
			}
			agent["providers"] = refs
		}
		if len(t.AllowedKnowledge) > 0 && cr.Spec.Retriever != "" {
			agent["retriever"] = "$ref:retriever/" + cr.Spec.Retriever
		}
		objs = append(objs, &unifaiv1.UnifaiAgent{ObjectMeta: childMeta(cr, name), Spec: unifaiv1.UnifaiAgentSpec{
			CommonSpec: common, Type: "custom_agent_node", ConfigSpec: unifaiv1.ConfigSpec{Config: rawJSON(agent)}}})

		title := t.Title
		if title == "" {
			title = t.Name
		}
		objs = append(objs, &unifaiv1.UnifaiWorkflow{ObjectMeta: childMeta(cr, wfName), Spec: unifaiv1.UnifaiWorkflowSpec{
			CommonSpec:  common,
			Description: fmt.Sprintf("%s - %s (OKF bundle %s, %s)", b.Title, title, b.Name, level),
			Blueprint:   *rawJSON(linearBlueprint(cond, name)),
		}})
		tasks = append(tasks, unifaiv1.BundleTaskStatus{Name: t.Name, Classification: level.String(), Workflow: wfName})
	}
	return objs, tasks, nil
}

func linearBlueprint(cond, agent string) map[string]any {
	return map[string]any{
		"conditions": []any{map[string]any{"rid": "$ref:condition/" + cond}},
		"nodes": []any{
			map[string]any{"name": "User Question Node", "rid": "user_question", "type": "user_question_node",
				"config": map[string]any{"retries": 1, "type": "user_question_node"}},
			map[string]any{"name": "Final Answer Node", "rid": "final_answer", "type": "final_answer_node",
				"config": map[string]any{"retries": 1, "type": "final_answer_node"}},
			map[string]any{"rid": "$ref:agent/" + agent},
		},
		"plan": []any{
			map[string]any{"uid": "ask", "node": "user_question", "branches": map[string]any{"agent": "agent"},
				"exit_condition": "$rid:condition/" + cond},
			map[string]any{"uid": "agent", "node": "$rid:agent/" + agent},
			map[string]any{"uid": "finish", "node": "final_answer", "after": "agent"},
		},
	}
}

func hasTask(b *okf.Bundle, name string) bool {
	for _, t := range b.Tasks {
		if t.Name == name {
			return true
		}
	}
	return false
}

// childName is <bundle>-<task>, lowercased with anything outside [a-z0-9-] replaced by '-'.
func childName(bundle, task string) string {
	n := strings.ToLower(bundle + "-" + task)
	return strings.Map(func(c rune) rune {
		if (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' {
			return c
		}
		return '-'
	}, n)
}

func childMeta(cr *unifaiv1.UnifaiAgentBundle, name string) metav1.ObjectMeta {
	return metav1.ObjectMeta{Name: name, Namespace: cr.Namespace, Labels: map[string]string{unifaiv1.AgentBundleLabel: cr.Name}}
}

func childNames(objs []client.Object) []string {
	out := make([]string, 0, len(objs))
	for _, o := range objs {
		out = append(out, bundleChildKind(o)+"/"+o.GetName())
	}
	sort.Strings(out)
	return out
}

func bundleChildKind(o client.Object) string {
	return reflect.TypeOf(o).Elem().Name()
}

func rawJSON(v any) *runtime.RawExtension {
	b, _ := json.Marshal(v)
	return &runtime.RawExtension{Raw: b}
}

func deepCopyMap(m map[string]any) map[string]any {
	b, _ := json.Marshal(m)
	out := map[string]any{}
	_ = json.Unmarshal(b, &out)
	return out
}

// specOf returns the spec of an emitted kind.
func specOf(o client.Object) any {
	switch v := o.(type) {
	case *unifaiv1.UnifaiLLM:
		return &v.Spec
	case *unifaiv1.UnifaiAgent:
		return &v.Spec
	case *unifaiv1.UnifaiCondition:
		return &v.Spec
	case *unifaiv1.UnifaiWorkflow:
		return &v.Spec
	case *unifaiv1.UnifaiProvider:
		return &v.Spec
	}
	return nil
}

// upsert creates the child or updates its spec and labels; a same-named object it does not own is refused.
func (r *AgentBundleReconciler) upsert(ctx context.Context, cr *unifaiv1.UnifaiAgentBundle, desired client.Object) error {
	existing := desired.DeepCopyObject().(client.Object)
	err := r.Get(ctx, client.ObjectKeyFromObject(desired), existing)
	if apierrors.IsNotFound(err) {
		if err := controllerutil.SetControllerReference(cr, desired, r.Scheme); err != nil {
			return err
		}
		return r.Create(ctx, desired)
	}
	if err != nil {
		return err
	}
	if !metav1.IsControlledBy(existing, cr) {
		return permanent("%s %s already exists and is not owned by this bundle", bundleChildKind(desired), desired.GetName())
	}
	want, _ := json.Marshal(specOf(desired))
	have, _ := json.Marshal(specOf(existing))
	if string(want) == string(have) && reflect.DeepEqual(existing.GetLabels(), desired.GetLabels()) {
		return nil
	}
	if err := json.Unmarshal(want, specOf(existing)); err != nil {
		return err
	}
	existing.SetLabels(desired.GetLabels())
	return r.Update(ctx, existing)
}

// prune deletes the children this bundle owns that the current bundle no longer emits (e.g. a removed task).
func (r *AgentBundleReconciler) prune(ctx context.Context, cr *unifaiv1.UnifaiAgentBundle, desired []client.Object) error {
	keep := map[string]bool{}
	for _, o := range childNames(desired) {
		keep[o] = true
	}
	sel := client.MatchingLabels{unifaiv1.AgentBundleLabel: cr.Name}
	lists := []client.ObjectList{&unifaiv1.UnifaiLLMList{}, &unifaiv1.UnifaiAgentList{}, &unifaiv1.UnifaiConditionList{}, &unifaiv1.UnifaiWorkflowList{}, &unifaiv1.UnifaiProviderList{}}
	for _, l := range lists {
		if err := r.List(ctx, l, client.InNamespace(cr.Namespace), sel); err != nil {
			return err
		}
		items, err := meta.ExtractList(l)
		if err != nil {
			return err
		}
		for _, it := range items {
			o := it.(client.Object)
			if keep[bundleChildKind(o)+"/"+o.GetName()] || !metav1.IsControlledBy(o, cr) {
				continue
			}
			log.FromContext(ctx).Info("pruning object no longer in the bundle", "kind", bundleChildKind(o), "name", o.GetName())
			if err := r.Delete(ctx, o); client.IgnoreNotFound(err) != nil {
				return err
			}
		}
	}
	return nil
}

func (r *AgentBundleReconciler) secretValue(ctx context.Context, ns string, sel unifaiv1.SecretKeySelector) (string, error) {
	var s corev1.Secret
	if err := r.Get(ctx, types.NamespacedName{Namespace: ns, Name: sel.Name}, &s); err != nil {
		return "", fmt.Errorf("secret %s: %w", sel.Name, err)
	}
	v, ok := s.Data[sel.Key]
	if !ok {
		return "", fmt.Errorf("secret %s has no key %s", sel.Name, sel.Key)
	}
	return string(v), nil
}

// pullCredential reads the registry's entry of a dockerconfigjson pull secret.
func (r *AgentBundleReconciler) pullCredential(ctx context.Context, cr *unifaiv1.UnifaiAgentBundle) (*okf.Credential, error) {
	if cr.Spec.Source.OCI.PullSecretRef == nil || cr.Spec.Source.OCI.PullSecretRef.Name == "" {
		return nil, nil
	}
	name := cr.Spec.Source.OCI.PullSecretRef.Name
	raw, err := r.secretValue(ctx, cr.Namespace, unifaiv1.SecretKeySelector{Name: name, Key: corev1.DockerConfigJsonKey})
	if err != nil {
		return nil, err
	}
	var cfg struct {
		Auths map[string]struct {
			Auth     string `json:"auth"`
			Username string `json:"username"`
			Password string `json:"password"`
		} `json:"auths"`
	}
	if err := json.Unmarshal([]byte(raw), &cfg); err != nil {
		return nil, permanent("pull secret %s: %v", name, err)
	}
	registry := strings.SplitN(cr.Spec.Source.OCI.Reference, "/", 2)[0]
	a, ok := cfg.Auths[registry]
	if !ok {
		return nil, permanent("pull secret %s has no entry for %s", name, registry)
	}
	if a.Username == "" && a.Auth != "" {
		dec, err := base64.StdEncoding.DecodeString(a.Auth)
		if err != nil {
			return nil, permanent("pull secret %s: %v", name, err)
		}
		u, p, _ := strings.Cut(string(dec), ":")
		a.Username, a.Password = u, p
	}
	return &okf.Credential{Username: a.Username, Password: a.Password}, nil
}

// SetupWithManager registers the controller; changes to emitted objects re-trigger the bundle.
func (r *AgentBundleReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiAgentBundle{}).
		Owns(&unifaiv1.UnifaiLLM{}).Owns(&unifaiv1.UnifaiAgent{}).
		Owns(&unifaiv1.UnifaiCondition{}).Owns(&unifaiv1.UnifaiWorkflow{}).Owns(&unifaiv1.UnifaiProvider{}).
		Named("unifaiagentbundle").Complete(r)
}
