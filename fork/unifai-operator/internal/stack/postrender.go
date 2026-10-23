package stack

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"slices"
	"strings"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	utilyaml "k8s.io/apimachinery/pkg/util/yaml"
	"sigs.k8s.io/yaml"
)

// Labels set on every object of the stack.
const (
	LabelPartOf    = "app.kubernetes.io/part-of"
	LabelManagedBy = "unifai.startx.fr/managed-by"
	LabelComponent = "unifai.startx.fr/component"
	// LabelStackNamespace marks the cluster-scoped objects of a stack.
	LabelStackNamespace = "unifai.startx.fr/stack-namespace"
	// PartOf is the value of LabelPartOf.
	PartOf = "unifai"
)

// Names used by the post-renderer.
const (
	uiRelease       = "unifai-ui"
	kindDeployment  = "Deployment"
	kindStatefulSet = "StatefulSet"
)

// QuiesceAnnotation on the UnifaiStack (value: the UnifaiRestore name) stops the UnifAI applications.
const QuiesceAnnotation = "unifai.startx.fr/quiesced-by"

func (r *postRenderer) quiesced() bool { return r.plan.Quiesced && r.rel.Quiescable() }

// devCaps are the request ceilings of the dev profile (limits are kept).
var devCaps = corev1.ResourceList{corev1.ResourceCPU: resource.MustParse("100m"), corev1.ResourceMemory: resource.MustParse("512Mi")}

// postRenderer applies the stack settings that upstream charts do not expose uniformly.
type postRenderer struct {
	plan *Plan
	rel  Release
	rwo  map[string]bool
}

// Run implements helm's postrender.PostRenderer.
func (r *postRenderer) Run(in *bytes.Buffer) (*bytes.Buffer, error) {
	reader := utilyaml.NewYAMLReader(bufio.NewReader(in))
	var objs []map[string]any
	for {
		doc, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		obj := map[string]any{}
		if err := yaml.Unmarshal(doc, &obj); err != nil {
			return nil, err
		}
		if len(obj) > 0 {
			objs = append(objs, obj)
		}
	}
	r.rwo = r.readWriteOnceClaims(objs)
	out := &bytes.Buffer{}
	for _, obj := range objs {
		keep, err := r.mutate(obj)
		if err != nil {
			return nil, fmt.Errorf("%s %s: %w", obj["kind"], name(obj), err)
		}
		if !keep {
			continue
		}
		b, err := yaml.Marshal(obj)
		if err != nil {
			return nil, err
		}
		out.WriteString("---\n")
		out.Write(b)
	}
	return out, nil
}

// readWriteOnceClaims lists the ReadWriteOnce PVCs of the release (rendered or already existing).
func (r *postRenderer) readWriteOnceClaims(objs []map[string]any) map[string]bool {
	rwo := map[string]bool{}
	for _, o := range objs {
		if o["kind"] != "PersistentVolumeClaim" {
			continue
		}
		for _, m := range asSlice(mapAt(o, "spec")["accessModes"]) {
			if m == "ReadWriteOnce" {
				rwo[name(o)] = true
			}
		}
	}
	for key, spec := range r.plan.LiveVolumes {
		for _, m := range spec.AccessModes {
			if m == corev1.ReadWriteOnce && strings.HasPrefix(key, "pvc/") {
				rwo[strings.TrimPrefix(key, "pvc/")] = true
			}
		}
	}
	return rwo
}

// usesRWO reports whether a pod template mounts a ReadWriteOnce claim: a rolling update would start the new pod
// on a volume the old one still holds (and locks), so such Deployments must be recreated.
func (r *postRenderer) usesRWO(tpl map[string]any) bool {
	for _, v := range asSlice(mapAt(tpl, "spec")["volumes"]) {
		vm, _ := v.(map[string]any)
		if c, ok := mapAt(vm, "persistentVolumeClaim")["claimName"].(string); ok && r.rwo[c] {
			return true
		}
	}
	return false
}

func name(obj map[string]any) string {
	n, _ := mapAt(obj, "metadata")["name"].(string)
	return n
}

// paasLabels are Red Hat internal PaaS labels hard-coded in some upstream templates.
var paasLabels = []string{"paas.redhat.com/appcode"}

// stripLabels removes paasLabels from every `labels` map of the object.
func stripLabels(v any) {
	switch t := v.(type) {
	case map[string]any:
		for k, x := range t {
			if l, ok := x.(map[string]any); ok && k == "labels" {
				for _, drop := range paasLabels {
					delete(l, drop)
				}
			}
			stripLabels(x)
		}
	case []any:
		for _, x := range t {
			stripLabels(x)
		}
	}
}

func (r *postRenderer) mutate(obj map[string]any) (bool, error) {
	stripLabels(obj)
	kind, _ := obj["kind"].(string)
	md := mapAt(obj, "metadata")
	obj["metadata"] = md
	labels := mapAt(md, "labels")
	labels[LabelPartOf] = PartOf
	labels[LabelManagedBy] = "unifai-operator"
	labels[LabelComponent] = r.rel.Component
	md["labels"] = labels
	spec := mapAt(obj, "spec")

	switch kind {
	case "Route":
		switch r.rel.Name {
		case uiRelease:
			r.setHost(md, spec, r.plan.UIHost)
			// Re-encrypt (was passthrough) so the router sees, and strips, the request headers; the backend
			// certificate is the service-ca one mounted below, trusted by the router without configuration.
			tls := mapAt(spec, "tls")
			tls["termination"] = "reencrypt"
			spec["tls"] = tls
		case "unifai-identity":
			r.setHost(md, spec, r.plan.IdentityHost)
		default:
			if r.rel.Internal && !r.plan.Spec.Exposure.ExposeInternal {
				return false, nil
			}
		}
		stripInternalAuthHeader(spec)
	case "Service":
		if r.rel.Name == uiRelease {
			a := mapAt(md, "annotations")
			a["service.beta.openshift.io/serving-cert-secret-name"] = UITLSSecret
			md["annotations"] = a
		}
	case "NetworkPolicy":
		// The upstream charts admit their port from every namespace (MongoDB, RabbitMQ, docling) or everything
		// (Temporal, Redis Insight): NetworkPolicies add up, so they would undo the stack ones.
		return false, nil
	case "HorizontalPodAutoscaler":
		if r.plan.Dev() || r.quiesced() {
			return false, nil
		}
	case "PersistentVolumeClaim":
		r.keepPVC(md)
		r.liveVolume(spec, "pvc/"+name(obj))
	case kindDeployment, kindStatefulSet:
		if kind == kindStatefulSet {
			r.claimTemplates(name(obj), spec)
		}
		tpl := mapAt(spec, "template")
		if kind == kindDeployment && r.plan.Dev() && spec["replicas"] == nil {
			spec["replicas"] = 1 // no HPA in dev: never keep the replicas an HPA left behind
		}
		if kind == kindDeployment && r.quiesced() {
			spec["replicas"] = 0
		}
		if kind == kindDeployment && r.usesRWO(tpl) {
			// rollingUpdate: null makes the upgrade patch drop the live rolling settings (rejected with Recreate).
			spec["strategy"] = map[string]any{"type": "Recreate", "rollingUpdate": nil}
		}
		if kind == kindDeployment && r.rel.Name == uiRelease {
			mountUITLS(tpl)
		}
		if err := r.mutatePod(tpl); err != nil {
			return false, err
		}
		spec["template"] = tpl
	}
	if len(spec) > 0 {
		obj["spec"] = spec
	}
	return true, nil
}

// claimTemplates keeps the live claim templates of a StatefulSet (immutable) and the PVC retention of new ones.
func (r *postRenderer) claimTemplates(sts string, spec map[string]any) {
	for _, t := range asSlice(spec["volumeClaimTemplates"]) {
		tm, ok := t.(map[string]any)
		if !ok {
			continue
		}
		tmd := mapAt(tm, "metadata")
		if live, ok := r.plan.LiveClaimTemplates[sts+"/"+fmt.Sprint(tmd["name"])]; ok {
			lm := toMap(live)
			delete(lm, "status")
			for k := range tm {
				delete(tm, k)
			}
			for k, v := range lm {
				tm[k] = v
			}
			continue
		}
		r.keepPVC(tmd)
		tm["metadata"] = tmd
	}
}

func (r *postRenderer) setHost(md, spec map[string]any, host string) {
	spec["host"] = host
	if a := mapAt(md, "annotations"); len(a) > 0 {
		delete(a, "openshift.io/host.generated")
		md["annotations"] = a
	}
}

// liveVolume keeps the size, class and access modes of a volume that already exists.
func (r *postRenderer) liveVolume(spec map[string]any, key string) {
	live, ok := r.plan.LiveVolumes[key]
	if !ok {
		return
	}
	if q, ok := live.Resources.Requests[corev1.ResourceStorage]; ok {
		res := mapAt(spec, "resources")
		req := mapAt(res, "requests")
		req["storage"] = q.String()
		res["requests"] = req
		spec["resources"] = res
	}
	if live.StorageClassName != nil {
		spec["storageClassName"] = *live.StorageClassName
	}
	if len(live.AccessModes) > 0 {
		var am []any
		for _, m := range live.AccessModes {
			am = append(am, string(m))
		}
		spec["accessModes"] = am
	}
}

func (r *postRenderer) keepPVC(md map[string]any) {
	if r.plan.Spec.DeletionPolicy == "Delete" {
		return
	}
	a := mapAt(md, "annotations")
	a["helm.sh/resource-policy"] = "keep"
	md["annotations"] = a
}

func asSlice(v any) []any {
	s, _ := v.([]any)
	return s
}

func (r *postRenderer) mutatePod(tpl map[string]any) error {
	md := mapAt(tpl, "metadata")
	labels := mapAt(md, "labels")
	labels[LabelPartOf] = PartOf
	labels[LabelComponent] = r.rel.Component
	md["labels"] = labels
	if r.plan.ConfigHash != "" {
		a := mapAt(md, "annotations")
		a["unifai.startx.fr/config-hash"] = r.plan.ConfigHash
		md["annotations"] = a
	}
	tpl["metadata"] = md
	ps := mapAt(tpl, "spec")
	defer func() { tpl["spec"] = ps }()

	s := r.plan.Spec
	if len(s.NodeSelector) > 0 {
		ns := mapAt(ps, "nodeSelector")
		for k, v := range s.NodeSelector {
			ns[k] = v
		}
		ps["nodeSelector"] = ns
	}
	if len(s.Tolerations) > 0 {
		tol := asSlice(ps["tolerations"])
		for _, t := range s.Tolerations {
			tol = append(tol, toMap(t))
		}
		ps["tolerations"] = tol
	}
	if len(s.ImagePullSecrets) > 0 {
		ips := asSlice(ps["imagePullSecrets"])
		for _, ref := range s.ImagePullSecrets {
			ips = append(ips, map[string]any{"name": ref.Name})
		}
		ps["imagePullSecrets"] = ips
	}
	for _, key := range []string{"containers", "initContainers"} {
		cs := asSlice(ps[key])
		for i, c := range cs {
			cm, ok := c.(map[string]any)
			if !ok {
				continue
			}
			res, err := r.resources(cm["resources"], key == "containers" && i == 0)
			if err != nil {
				return err
			}
			cm["resources"] = res
			if key == "containers" {
				r.env(cm)
			}
		}
	}
	if !r.plan.Spec.RAG.GPU {
		// The upstream rag-celery chart targets GPU nodes.
		delete(ps, "runtimeClassName")
		if sel := mapAt(ps, "nodeSelector"); len(sel) > 0 {
			for k := range sel {
				if strings.Contains(k, "nvidia.com") {
					delete(sel, k)
				}
			}
		}
	}
	return nil
}

// env adds INTERNAL_AUTH_SECRET (secretKeyRef) to the services that check it, then spec.extraEnv of the component;
// a variable of the chart with the same name is replaced.
func (r *postRenderer) env(c map[string]any) {
	extra := r.plan.Spec.ExtraEnv[r.rel.Component]
	add := make([]map[string]any, 0, len(extra)+1)
	if r.rel.InternalAuth {
		add = append(add, map[string]any{"name": KeyInternalAuth, "valueFrom": map[string]any{
			"secretKeyRef": map[string]any{"name": InternalAuthSecret, "key": KeyInternalAuth}}})
	}
	for _, e := range extra {
		add = append(add, toMap(e))
	}
	if len(add) == 0 {
		return
	}
	env := asSlice(c["env"])
	for _, a := range add {
		replaced := false
		for i, e := range env {
			if em, ok := e.(map[string]any); ok && em["name"] == a["name"] {
				env[i], replaced = a, true
			}
		}
		if !replaced {
			env = append(env, a)
		}
	}
	c["env"] = env
}

// resources applies, in order: the spec override of the component (main container only), the dev ceilings, the GPU switch.
func (r *postRenderer) resources(v any, main bool) (map[string]any, error) {
	var rr corev1.ResourceRequirements
	if v != nil {
		b, _ := json.Marshal(v)
		if err := json.Unmarshal(b, &rr); err != nil {
			return nil, err
		}
	}
	if o, ok := r.plan.Spec.Resources[r.rel.Component]; ok && main {
		rr = *o.DeepCopy()
	} else if r.plan.Dev() {
		for name, ceiling := range devCaps {
			if q, ok := rr.Requests[name]; ok && q.Cmp(ceiling) > 0 {
				rr.Requests[name] = ceiling
			}
		}
	}
	if !r.plan.Spec.RAG.GPU {
		delete(rr.Requests, "nvidia.com/gpu")
		delete(rr.Limits, "nvidia.com/gpu")
	}
	return toMap(rr), nil
}

func toMap(v any) map[string]any {
	b, _ := json.Marshal(v)
	m := map[string]any{}
	_ = json.Unmarshal(b, &m)
	return m
}

// InternalAuthHeader is trusted by MAS and RAG as the caller identity when no session cookie is sent; it is meant
// for pod-to-pod calls only and must never come from outside the cluster.
const InternalAuthHeader = "X-Authenticated-User"

// InternalSecretHeader carries the shared INTERNAL_AUTH_SECRET that makes the services honour InternalAuthHeader.
const InternalSecretHeader = "X-Internal-Auth"

// internalHeaders are deleted from every request coming through a Route.
var internalHeaders = []string{InternalAuthHeader, InternalSecretHeader}

// UITLSSecret receives the service-ca certificate of the UI Service (OpenShift serving certificate).
const UITLSSecret = "unifai-ui-tls"

// stripInternalAuthHeader makes the router delete the internal headers from incoming requests. Passthrough routes
// cannot change headers (TLS reaches the pod), so the UI route is re-encrypted.
func stripInternalAuthHeader(spec map[string]any) {
	if mapAt(spec, "tls")["termination"] == "passthrough" {
		return
	}
	hh := mapAt(spec, "httpHeaders")
	actions := mapAt(hh, "actions")
	cur := asSlice(actions["request"])
	req := make([]any, 0, len(cur)+len(internalHeaders))
	for _, a := range cur {
		if am, ok := a.(map[string]any); ok && slices.Contains(internalHeaders, fmt.Sprint(am["name"])) {
			continue
		}
		req = append(req, a)
	}
	for _, h := range internalHeaders {
		req = append(req, map[string]any{"name": h, "action": map[string]any{"type": "Delete"}})
	}
	actions["request"] = req
	hh["actions"] = actions
	spec["httpHeaders"] = hh
}

// mountUITLS replaces the self-signed certificate baked in the UI image with the service-ca one.
func mountUITLS(tpl map[string]any) {
	ps := mapAt(tpl, "spec")
	vols := asSlice(ps["volumes"])
	vols = append(vols, map[string]any{"name": "ui-tls", "secret": map[string]any{
		"secretName": UITLSSecret,
		"items": []any{
			map[string]any{"key": "tls.crt", "path": "unifai.crt"},
			map[string]any{"key": "tls.key", "path": "unifai.key"},
		},
	}})
	ps["volumes"] = vols
	for _, c := range asSlice(ps["containers"]) {
		cm, ok := c.(map[string]any)
		if !ok {
			continue
		}
		mounts := asSlice(cm["volumeMounts"])
		cm["volumeMounts"] = append(mounts, map[string]any{"name": "ui-tls", "mountPath": "/etc/nginx/ssl", "readOnly": true})
		break
	}
	tpl["spec"] = ps
}
