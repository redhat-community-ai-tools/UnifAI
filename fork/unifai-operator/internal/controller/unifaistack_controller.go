package controller

import (
	"context"
	"fmt"
	"os"
	"sort"
	"strings"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/recorder"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/stack"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// StackReconciler deploys an UnifaiStack: generated secrets, hook ConfigMaps/Secrets, Helm releases by phase,
// an optional managed Keycloak, and the status of every component.
type StackReconciler struct {
	client.Client
	Engine *stack.Engine
	// OperatorNamespace is allowed through the stack NetworkPolicy.
	OperatorNamespace string
	// Recorder records an Event at each phase change (optional).
	Recorder recorder.EventRecorder
}

// NewStackReconciler builds the reconciler from the manager.
func NewStackReconciler(mgr ctrl.Manager) *StackReconciler {
	return &StackReconciler{Client: mgr.GetClient(), Engine: &stack.Engine{Config: mgr.GetConfig()}, OperatorNamespace: os.Getenv("POD_NAMESPACE"),
		Recorder: mgr.GetEventRecorder(EventSource)}
}

// specHashAnnotation records the desired spec of the Deployments the operator manages directly.
const specHashAnnotation = "unifai.startx.fr/spec-hash"

const (
	stackRequeue      = 15 * time.Second
	stackReadyRequeue = 5 * time.Minute
)

// The operator installs arbitrary chart content in the stack namespaces.
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaistacks,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaistacks/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaistacks/finalizers,verbs=update
// +kubebuilder:rbac:groups="",resources=configmaps;secrets;services;serviceaccounts;persistentvolumeclaims;endpoints,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups="",resources=pods,verbs=get;list;watch;delete
// +kubebuilder:rbac:groups="",resources=namespaces,verbs=get;list;watch
// +kubebuilder:rbac:groups="",resources=events,verbs=create;patch
// +kubebuilder:rbac:groups=apps,resources=deployments;statefulsets,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=batch,resources=jobs;cronjobs,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=autoscaling,resources=horizontalpodautoscalers,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=policy,resources=poddisruptionbudgets,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=networking.k8s.io,resources=networkpolicies;ingresses,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=rbac.authorization.k8s.io,resources=roles;rolebindings,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=route.openshift.io,resources=routes;routes/custom-host,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=config.openshift.io,resources=ingresses,verbs=get;list;watch
// +kubebuilder:rbac:groups=monitoring.coreos.com,resources=servicemonitors;prometheusrules,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=operators.coreos.com,resources=operatorgroups;subscriptions;clusterserviceversions,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=k8s.keycloak.org,resources=keycloaks;keycloakrealmimports,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=postgres-operator.crunchydata.com,resources=postgresclusters,verbs=get;list;watch;create;update;patch;delete

func (r *StackReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	st := &unifaiv1.UnifaiStack{}
	if err := r.Get(ctx, req.NamespacedName, st); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	if st.Name != unifaiv1.StackName { // defence in depth: the CRD already enforces it
		return ctrl.Result{}, nil
	}
	if !st.DeletionTimestamp.IsZero() {
		return r.finalize(ctx, st)
	}
	if !controllerutil.ContainsFinalizer(st, Finalizer) {
		controllerutil.AddFinalizer(st, Finalizer)
		if err := r.Update(ctx, st); err != nil {
			return ctrl.Result{}, err
		}
	}
	if st.Spec.Paused {
		return ctrl.Result{}, r.setStatus(ctx, st, "Paused", "reconciliation paused", metav1.ConditionFalse, "Paused")
	}
	requeue, err := r.deploy(ctx, st)
	if err != nil {
		log.FromContext(ctx).Error(err, "deploy failed")
		_ = r.setStatus(ctx, st, "Error", err.Error(), metav1.ConditionFalse, "Error")
		return ctrl.Result{RequeueAfter: stackRequeue}, nil
	}
	return ctrl.Result{RequeueAfter: requeue}, nil
}

func (r *StackReconciler) setStatus(ctx context.Context, st *unifaiv1.UnifaiStack, phase, msg string, ready metav1.ConditionStatus, reason string) error {
	prev := st.Status.Phase
	st.Status.Phase, st.Status.Message, st.Status.ObservedGeneration = phase, unifai.Truncate(msg, 1000), st.Generation
	st.Status.OperatorVersion = OperatorVersion
	meta.SetStatusCondition(&st.Status.Conditions, metav1.Condition{Type: "Ready", Status: ready, Reason: reason,
		Message: unifai.Truncate(msg, 1000), ObservedGeneration: st.Generation})
	// Merge patch from an empty status: no resourceVersion conflict (arrays such as components are replaced whole).
	base := st.DeepCopy()
	base.Status = unifaiv1.UnifaiStackStatus{}
	if err := r.Status().Patch(ctx, st, client.MergeFrom(base)); err != nil {
		return err
	}
	recordPhase(r.Recorder, st, prev, phase, msg)
	v := 0.0
	if ready == metav1.ConditionTrue {
		v = 1
	}
	stackReady.WithLabelValues(st.Namespace).Set(v)
	return nil
}

// clusterDomain returns the OpenShift apps domain ("" elsewhere).
func (r *StackReconciler) clusterDomain(ctx context.Context) string {
	u := &unstructured.Unstructured{}
	u.SetGroupVersionKind(schema.GroupVersionKind{Group: "config.openshift.io", Version: "v1", Kind: "Ingress"})
	if err := r.Get(ctx, types.NamespacedName{Name: "cluster"}, u); err != nil {
		return ""
	}
	d, _, _ := unstructured.NestedString(u.Object, "spec", "domain")
	return d
}

// plan builds the deployment plan: hosts, secrets (generated, overridden, integrations) and OIDC settings.
func (r *StackReconciler) plan(ctx context.Context, st *unifaiv1.UnifaiStack) (*stack.Plan, error) {
	p, err := stack.NewPlan(st, r.clusterDomain(ctx), r.OperatorNamespace)
	if err != nil {
		return nil, err
	}
	gen := &corev1.Secret{}
	err = r.Get(ctx, types.NamespacedName{Namespace: st.Namespace, Name: stack.GeneratedSecretName}, gen)
	switch {
	case apierrors.IsNotFound(err):
		gen = &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: stack.GeneratedSecretName, Namespace: st.Namespace,
			Labels: map[string]string{stack.LabelPartOf: "unifai", stack.LabelManagedBy: "unifai-operator"}}, Data: map[string][]byte{}}
		if err := r.seedFromExisting(ctx, st.Namespace, gen.Data); err != nil {
			return nil, err
		}
		stack.FillGenerated(gen.Data)
		if err := r.Create(ctx, gen); err != nil {
			return nil, err
		}
	case err != nil:
		return nil, err
	default:
		if gen.Data == nil {
			gen.Data = map[string][]byte{}
		}
		if stack.FillGenerated(gen.Data) { // keys added by a newer operator; existing keys are never changed
			if err := r.Update(ctx, gen); err != nil {
				return nil, err
			}
		}
	}
	p.Secrets = map[string]string{}
	for k, v := range gen.Data {
		p.Secrets[k] = string(v)
	}
	if ref := st.Spec.SecretsRef; ref != nil {
		var o corev1.Secret
		if err := r.Get(ctx, types.NamespacedName{Namespace: st.Namespace, Name: ref.Name}, &o); err != nil {
			return nil, fmt.Errorf("secretsRef %s: %w", ref.Name, err)
		}
		for k, v := range o.Data {
			p.Secrets[k] = string(v)
		}
	}
	get := func(sel *unifaiv1.SecretKeySelector) (string, error) {
		if sel == nil {
			return "", nil
		}
		var s corev1.Secret
		if err := r.Get(ctx, types.NamespacedName{Namespace: st.Namespace, Name: sel.Name}, &s); err != nil {
			return "", fmt.Errorf("secret %s: %w", sel.Name, err)
		}
		v, ok := s.Data[sel.Key]
		if !ok {
			return "", fmt.Errorf("secret %s has no key %s", sel.Name, sel.Key)
		}
		return string(v), nil
	}
	in := st.Spec.Integrations
	refs := map[string]*unifaiv1.SecretKeySelector{"GCP_SA_KEY_JSON": in.GCPServiceAccountKey}
	if s := in.Slack; s != nil {
		refs["SLACK_BOT_TOKEN"], refs["SLACK_USER_TOKEN"], refs["SLACK_APP_TOKEN"], refs["SLACK_SIGNING_SECRET"] = s.BotToken, s.UserToken, s.AppToken, s.SigningSecret
	}
	if u := in.Umami; u != nil {
		p.Secrets["UMAMI_URL"], p.Secrets["UMAMI_WEBSITE_NAME"] = u.URL, u.WebsiteName
		refs["UMAMI_USERNAME"], refs["UMAMI_PASSWORD"] = u.Username, u.Password
	}
	if c := st.Spec.RAG.Confluence; c != nil {
		refs["CONFLUENCE_USERNAME"], refs["CONFLUENCE_TOKEN"] = c.Username, &c.Token
	}
	if l := in.Langfuse; l != nil {
		p.Secrets["LANGFUSE_BASE_URL"] = l.BaseURL
		refs["LANGFUSE_PUBLIC_KEY"], refs["LANGFUSE_SECRET_KEY"] = &l.PublicKey, &l.SecretKey
	}
	for k, sel := range refs {
		if sel == nil {
			continue
		}
		v, err := get(sel)
		if err != nil {
			return nil, err
		}
		p.Secrets[k] = v
	}
	id := st.Spec.Identity
	switch {
	case id.External != nil:
		p.OIDCURL, p.OIDCRealm, p.OIDCClientID = strings.TrimRight(id.External.URL, "/"), id.External.Realm, id.External.ClientID
		if p.OIDCRealm == "" {
			p.OIDCRealm = "unifai"
		}
		if p.OIDCClientID == "" {
			p.OIDCClientID = "unifai"
		}
		if p.OIDCClientSecret, err = get(&id.External.ClientSecret); err != nil {
			return nil, err
		}
	case id.Keycloak != nil:
		p.OIDCURL, p.OIDCRealm, p.OIDCClientID = "https://"+p.KeycloakHost, stack.RealmName, stack.ClientID
		p.OIDCClientSecret = p.Secrets[stack.KeyClientSecret]
	default:
		return nil, fmt.Errorf("spec.identity needs external or keycloak")
	}
	return p, nil
}

// apply creates or updates an object owned by the stack (data/spec fields are replaced).
func (r *StackReconciler) apply(ctx context.Context, st *unifaiv1.UnifaiStack, obj client.Object) error {
	if err := controllerutil.SetControllerReference(st, obj, r.Scheme()); err != nil {
		return err
	}
	desired := obj.DeepCopyObject().(client.Object)
	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, obj, func() error {
		obj.SetLabels(desired.GetLabels())
		obj.SetOwnerReferences(desired.GetOwnerReferences())
		switch o := obj.(type) {
		case *corev1.ConfigMap:
			o.Data = desired.(*corev1.ConfigMap).Data
		case *corev1.Secret:
			d := desired.(*corev1.Secret)
			o.Data, o.StringData, o.Type = secretData(d), nil, d.Type
		case *networkingv1.NetworkPolicy:
			o.Spec = desired.(*networkingv1.NetworkPolicy).Spec
		case *corev1.Service:
			d := desired.(*corev1.Service)
			o.Spec.Ports, o.Spec.Selector = d.Spec.Ports, d.Spec.Selector
		case *appsv1.Deployment:
			// Replaced only when the desired spec changes (server defaults would make every compare differ).
			d := desired.(*appsv1.Deployment)
			h := hash(d.Spec)
			if o.Annotations[specHashAnnotation] != h {
				o.Spec = d.Spec
				if o.Annotations == nil {
					o.Annotations = map[string]string{}
				}
				o.Annotations[specHashAnnotation] = h
			}
		case *batchv1.CronJob:
			// Same rule as Deployments: replace the spec only when the desired one changes.
			d := desired.(*batchv1.CronJob)
			h := hash(d.Spec)
			if o.Annotations[specHashAnnotation] != h {
				o.Spec = d.Spec
				if o.Annotations == nil {
					o.Annotations = map[string]string{}
				}
				o.Annotations[specHashAnnotation] = h
			}
		default:
			return fmt.Errorf("unsupported object %T", obj)
		}
		return nil
	})
	return err
}

func (r *StackReconciler) deploy(ctx context.Context, st *unifaiv1.UnifaiStack) (time.Duration, error) {
	p, err := r.plan(ctx, st)
	if err != nil {
		return 0, err
	}
	if p.LiveVolumes, p.LiveClaimTemplates, err = r.liveVolumes(ctx, st.Namespace); err != nil {
		return 0, err
	}
	base := stack.BaseObjects(p)
	p.ConfigHash = configHash(base)
	managed := map[string]bool{}
	for _, o := range base {
		managed[o.GetName()] = true
	}
	for _, sc := range stack.ServiceConfigs {
		managed[sc.ConfigMap] = true
	}
	if err := r.removeLegacyReleases(ctx, st.Namespace, managed); err != nil {
		return 0, err
	}
	for _, o := range base {
		if err := r.apply(ctx, st, o); err != nil {
			return 0, fmt.Errorf("%T %s: %w", o, o.GetName(), err)
		}
	}
	if !(st.Spec.Exposure.NetworkPolicy == nil || *st.Spec.Exposure.NetworkPolicy) {
		np := &unstructured.Unstructured{}
		np.SetGroupVersionKind(schema.GroupVersionKind{Group: "networking.k8s.io", Version: "v1", Kind: "NetworkPolicy"})
		np.SetNamespace(st.Namespace)
		np.SetName(stack.NetworkPolicyName)
		if err := r.Delete(ctx, np); client.IgnoreNotFound(err) != nil {
			return 0, err
		}
	}

	if err := r.reconcileBackups(ctx, st, p); err != nil {
		return 0, err
	}

	waiting := []string{}
	embedding := stack.EmbeddingObjects(p)
	for _, o := range embedding {
		if err := r.apply(ctx, st, o); err != nil {
			return 0, fmt.Errorf("%T %s: %w", o, o.GetName(), err)
		}
	}
	if len(embedding) == 0 {
		for _, o := range []client.Object{
			&appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Namespace: st.Namespace, Name: stack.EmbeddingName}},
			&corev1.Service{ObjectMeta: metav1.ObjectMeta{Namespace: st.Namespace, Name: stack.EmbeddingName}},
		} {
			if err := r.Delete(ctx, o); client.IgnoreNotFound(err) != nil {
				return 0, err
			}
		}
	} else if msg, err := stack.WorkloadsReady(ctx, r.Client, st.Namespace,
		[]stack.ManifestObject{{Kind: "Deployment", Name: stack.EmbeddingName}}); err != nil {
		return 0, err
	} else if msg != "" {
		waiting = append(waiting, "embedding: "+msg)
	}
	kcReady := true
	if st.Spec.Identity.Keycloak != nil {
		kc := &stack.Keycloak{Client: r.Client, SetOwner: func(o client.Object) error {
			return controllerutil.SetControllerReference(st, o, r.Scheme())
		}}
		msg, err := kc.Ensure(ctx, p)
		if err != nil {
			return 0, fmt.Errorf("keycloak: %w", err)
		}
		if msg != "" {
			kcReady = false
			waiting = append(waiting, "keycloak: "+msg)
		}
	}

	prev := map[string]unifaiv1.ComponentStatus{}
	for _, c := range st.Status.Components {
		prev[c.Name] = c
	}
	var comps []unifaiv1.ComponentStatus
	phaseReady := map[int]bool{0: true, 1: true, 2: true}
	phaseInstalled := map[int]bool{0: true, 1: true, 2: true}
	for phase := 0; phase <= 2; phase++ {
		// Applications wait for the shared resources; the UI waits for the applications' Services.
		blocked := (phase == 1 && !phaseReady[0]) || (phase == 2 && !phaseInstalled[1])
		for _, rel := range stack.Releases {
			if rel.Phase != phase {
				continue
			}
			if !rel.IsEnabled(p) {
				if _, err := r.Engine.Uninstall(ctx, st.Namespace, rel.Name); err != nil {
					return 0, err
				}
				continue
			}
			cs := unifaiv1.ComponentStatus{Name: rel.Name}
			if blocked {
				cs.Message = "waiting for the previous phase"
				phaseReady[phase], phaseInstalled[phase] = false, false
				comps = append(comps, cs)
				continue
			}
			cs, err := r.applyRelease(ctx, p, rel, prev[rel.Name])
			if err != nil {
				return 0, err
			}
			if cs.Revision == 0 {
				phaseInstalled[phase] = false
			}
			if !cs.Ready {
				phaseReady[phase] = false
				waiting = append(waiting, rel.Name+": "+cs.Message)
			}
			comps = append(comps, cs)
		}
		if phase == 1 && phaseInstalled[1] {
			missing, err := r.serviceConfigs(ctx, st, p)
			if err != nil {
				return 0, err
			}
			if missing != "" {
				phaseInstalled[1] = false
				waiting = append(waiting, missing)
			}
		}
	}

	st.Status.Components = comps
	st.Status.Version = p.Version
	st.Status.Endpoints = unifaiv1.StackEndpoints{
		UI: "https://" + p.UIHost, Identity: "https://" + p.IdentityHost,
		MultiAgent: fmt.Sprintf("http://unifai-multiagent-be.%s.svc:%d", p.Namespace, unifai.MASPort),
		RAG:        fmt.Sprintf("http://unifai-rag-server.%s.svc:%d", p.Namespace, unifai.RAGPort),
	}
	if p.KeycloakHost != "" {
		st.Status.Endpoints.Keycloak = "https://" + p.KeycloakHost
	}
	embeddingReady := !strings.Contains(strings.Join(waiting, ";"), "embedding: ")
	if kcReady && embeddingReady && phaseReady[0] && phaseReady[1] && phaseReady[2] {
		return stackReadyRequeue, r.setStatus(ctx, st, "Ready", "all components ready", metav1.ConditionTrue, "Ready")
	}
	sort.Strings(waiting)
	return stackRequeue, r.setStatus(ctx, st, "Deploying", strings.Join(waiting, "; "), metav1.ConditionFalse, "Deploying")
}

// applyRelease installs/upgrades a release when its inputs changed, then reports its readiness.
func (r *StackReconciler) applyRelease(ctx context.Context, p *stack.Plan, rel stack.Release, prev unifaiv1.ComponentStatus) (unifaiv1.ComponentStatus, error) {
	cs := unifaiv1.ComponentStatus{Name: rel.Name}
	rr, err := stack.Render(p, rel)
	if err != nil {
		return cs, err
	}
	cur, err := r.Engine.Get(ctx, p.Namespace, rel.Name)
	if err != nil {
		return cs, err
	}
	// The hash is stored on the Helm release itself, so a lost status never causes a needless upgrade.
	deployed := cur != nil && cur.Info != nil && cur.Info.Status == "deployed"
	if !deployed || cur.Labels[stack.HashLabel] != rr.Hash {
		log.FromContext(ctx).Info("applying release", "release", rel.Name, "upgrade", cur != nil)
		start := time.Now()
		cur, err = r.Engine.Apply(ctx, p, rr)
		result := "ok"
		if err != nil {
			result = "error"
		}
		helmApplySeconds.WithLabelValues(rel.Name, result).Observe(time.Since(start).Seconds())
		if err != nil {
			return cs, fmt.Errorf("release %s: %w", rel.Name, err)
		}
	}
	cs.Revision, cs.Hash = cur.Version, rr.Hash
	objs, err := stack.ParseManifest(cur.Manifest)
	if err != nil {
		return cs, err
	}
	waiting, err := stack.WorkloadsReady(ctx, r.Client, p.Namespace, objs)
	if err != nil {
		return cs, err
	}
	cs.Ready, cs.Message = waiting == "", waiting
	if cs.Ready {
		cs.Message = "ready"
	}
	return cs, nil
}

// serviceConfigs writes the ConfigMaps the upstream postsync hooks derived from the application Services.
func (r *StackReconciler) serviceConfigs(ctx context.Context, st *unifaiv1.UnifaiStack, p *stack.Plan) (string, error) {
	for _, sc := range stack.ServiceConfigs {
		var svc corev1.Service
		if err := r.Get(ctx, types.NamespacedName{Namespace: p.Namespace, Name: sc.Service}, &svc); err != nil {
			if apierrors.IsNotFound(err) {
				return "waiting for service " + sc.Service, nil
			}
			return "", err
		}
		if err := r.apply(ctx, st, stack.ServiceConfig(p, sc.ConfigMap, sc.Prefix, sc.Component, &svc)); err != nil {
			return "", err
		}
	}
	return "", nil
}

// finalize removes the releases (reverse order), the managed Keycloak and, with deletionPolicy Delete, the data.
func (r *StackReconciler) finalize(ctx context.Context, st *unifaiv1.UnifaiStack) (ctrl.Result, error) {
	if !controllerutil.ContainsFinalizer(st, Finalizer) {
		return ctrl.Result{}, nil
	}
	removeData := st.Spec.DeletionPolicy == "Delete"
	if st.Status.Phase != "Deleting" {
		_ = r.setStatus(ctx, st, "Deleting", "removing the stack", metav1.ConditionFalse, "Deleting")
	}
	var pvcs []string
	for i := len(stack.Releases) - 1; i >= 0; i-- {
		rel := stack.Releases[i]
		cur, err := r.Engine.Get(ctx, st.Namespace, rel.Name)
		if err != nil {
			return ctrl.Result{}, err
		}
		if cur == nil {
			continue
		}
		objs, _ := stack.ParseManifest(cur.Manifest)
		for _, o := range objs {
			if o.Kind == "PersistentVolumeClaim" {
				pvcs = append(pvcs, o.Name)
			}
			for _, t := range o.ClaimTemplates {
				for n := 0; n < o.Replicas; n++ {
					pvcs = append(pvcs, fmt.Sprintf("%s-%s-%d", t, o.Name, n))
				}
			}
		}
		if _, err := r.Engine.Uninstall(ctx, st.Namespace, rel.Name); err != nil {
			return ctrl.Result{}, fmt.Errorf("uninstall %s: %w", rel.Name, err)
		}
	}
	kc := &stack.Keycloak{Client: r.Client}
	gone, err := kc.Delete(ctx, st.Namespace, removeData)
	if err != nil {
		return ctrl.Result{}, err
	}
	if !gone {
		return ctrl.Result{RequeueAfter: 5 * time.Second}, nil
	}
	if removeData {
		for _, n := range pvcs {
			pvc := &corev1.PersistentVolumeClaim{ObjectMeta: metav1.ObjectMeta{Namespace: st.Namespace, Name: n}}
			if err := r.Delete(ctx, pvc); client.IgnoreNotFound(err) != nil {
				return ctrl.Result{}, err
			}
		}
		gen := &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Namespace: st.Namespace, Name: stack.GeneratedSecretName}}
		if err := r.Delete(ctx, gen); client.IgnoreNotFound(err) != nil {
			return ctrl.Result{}, err
		}
	}
	r.Engine.Forget(st.Namespace)
	stackReady.DeleteLabelValues(st.Namespace)
	controllerutil.RemoveFinalizer(st, Finalizer)
	return ctrl.Result{}, r.Update(ctx, st)
}

// reconcileBackups applies the backup CronJobs, or deletes them when spec.backup is unset. The backups
// themselves live in S3 and are never deleted by the operator.
func (r *StackReconciler) reconcileBackups(ctx context.Context, st *unifaiv1.UnifaiStack, p *stack.Plan) error {
	jobs := stack.BackupObjects(p)
	for _, o := range jobs {
		if err := r.apply(ctx, st, o); err != nil {
			return fmt.Errorf("%T %s: %w", o, o.GetName(), err)
		}
	}
	if len(jobs) == 0 {
		for _, name := range stack.BackupNames {
			cj := &batchv1.CronJob{ObjectMeta: metav1.ObjectMeta{Namespace: st.Namespace, Name: name}}
			if err := r.Delete(ctx, cj); client.IgnoreNotFound(err) != nil {
				return err
			}
		}
	}
	return nil
}

// SetupWithManager registers the controller; owned ConfigMaps/Secrets trigger a reconcile when edited by hand.
func (r *StackReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiStack{}).
		Owns(&corev1.ConfigMap{}).Owns(&corev1.Secret{}).Owns(&appsv1.Deployment{}).Owns(&batchv1.CronJob{}).
		Named("unifaistack").Complete(r)
}

// secretData returns the bytes of a Secret built with StringData (so CreateOrUpdate sees no change when equal).
func secretData(s *corev1.Secret) map[string][]byte {
	out := make(map[string][]byte, len(s.Data)+len(s.StringData))
	for k, v := range s.Data {
		out[k] = v
	}
	for k, v := range s.StringData {
		out[k] = []byte(v)
	}
	return out
}

// configHash fingerprints the ConfigMaps/Secrets read by the pods.
func configHash(objs []client.Object) string {
	parts := map[string]any{}
	for _, o := range objs {
		switch t := o.(type) {
		case *corev1.ConfigMap:
			parts["cm/"+t.Name] = t.Data
		case *corev1.Secret:
			parts["secret/"+t.Name] = secretData(t)
		}
	}
	return hash(parts)
}

// liveVolumes records the existing PVCs and StatefulSet claim templates of the namespace (see Plan.LiveVolumes).
func (r *StackReconciler) liveVolumes(ctx context.Context, ns string) (map[string]corev1.PersistentVolumeClaimSpec, map[string]corev1.PersistentVolumeClaim, error) {
	out := map[string]corev1.PersistentVolumeClaimSpec{}
	tpl := map[string]corev1.PersistentVolumeClaim{}
	var pvcs corev1.PersistentVolumeClaimList
	if err := r.List(ctx, &pvcs, client.InNamespace(ns)); err != nil {
		return nil, nil, err
	}
	for _, p := range pvcs.Items {
		out["pvc/"+p.Name] = p.Spec
	}
	var stss appsv1.StatefulSetList
	if err := r.List(ctx, &stss, client.InNamespace(ns)); err != nil {
		return nil, nil, err
	}
	for _, s := range stss.Items {
		for _, t := range s.Spec.VolumeClaimTemplates {
			tpl[s.Name+"/"+t.Name] = t
		}
	}
	return out, tpl, nil
}

// seedFromExisting copies the keys of a stack deployed before (helmfile or an older operator) into a new generated
// secret: a new CREDENTIAL_ENCRYPTION_KEY would make the credentials stored in MongoDB unreadable.
func (r *StackReconciler) seedFromExisting(ctx context.Context, ns string, data map[string][]byte) error {
	sources := map[string][]string{
		"multiagent-be-secret": {stack.KeyCredentialKey, stack.KeyOAuthState},
		"shared-secret":        {stack.KeySecretKey, stack.KeyRedisPassword},
	}
	for name, keys := range sources {
		var s corev1.Secret
		err := r.Get(ctx, types.NamespacedName{Namespace: ns, Name: name}, &s)
		if apierrors.IsNotFound(err) {
			continue
		}
		if err != nil {
			return err
		}
		for _, k := range keys {
			if v := s.Data[k]; len(v) > 0 {
				data[k] = v
			}
		}
	}
	return nil
}

// legacyReleases are the helmfile "dummy" ConfigMap charts: the operator writes these ConfigMaps itself.
var legacyReleases = []string{"unifai-redis-config", "unifai-shared-config", "unifai-rag-config", "multiagent-config"}

// removeLegacyReleases uninstalls the helmfile dummy releases, keeping the ConfigMaps the operator manages.
func (r *StackReconciler) removeLegacyReleases(ctx context.Context, ns string, managed map[string]bool) error {
	for _, name := range legacyReleases {
		rel, err := r.Engine.Get(ctx, ns, name)
		if err != nil || rel == nil {
			if err != nil {
				return err
			}
			continue
		}
		objs, _ := stack.ParseManifest(rel.Manifest)
		for _, o := range objs {
			if o.Kind != "ConfigMap" || !managed[o.Name] {
				continue
			}
			cm := &corev1.ConfigMap{}
			if err := r.Get(ctx, types.NamespacedName{Namespace: ns, Name: o.Name}, cm); err != nil {
				if apierrors.IsNotFound(err) {
					continue
				}
				return err
			}
			if cm.Annotations == nil {
				cm.Annotations = map[string]string{}
			}
			cm.Annotations["helm.sh/resource-policy"] = "keep"
			if err := r.Update(ctx, cm); err != nil {
				return err
			}
		}
		log.FromContext(ctx).Info("removing helmfile dummy release", "release", name)
		if _, err := r.Engine.Uninstall(ctx, ns, name); err != nil {
			return err
		}
	}
	return nil
}
