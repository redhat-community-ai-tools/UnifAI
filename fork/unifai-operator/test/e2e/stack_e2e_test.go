//go:build e2e

// Package e2e tests the UnifAI operator installed on the current cluster (kubeconfig context): it deploys an
// UnifaiStack in a throwaway namespace, checks its invariants and a chat through the whole chain, then deletes it.
//
//	make test-e2e                      # E2E_KEEP=1 keeps the namespace, see the E2E_* variables below
package e2e

import (
	"context"
	"crypto/tls"
	"net/http"
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"strings"
	"testing"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/util/intstr"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

var (
	ctx = context.Background()
	c   client.Client
	ns  string
)

func raw(v any) *runtime.RawExtension {
	b, _ := json.Marshal(v)
	return &runtime.RawExtension{Raw: b}
}

// eventually polls cond until it returns true or the timeout expires; the last message is reported on failure.
func eventually(t *testing.T, what string, timeout time.Duration, cond func() (bool, string)) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	last := ""
	for time.Now().Before(deadline) {
		ok, msg := cond()
		if ok {
			return
		}
		if msg != last {
			t.Logf("%s: %s", what, msg)
			last = msg
		}
		time.Sleep(10 * time.Second)
	}
	t.Fatalf("%s: timed out after %s (%s)", what, timeout, last)
}

func TestMain(m *testing.M) {
	scheme := runtime.NewScheme()
	_ = clientgoscheme.AddToScheme(scheme)
	_ = unifaiv1.AddToScheme(scheme)
	cfg, err := ctrl.GetConfig()
	if err != nil {
		fmt.Println("no kubeconfig:", err)
		os.Exit(1)
	}
	if c, err = client.New(cfg, client.Options{Scheme: scheme}); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	ns = env("E2E_NAMESPACE", fmt.Sprintf("unifai-e2e-%05d", rand.Intn(100000)))
	code := m.Run()
	if os.Getenv("E2E_KEEP") == "" {
		if err := deleteNamespace(ns); err != nil {
			fmt.Println(err)
			code = 1
		}
	} else {
		fmt.Println("E2E_KEEP set: namespace", ns, "kept")
	}
	os.Exit(code)
}

func TestUnifaiStack(t *testing.T) {
	timeout, _ := time.ParseDuration(env("E2E_TIMEOUT", "30m"))

	// The operator must run (installed by OLM or `make deploy`).
	var deps appsv1.DeploymentList
	opts := []client.ListOption{client.MatchingLabels{"control-plane": "controller-manager", "app.kubernetes.io/name": "unifai-operator"}}
	if n := os.Getenv("E2E_OPERATOR_NAMESPACE"); n != "" {
		opts = append(opts, client.InNamespace(n))
	}
	if err := c.List(ctx, &deps, opts...); err != nil || len(deps.Items) == 0 {
		t.Fatalf("no unifai-operator deployment found (err=%v)", err)
	}
	t.Logf("operator: %s/%s image %s", deps.Items[0].Namespace, deps.Items[0].Name, deps.Items[0].Spec.Template.Spec.Containers[0].Image)

	if err := c.Create(ctx, &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: ns}}); err != nil {
		t.Fatal(err)
	}
	t.Logf("namespace %s", ns)
	must(t, c.Create(ctx, &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "e2e-oidc", Namespace: ns},
		StringData: map[string]string{"client-secret": "not-used-by-the-e2e"}}))

	spec := stackSpec(unifaiv1.IdentitySpec{External: &unifaiv1.ExternalOIDCSpec{
		URL: env("E2E_OIDC_URL", "https://keycloak.example.invalid"), Realm: "unifai", ClientID: "unifai",
		ClientSecret: unifaiv1.SecretKeySelector{Name: "e2e-oidc", Key: "client-secret"}}})

	t.Run("a second stack in the namespace is refused", func(t *testing.T) {
		second := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: "second", Namespace: ns}, Spec: spec}
		label(second, instance)
		err := c.Create(ctx, second)
		if !apierrors.IsInvalid(err) {
			t.Fatalf("expected Invalid, got %v", err)
		}
	})

	st := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: unifaiv1.StackName, Namespace: ns}, Spec: spec}
	create(t, st)
	eventually(t, "stack Ready", timeout, func() (bool, string) {
		if err := c.Get(ctx, client.ObjectKeyFromObject(st), st); err != nil {
			return false, err.Error()
		}
		return meta.IsStatusConditionTrue(st.Status.Conditions, "Ready"), st.Status.Phase + ": " + st.Status.Message
	})
	// The suite must exercise the release candidate, not whatever image the instance happens to run.
	if want := os.Getenv("E2E_CANDIDATE_VERSION"); want != "" && st.Status.OperatorVersion != want {
		t.Fatalf("stack reconciled by operator %q, want the candidate %q", st.Status.OperatorVersion, want)
	}

	t.Run("stack invariants", func(t *testing.T) {
		for _, comp := range st.Status.Components {
			if !comp.Ready {
				t.Errorf("component %s not ready: %s", comp.Name, comp.Message)
			}
		}
		if !strings.HasPrefix(st.Status.Endpoints.UI, "https://unifai-ui-"+ns+".") {
			t.Errorf("unexpected UI endpoint %q", st.Status.Endpoints.UI)
		}
		routes := &unstructured.UnstructuredList{}
		routes.SetAPIVersion("route.openshift.io/v1")
		routes.SetKind("RouteList")
		if err := c.List(ctx, routes, client.InNamespace(ns)); err == nil {
			var names []string
			for _, r := range routes.Items {
				names = append(names, r.GetName())
			}
			if len(names) != 2 {
				t.Errorf("expected only the ui and identity routes, got %v", names)
			}
		}
		np := &networkingv1.NetworkPolicy{}
		if err := c.Get(ctx, client.ObjectKey{Namespace: ns, Name: "unifai-stack"}, np); err != nil {
			t.Errorf("NetworkPolicy: %v", err)
		}
		gen := &corev1.Secret{}
		if err := c.Get(ctx, client.ObjectKey{Namespace: ns, Name: "unifai-generated"}, gen); err != nil || len(gen.Data["CREDENTIAL_ENCRYPTION_KEY"]) != 44 {
			t.Errorf("generated secret: err=%v key length=%d", err, len(gen.Data["CREDENTIAL_ENCRYPTION_KEY"]))
		}
		var deps appsv1.DeploymentList
		must(t, c.List(ctx, &deps, client.InNamespace(ns)))
		for _, d := range deps.Items {
			if d.Spec.Replicas == nil || *d.Spec.Replicas != 1 {
				t.Errorf("deployment %s: replicas %v in dev profile", d.Name, d.Spec.Replicas)
			}
			for _, v := range d.Spec.Template.Spec.Volumes {
				if v.PersistentVolumeClaim == nil {
					continue
				}
				pvc := &corev1.PersistentVolumeClaim{}
				if c.Get(ctx, client.ObjectKey{Namespace: ns, Name: v.PersistentVolumeClaim.ClaimName}, pvc) == nil &&
					len(pvc.Spec.AccessModes) == 1 && pvc.Spec.AccessModes[0] == corev1.ReadWriteOnce && d.Spec.Strategy.Type != appsv1.RecreateDeploymentStrategyType {
					t.Errorf("deployment %s mounts RWO %s but uses %s", d.Name, pvc.Name, d.Spec.Strategy.Type)
				}
			}
		}
	})

	t.Run("the internal auth header is not honoured from outside", func(t *testing.T) {
		hc := &http.Client{Timeout: 30 * time.Second, Transport: &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}} //nolint:gosec
		url := st.Status.Endpoints.UI + "/api2/resources/resources.list?category=llms"
		eventually(t, "UI route answers", 3*time.Minute, func() (bool, string) {
			resp, err := hc.Get(st.Status.Endpoints.UI + "/")
			if err != nil {
				return false, err.Error()
			}
			_ = resp.Body.Close()
			return resp.StatusCode == http.StatusOK, resp.Status
		})
		for _, name := range []string{"X-Authenticated-User", "x-authenticated-user"} {
			req, _ := http.NewRequest(http.MethodGet, url, nil)
			req.Header.Set(name, "admin")
			resp, err := hc.Do(req)
			if err != nil {
				t.Fatal(err)
			}
			_ = resp.Body.Close()
			if resp.StatusCode != http.StatusUnauthorized {
				t.Errorf("%s through the UI route: got %s, want 401", name, resp.Status)
			}
		}
	})

	t.Run("the internal auth header needs the shared secret inside the cluster", func(t *testing.T) {
		if os.Getenv("E2E_INTERNAL_AUTH") == "0" {
			t.Skip("E2E_INTERNAL_AUTH=0: images without the internal authentication")
		}
		checkInternalAuth(t, ns)
	})

	t.Run("objects and a chat through the whole chain", func(t *testing.T) {
		deployMockLLM(t, ns)
		llm := &unifaiv1.UnifaiLLM{ObjectMeta: metav1.ObjectMeta{Name: "e2e-llm", Namespace: ns}, Spec: unifaiv1.UnifaiLLMSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "e2e-llm"}, Type: "openai_compatible",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"model_name": "mock-model", "base_url": "http://e2e-llm:8000/v1", "api_key": "EMPTY"})}}}
		cond := &unifaiv1.UnifaiCondition{ObjectMeta: metav1.ObjectMeta{Name: "e2e-direct", Namespace: ns}, Spec: unifaiv1.UnifaiConditionSpec{Type: "router_direct"}}
		agent := &unifaiv1.UnifaiAgent{ObjectMeta: metav1.ObjectMeta{Name: "e2e-agent", Namespace: ns}, Spec: unifaiv1.UnifaiAgentSpec{
			Type: "custom_agent_node", ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"llm": "$ref:llm/e2e-llm", "hitl_mode": "skip"})}}}
		wf := &unifaiv1.UnifaiWorkflow{ObjectMeta: metav1.ObjectMeta{Name: "e2e-wf", Namespace: ns}, Spec: unifaiv1.UnifaiWorkflowSpec{
			Blueprint: *raw(map[string]any{
				"nodes": []any{
					map[string]any{"rid": "user_question", "name": "User Question Node", "type": "user_question_node", "config": map[string]any{"type": "user_question_node"}},
					map[string]any{"rid": "final_answer", "name": "Final Answer Node", "type": "final_answer_node", "config": map[string]any{"type": "final_answer_node"}},
					map[string]any{"rid": "$ref:agent/e2e-agent"}},
				"conditions": []any{map[string]any{"rid": "$ref:condition/e2e-direct"}},
				"plan": []any{
					map[string]any{"uid": "ask", "node": "user_question", "exit_condition": "$rid:condition/e2e-direct", "branches": map[string]any{"agent": "agent"}},
					map[string]any{"uid": "agent", "node": "$rid:agent/e2e-agent"},
					map[string]any{"uid": "finish", "node": "final_answer", "after": "agent"}},
			})}}
		chat := &unifaiv1.UnifaiChat{ObjectMeta: metav1.ObjectMeta{Name: "e2e-chat", Namespace: ns}, Spec: unifaiv1.UnifaiChatSpec{Workflow: "e2e-wf", Prompt: "ping"}}
		for _, o := range []client.Object{llm, cond, agent, wf} {
			create(t, o)
		}
		for _, o := range []unifaiv1.Object{llm, cond, agent, wf} {
			waitPhase(t, o, "Ready", 5*time.Minute)
		}
		create(t, chat)
		waitPhase(t, chat, "Completed", 5*time.Minute)
		if !strings.Contains(chat.Status.Result, "pong") {
			t.Errorf("unexpected chat result %s", chat.Status.Result)
		}
	})

	t.Run("schedule, template and RAG pipeline on the real services", func(t *testing.T) {
		sch := &unifaiv1.UnifaiSchedule{ObjectMeta: metav1.ObjectMeta{Name: "e2e-every", Namespace: ns}, Spec: unifaiv1.UnifaiScheduleSpec{
			Workflow: "e2e-wf", Inputs: map[string]string{"user_prompt": "ping"}, Schedule: unifaiv1.ScheduleDefinition{Interval: "PT12H"}}}
		tpl := &unifaiv1.UnifaiTemplate{ObjectMeta: metav1.ObjectMeta{Name: "e2e-template", Namespace: ns}, Spec: unifaiv1.UnifaiTemplateSpec{
			Draft: *raw(map[string]any{
				"name": "E2E Template", "description": "e2e",
				"llms": []any{map[string]any{"rid": "llm_rid", "name": "mock", "type": "openai_compatible",
					"config": map[string]any{"type": "openai_compatible", "model_name": "mock-model", "base_url": "http://e2e-llm:8000/v1", "api_key": "PLACEHOLDER_API_KEY"}}},
				"nodes": []any{
					map[string]any{"rid": "user_question", "name": "User Question Node", "type": "user_question_node", "config": map[string]any{"type": "user_question_node"}},
					map[string]any{"rid": "final_answer", "name": "Final Answer Node", "type": "final_answer_node", "config": map[string]any{"type": "final_answer_node"}},
					map[string]any{"rid": "agent_rid", "name": "Assistant", "type": "custom_agent_node",
						"config": map[string]any{"type": "custom_agent_node", "llm": "llm_rid", "hitl_mode": "skip"}}},
				"plan": []any{
					map[string]any{"uid": "ask", "node": "user_question"},
					map[string]any{"uid": "answer", "node": "agent_rid", "after": "ask"},
					map[string]any{"uid": "finish", "node": "final_answer", "after": "answer"}},
			}),
			Placeholders: raw(map[string]any{"categories": []any{map[string]any{"category": "llms", "resources": []any{
				map[string]any{"rid": "llm_rid", "placeholders": []any{map[string]any{"field_path": "api_key", "required": true, "label": "API key"}}}}}}}),
			Metadata: raw(map[string]any{"author": "e2e", "version": "1.0.0", "is_public": false, "category": "Chat"}),
		}}
		for _, o := range []client.Object{sch, tpl} {
			create(t, o)
		}
		waitPhase(t, sch, "Ready", 5*time.Minute)
		if sch.Status.ScheduleID == "" {
			t.Errorf("schedule Ready without an id")
		}
		waitPhase(t, tpl, "Ready", 5*time.Minute)

		must(t, c.Get(ctx, client.ObjectKeyFromObject(sch), sch))
		sch.Spec.Suspend = true
		must(t, c.Update(ctx, sch))
		waitPhase(t, sch, "Suspended", 5*time.Minute)

		if os.Getenv("E2E_FULL") == "" {
			t.Log("RAG pipeline skipped: docling and the embedding service are only deployed with E2E_FULL=1")
			return
		}
		rag := &unifaiv1.UnifaiRAGPipeline{ObjectMeta: metav1.ObjectMeta{Name: "e2e-docs", Namespace: ns}, Spec: unifaiv1.UnifaiRAGPipelineSpec{
			Documents: []unifaiv1.RAGDocument{{Name: "e2e-notes.md", Tags: []string{"e2e"},
				Source: unifaiv1.DocumentSource{Inline: "# E2E\nThe UnifAI operator ingests this document through docling and TEI."}}}}}
		create(t, rag)
		waitPhase(t, rag, "Ready", 15*time.Minute)
	})

	t.Run("no Helm release is re-applied without a change", func(t *testing.T) {
		before := releaseVersions(t, ns)
		must(t, c.Get(ctx, client.ObjectKeyFromObject(st), st))
		if st.Annotations == nil {
			st.Annotations = map[string]string{}
		}
		st.Annotations["e2e/touch"] = time.Now().Format(time.RFC3339) // triggers a reconcile, no spec change
		must(t, c.Update(ctx, st))
		time.Sleep(60 * time.Second)
		after := releaseVersions(t, ns)
		for name, v := range after {
			if before[name] != v {
				t.Errorf("release %s went from revision %d to %d", name, before[name], v)
			}
		}
	})

	t.Run("deletion with deletionPolicy Delete removes everything", func(t *testing.T) {
		must(t, c.Get(ctx, client.ObjectKeyFromObject(st), st))
		must(t, c.Delete(ctx, st))
		eventually(t, "stack deleted", 15*time.Minute, func() (bool, string) {
			err := c.Get(ctx, client.ObjectKeyFromObject(st), st)
			return apierrors.IsNotFound(err), fmt.Sprintf("phase %s %s", st.Status.Phase, st.Status.Message)
		})
		if v := releaseVersions(t, ns); len(v) > 0 {
			t.Errorf("Helm releases left: %v", v)
		}
		var pvcs corev1.PersistentVolumeClaimList
		must(t, c.List(ctx, &pvcs, client.InNamespace(ns)))
		for _, p := range pvcs.Items {
			if p.DeletionTimestamp == nil {
				t.Errorf("PVC %s left", p.Name)
			}
		}
		if err := c.Get(ctx, client.ObjectKey{Namespace: ns, Name: "unifai-generated"}, &corev1.Secret{}); !apierrors.IsNotFound(err) {
			t.Errorf("unifai-generated left (err=%v)", err)
		}
	})
}

// instance is the operator instance under test (E2E_OPERATOR_INSTANCE, "" = the OLM one).
var instance = os.Getenv("E2E_OPERATOR_INSTANCE")

// create creates obj, labelled for the operator instance under test when it is an UnifAI resource.
func create(t *testing.T, obj client.Object) {
	t.Helper()
	label(obj, instance)
	must(t, c.Create(ctx, obj))
}

// label assigns an UnifAI resource to an operator instance ("" = default).
func label(obj client.Object, inst string) {
	if _, ok := obj.(unifaiv1.Object); !ok {
		if _, ok := obj.(*unifaiv1.UnifaiStack); !ok {
			return
		}
	}
	l := obj.GetLabels()
	if l == nil {
		l = map[string]string{}
	}
	if inst == "" {
		delete(l, "unifai.startx.fr/operator-instance")
	} else {
		l["unifai.startx.fr/operator-instance"] = inst
	}
	obj.SetLabels(l)
}

// stackSpec is the spec of the stacks under test (dev profile, Delete policy, light RAG unless E2E_FULL).
func stackSpec(identity unifaiv1.IdentitySpec) unifaiv1.UnifaiStackSpec {
	spec := unifaiv1.UnifaiStackSpec{
		Profile:        "dev",
		Identity:       identity,
		Storage:        unifaiv1.StorageSpec{ClassName: os.Getenv("E2E_STORAGE_CLASS"), SharedClassName: os.Getenv("E2E_SHARED_STORAGE_CLASS")},
		DeletionPolicy: "Delete",
		Version:        os.Getenv("E2E_VERSION"), // UnifAI images tag ("" = the operator's default)
	}
	if sel := os.Getenv("E2E_NODE_SELECTOR"); sel != "" {
		k, v, _ := strings.Cut(sel, "=")
		spec.NodeSelector = map[string]string{k: v}
	}
	if os.Getenv("E2E_FULL") == "" { // light run: no docling/TEI images (several GB)
		spec.RAG.Docling = unifaiv1.DoclingSpec{Mode: "remote", URL: "http://docling.invalid:5001"}
		spec.RAG.Embedding = unifaiv1.EmbeddingSpec{Mode: "remote", URL: "http://embedding.invalid:8080"}
	}
	return spec
}

// deleteNamespace deletes a test namespace and waits until it is gone: its UnifAI objects carry finalizers only
// the operator instance under test can release, so the instance must not be removed before (make release runs
// canary-delete right after the e2e).
func deleteNamespace(name string) error {
	err := c.Delete(ctx, &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: name}})
	if apierrors.IsNotFound(err) {
		return nil
	}
	if err != nil {
		return err
	}
	deadline := time.Now().Add(15 * time.Minute)
	for time.Now().Before(deadline) {
		if apierrors.IsNotFound(c.Get(ctx, client.ObjectKey{Name: name}, &corev1.Namespace{})) {
			return nil
		}
		time.Sleep(5 * time.Second)
	}
	return fmt.Errorf("namespace %s still terminating after 15 min", name)
}

func must(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatal(err)
	}
}

func waitPhase(t *testing.T, o unifaiv1.Object, phase string, timeout time.Duration) {
	t.Helper()
	eventually(t, fmt.Sprintf("%T %s %s", o, o.GetName(), phase), timeout, func() (bool, string) {
		if err := c.Get(ctx, client.ObjectKeyFromObject(o), o); err != nil {
			return false, err.Error()
		}
		st := o.GetObjectStatus()
		if st.Phase == "Error" || st.Phase == "Failed" {
			t.Fatalf("%s: %s %s", o.GetName(), st.Phase, st.Message)
		}
		return st.Phase == phase, st.Phase + " " + st.Message
	})
}

// releaseVersions returns the latest revision of each Helm release of the namespace.
func releaseVersions(t *testing.T, ns string) map[string]int {
	t.Helper()
	var secrets corev1.SecretList
	must(t, c.List(ctx, &secrets, client.InNamespace(ns), client.MatchingLabels{"owner": "helm"}))
	out := map[string]int{}
	for _, s := range secrets.Items {
		var v int
		_, _ = fmt.Sscan(s.Labels["version"], &v)
		if v > out[s.Labels["name"]] {
			out[s.Labels["name"]] = v
		}
	}
	return out
}

// deployMockLLM runs the OpenAI-compatible fake of examples/demo-backends (constant answer "pong ...").
func deployMockLLM(t *testing.T, ns string) {
	t.Helper()
	src, err := os.ReadFile("../../examples/demo-backends/mock_llm.py")
	must(t, err)
	labels := map[string]string{"app": "e2e-llm"}
	must(t, c.Create(ctx, &corev1.ConfigMap{ObjectMeta: metav1.ObjectMeta{Name: "e2e-llm-src", Namespace: ns}, Data: map[string]string{"mock_llm.py": string(src)}}))
	one := int32(1)
	must(t, c.Create(ctx, &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "e2e-llm", Namespace: ns}, Spec: appsv1.DeploymentSpec{
		Replicas: &one, Selector: &metav1.LabelSelector{MatchLabels: labels},
		Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{Labels: labels}, Spec: corev1.PodSpec{
			Containers: []corev1.Container{{Name: "llm", Image: "registry.access.redhat.com/ubi9/python-312:latest",
				Command: []string{"python", "/src/mock_llm.py"}, Ports: []corev1.ContainerPort{{ContainerPort: 8000}},
				VolumeMounts: []corev1.VolumeMount{{Name: "src", MountPath: "/src"}}}},
			Volumes: []corev1.Volume{{Name: "src", VolumeSource: corev1.VolumeSource{ConfigMap: &corev1.ConfigMapVolumeSource{
				LocalObjectReference: corev1.LocalObjectReference{Name: "e2e-llm-src"}}}}},
		}}}}))
	must(t, c.Create(ctx, &corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: "e2e-llm", Namespace: ns}, Spec: corev1.ServiceSpec{
		Selector: labels, Ports: []corev1.ServicePort{{Port: 8000, TargetPort: intstr.FromInt32(8000)}}}}))
	eventually(t, "mock LLM ready", 5*time.Minute, func() (bool, string) {
		d := &appsv1.Deployment{}
		if err := c.Get(ctx, client.ObjectKey{Namespace: ns, Name: "e2e-llm"}, d); err != nil {
			return false, err.Error()
		}
		return d.Status.AvailableReplicas == 1, fmt.Sprintf("%d available", d.Status.AvailableReplicas)
	})
}

// internalAuthProbe calls MAS, RAG and identity (through its Service, as the apps do) from inside the namespace (allowed by the stack NetworkPolicy) with the
// internal identity header, without and with the shared secret; it exits 0 when only the secret is accepted.
const internalAuthProbe = `
import os, sys, urllib.request, urllib.error
def code(url, headers):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30).status
    except urllib.error.HTTPError as e:
        return e.code
secret = os.environ["INTERNAL_AUTH_SECRET"]
urls = {"mas": "http://unifai-multiagent-be:8003/api/resources/resources.list?category=llms",
        "rag": "http://unifai-rag-server:13456/api/data_sources/data.sources.get?source_type=DOCUMENT",
        "identity": "http://identity:13456/api/teams/teams.list"}
out, ok = [], True
for name, url in urls.items():
    bare = code(url, {"X-Authenticated-User": "admin"})
    wrong = code(url, {"X-Authenticated-User": "admin", "X-Internal-Auth": "wrong"})
    good = code(url, {"X-Authenticated-User": "admin", "X-Internal-Auth": secret})
    out.append("%s header-only=%d wrong-secret=%d secret=%d" % (name, bare, wrong, good))
    ok = ok and bare in (401, 403) and wrong in (401, 403) and good == 200
open("/dev/termination-log", "w").write("; ".join(out))
sys.exit(0 if ok else 1)
`

// checkInternalAuth runs internalAuthProbe in a pod of the namespace and fails unless MAS, RAG and identity refuse the
// internal identity header without the right X-Internal-Auth and accept it with the stack's secret.
func checkInternalAuth(t *testing.T, ns string) {
	t.Helper()
	pod := &corev1.Pod{ObjectMeta: metav1.ObjectMeta{Name: "e2e-internal-auth", Namespace: ns}, Spec: corev1.PodSpec{
		RestartPolicy: corev1.RestartPolicyNever,
		Containers: []corev1.Container{{Name: "probe", Image: "registry.access.redhat.com/ubi9/python-312:latest",
			Command: []string{"python", "-c", internalAuthProbe},
			Env: []corev1.EnvVar{{Name: "INTERNAL_AUTH_SECRET", ValueFrom: &corev1.EnvVarSource{SecretKeyRef: &corev1.SecretKeySelector{
				LocalObjectReference: corev1.LocalObjectReference{Name: "unifai-internal-auth"}, Key: "INTERNAL_AUTH_SECRET"}}}}}},
	}}
	must(t, c.Create(ctx, pod))
	defer func() { _ = c.Delete(ctx, pod) }()
	var msg string
	eventually(t, "internal auth probe finished", 5*time.Minute, func() (bool, string) {
		if err := c.Get(ctx, client.ObjectKeyFromObject(pod), pod); err != nil {
			return false, err.Error()
		}
		for _, cs := range pod.Status.ContainerStatuses {
			if term := cs.State.Terminated; term != nil {
				msg = term.Message
			}
		}
		return pod.Status.Phase == corev1.PodSucceeded || pod.Status.Phase == corev1.PodFailed, string(pod.Status.Phase)
	})
	t.Log(msg)
	if pod.Status.Phase != corev1.PodSucceeded {
		t.Errorf("MAS/RAG must accept X-Authenticated-User only with the internal secret: %s", msg)
	}
}
