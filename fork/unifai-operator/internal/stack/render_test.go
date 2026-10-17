package stack

import (
	"strings"
	"testing"

	"helm.sh/helm/v3/pkg/action"
	"helm.sh/helm/v3/pkg/chartutil"
	kubefake "helm.sh/helm/v3/pkg/kube/fake"
	"helm.sh/helm/v3/pkg/registry"
	helmstorage "helm.sh/helm/v3/pkg/storage"
	"helm.sh/helm/v3/pkg/storage/driver"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

func testPlan(t *testing.T, mutate func(*unifaiv1.UnifaiStackSpec)) *Plan {
	t.Helper()
	st := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: "unifai", Namespace: "team-a"}}
	st.Spec.Identity.External = &unifaiv1.ExternalOIDCSpec{URL: "https://kc.example.com", Realm: "unifai", ClientID: "unifai"}
	st.Spec.Storage = unifaiv1.StorageSpec{ClassName: "gp3-csi", SharedClassName: "nfs"}
	if mutate != nil {
		mutate(&st.Spec)
	}
	p, err := NewPlan(st, "apps.example.com", "openshift-operators")
	if err != nil {
		t.Fatal(err)
	}
	p.Secrets = map[string]string{}
	return p
}

// renderAll renders every enabled release client-side (helm template) with the post-renderer.
func renderAll(t *testing.T, p *Plan) map[string]string {
	t.Helper()
	out := map[string]string{}
	for _, r := range Releases {
		if !r.IsEnabled(p) {
			continue
		}
		rr, err := Render(p, r)
		if err != nil {
			t.Fatalf("%s: %v", r.Name, err)
		}
		chrt, _, err := loadChart(r.Chart)
		if err != nil {
			t.Fatal(err)
		}
		cfg := &action.Configuration{
			Releases:       helmstorage.Init(driver.NewMemory()),
			KubeClient:     &kubefake.PrintingKubeClient{},
			Capabilities:   chartutil.DefaultCapabilities,
			RegistryClient: &registry.Client{},
		}
		in := action.NewInstall(cfg)
		in.ReleaseName, in.Namespace, in.DryRun, in.ClientOnly = r.Name, p.Namespace, true, true
		in.PostRenderer = &postRenderer{plan: p, rel: r}
		rel, err := in.Run(chrt, rr.Values)
		if err != nil {
			t.Fatalf("render %s: %v", r.Name, err)
		}
		out[r.Name] = rel.Manifest
	}
	return out
}

func TestRenderDevProfile(t *testing.T) {
	p := testPlan(t, nil)
	m := renderAll(t, p)
	if len(m) != 17 {
		t.Fatalf("expected 17 releases (with docling), got %d", len(m))
	}
	all := strings.Join(func() []string {
		var s []string
		for _, v := range m {
			s = append(s, v)
		}
		return s
	}(), "\n---\n")
	for _, bad := range []string{"images.paas.redhat.com", "aws-ebs", "aws-efs", "nvidia.com/gpu", "paas.redhat.com/appcode", "HorizontalPodAutoscaler"} {
		if strings.Contains(all, bad) {
			t.Errorf("rendered stack still contains %q", bad)
		}
	}
	for _, want := range []string{
		"quay.io/zuno/unifai-rag:devel", "quay.io/zuno/unifai-multiagent:devel", "quay.io/zuno/unifai-backend:devel",
		"quay.io/zuno/unifai-identity:devel", "quay.io/zuno/unifai-ui:devel", "docker.io/qdrant/qdrant:v1.16.0",
		"host: unifai-ui-team-a.apps.example.com", "host: unifai-identity-team-a.apps.example.com",
		"storageClassName: gp3-csi", "storageClassName: nfs", "https://unifai-ui-team-a.apps.example.com",
		"http://unifai-rag-server:13456", "helm.sh/resource-policy: keep",
		DoclingURL, EmbeddingURL, "docling-project/docling-serve-cpu:v1.37.0",
	} {
		if !strings.Contains(all, want) {
			t.Errorf("rendered stack lacks %q", want)
		}
	}
	// The service URLs given to the rag pods must match the rendered Service names.
	objs, _ := ParseManifest(m["unifai-docling"])
	found := false
	for _, o := range objs {
		found = found || (o.Kind == "Service" && strings.HasPrefix(DoclingURL, "http://"+o.Name+":"))
	}
	if !found {
		t.Errorf("no docling Service matches DoclingURL %s: %v", DoclingURL, objs)
	}
	if !strings.Contains(m["unifai-multiagent-be"], "replicas: 1") {
		t.Errorf("multiagent-be must have a fixed replica count in dev")
	}
	for _, rel := range []string{"unifai-qdrant", "unifai-temporal", "unifai-redis-insight", "unifai-docling"} {
		if !strings.Contains(m[rel], "type: Recreate") {
			t.Errorf("%s mounts a ReadWriteOnce volume but is not recreated", rel)
		}
	}
	if strings.Contains(m["unifai-rag-server"], "type: Recreate") {
		t.Errorf("rag-server uses a ReadWriteMany volume and should roll")
	}
	for _, rel := range []string{"unifai-ui", "unifai-identity"} {
		if !strings.Contains(m[rel], "name: X-Authenticated-User") || !strings.Contains(m[rel], "type: Delete") {
			t.Errorf("%s route does not strip the internal auth header", rel)
		}
	}
	if !strings.Contains(m["unifai-ui"], "termination: reencrypt") || strings.Contains(m["unifai-ui"], "termination: passthrough") {
		t.Errorf("UI route must be re-encrypted")
	}
	if !strings.Contains(m["unifai-ui"], "service.beta.openshift.io/serving-cert-secret-name: "+UITLSSecret) ||
		!strings.Contains(m["unifai-ui"], "mountPath: /etc/nginx/ssl") {
		t.Errorf("UI does not use the service-ca certificate")
	}
	routes := strings.Count(all, "kind: Route")
	if routes != 2 {
		t.Errorf("expected only the ui and identity routes, got %d routes", routes)
	}
	for name, man := range m {
		objs, err := ParseManifest(man)
		if err != nil {
			t.Fatal(err)
		}
		for _, o := range objs {
			if o.Kind == "Deployment" || o.Kind == "StatefulSet" {
				t.Logf("%s: %s/%s", name, o.Kind, o.Name)
			}
		}
	}
}

func TestLiveVolumesAreKept(t *testing.T) {
	p := testPlan(t, nil)
	sc := "old-class"
	p.LiveClaimTemplates = map[string]corev1.PersistentVolumeClaim{"mongodb/unifai-mongodb-volume": {
		ObjectMeta: metav1.ObjectMeta{Name: "unifai-mongodb-volume", Labels: map[string]string{"paas.redhat.com/appcode": "TAG-001"}},
		Spec: corev1.PersistentVolumeClaimSpec{StorageClassName: &sc, Resources: corev1.VolumeResourceRequirements{
			Requests: corev1.ResourceList{corev1.ResourceStorage: resource.MustParse("100G")}}}}}
	p.LiveVolumes = map[string]corev1.PersistentVolumeClaimSpec{
		"pvc/qdrant": {Resources: corev1.VolumeResourceRequirements{Requests: corev1.ResourceList{corev1.ResourceStorage: resource.MustParse("100Gi")}}},
	}
	m := renderAll(t, p)
	if !strings.Contains(m["unifai-mongodb"], "storage: 100G\n") || !strings.Contains(m["unifai-mongodb"], "storageClassName: old-class") ||
		!strings.Contains(m["unifai-mongodb"], "paas.redhat.com/appcode: TAG-001") {
		t.Errorf("live MongoDB claim template not kept:\n%s", m["unifai-mongodb"])
	}
	if !strings.Contains(m["unifai-qdrant"], "storage: 100Gi") {
		t.Errorf("live qdrant PVC size not kept")
	}
	if fresh := renderAll(t, testPlan(t, nil)); !strings.Contains(fresh["unifai-mongodb"], "storage: 10Gi") {
		t.Errorf("dev MongoDB size not applied on a new stack")
	}
}

func TestIdentityForwarding(t *testing.T) {
	off := renderAll(t, testPlan(t, nil))
	for _, rel := range []string{"unifai-multiagent-be", "unifai-multiagent-temporal-worker"} {
		if strings.Contains(off[rel], "IDENTITY_FORWARDING_ENABLED") || strings.Contains(off[rel], "KEYCLOAK_BASE_URL") {
			t.Errorf("%s: identity forwarding must be off by default", rel)
		}
	}
	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) { s.Identity.ForwardUserToken = true })
	p.OIDCURL, p.OIDCRealm, p.OIDCClientID, p.OIDCClientSecret = "https://kc.example.com", "unifai", "unifai", "s3cr3t"
	on := renderAll(t, p)
	for _, rel := range []string{"unifai-multiagent-be", "unifai-multiagent-temporal-worker"} {
		for _, want := range []string{"IDENTITY_FORWARDING_ENABLED", "https://kc.example.com", "KEYCLOAK_REALM", "CLIENT_ID"} {
			if !strings.Contains(on[rel], want) {
				t.Errorf("%s lacks %s", rel, want)
			}
		}
		if strings.Contains(on[rel], "s3cr3t") {
			t.Errorf("%s: the client secret must come from multiagent-be-secret, not plain env", rel)
		}
	}
	if multiagentSecret(p)["CLIENT_SECRET"] != "s3cr3t" {
		t.Errorf("multiagent-be-secret lacks CLIENT_SECRET")
	}
	pOff := testPlan(t, nil)
	if _, ok := multiagentSecret(pOff)["CLIENT_SECRET"]; ok {
		t.Errorf("CLIENT_SECRET must not be set when forwarding is off")
	}
}

func TestRenderOverrides(t *testing.T) {
	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) {
		s.Profile = "prod"
		s.Version = "v1.2.3"
		s.Exposure.ExposeInternal = true
		s.RAG.GPU = true
		s.RAG.Docling.Mode = "remote"
		s.RAG.Docling.URL = "http://docling.example.com"
		s.DeletionPolicy = "Delete"
		s.Images = map[string]string{"redis": "registry.example.com/redis/redis:7", "ui": "registry.example.com/ui:x"}
		s.NodeSelector = map[string]string{"workload": "unifai"}
		s.Resources = map[string]corev1.ResourceRequirements{"backend": {Requests: corev1.ResourceList{corev1.ResourceCPU: resource.MustParse("3")}}}
	})
	m := renderAll(t, p)
	if len(m) != 16 {
		t.Fatalf("expected 16 releases with a remote docling, got %d", len(m))
	}
	for rel, want := range map[string]string{
		"unifai-rag-celery":    "nvidia.com/gpu",
		"unifai-redis":         "registry.example.com/redis/redis:7",
		"unifai-ui":            "registry.example.com/ui:x",
		"unifai-rag-server":    "quay.io/zuno/unifai-rag:v1.2.3",
		"unifai-backend":       "cpu: \"3\"",
		"unifai-multiagent-be": "workload: unifai",
		"unifai-qdrant":        "kind: Route",
	} {
		if !strings.Contains(m[rel], want) {
			t.Errorf("%s lacks %q", rel, want)
		}
	}
	if !strings.Contains(m["unifai-rag-server"], "http://docling.example.com") {
		t.Errorf("rag-server not pointed at the remote docling")
	}
	if strings.Contains(m["unifai-mongodb"], "helm.sh/resource-policy: keep") {
		t.Errorf("Delete policy must not keep the MongoDB volume")
	}
}
