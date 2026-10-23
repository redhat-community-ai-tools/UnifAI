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

// testSecret is a secret value that must never appear in rendered manifests.
const testSecret = "s3cr3t"

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
	p.OIDCURL, p.OIDCRealm, p.OIDCClientID, p.OIDCClientSecret = "https://kc.example.com", "unifai", "unifai", testSecret
	on := renderAll(t, p)
	for _, rel := range []string{"unifai-multiagent-be", "unifai-multiagent-temporal-worker"} {
		for _, want := range []string{"IDENTITY_FORWARDING_ENABLED", "https://kc.example.com", "KEYCLOAK_REALM", "CLIENT_ID"} {
			if !strings.Contains(on[rel], want) {
				t.Errorf("%s lacks %s", rel, want)
			}
		}
		if strings.Contains(on[rel], testSecret) {
			t.Errorf("%s: the client secret must come from multiagent-be-secret, not plain env", rel)
		}
	}
	if multiagentSecret(p)["CLIENT_SECRET"] != testSecret {
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

func TestRAGSettings(t *testing.T) {
	off := renderAll(t, testPlan(t, nil))
	for _, rel := range []string{"unifai-rag-server", "unifai-rag-celery"} {
		for _, absent := range []string{"QDRANT_HYBRID_ENABLED", "RAG_SHARED_PUBLISHERS", "OIDC_ISSUER_URL", "confluence_queue"} {
			if strings.Contains(off[rel], absent) {
				t.Errorf("%s: %s must not be rendered by default (it would roll existing stacks)", rel, absent)
			}
		}
	}
	if _, ok := ragSecret(map[string]string{})["CONFLUENCE_TOKEN"]; ok {
		t.Errorf("unifai-rag-secrets must not gain Confluence keys when Confluence is not configured")
	}

	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) {
		s.RAG.Hybrid = true
		s.RAG.SharedPublishers = []string{"admin"}
		s.RAG.Confluence = &unifaiv1.ConfluenceSpec{Token: unifaiv1.SecretKeySelector{Name: "conf", Key: "token"}}
	})
	p.OIDCURL, p.OIDCRealm = "https://kc.example.com/", "zuno"
	on := renderAll(t, p)
	for _, rel := range []string{"unifai-rag-server", "unifai-rag-celery"} {
		for _, want := range []string{"QDRANT_HYBRID_ENABLED", `["admin"]`, "https://kc.example.com/realms/zuno", "confluence_queue"} {
			if !strings.Contains(on[rel], want) {
				t.Errorf("%s lacks %s", rel, want)
			}
		}
	}
	data := ragSecret(map[string]string{"CONFLUENCE_USERNAME": "u", "CONFLUENCE_TOKEN": "tok"})
	if data["CONFLUENCE_TOKEN"] != "tok" || data["CONFLUENCE_USERNAME"] != "u" {
		t.Errorf("unifai-rag-secrets lacks the Confluence credentials: %v", data)
	}
	if strings.Contains(on["unifai-rag-server"], "tok") && strings.Contains(on["unifai-rag-server"], "CONFLUENCE_TOKEN") {
		t.Errorf("the Confluence token must come from unifai-rag-secrets, not plain env")
	}
}

func TestOpenTelemetry(t *testing.T) {
	traced := []string{"unifai-rag-server", "unifai-rag-celery", "unifai-multiagent-be", "unifai-multiagent-temporal-worker", "unifai-backend"}
	off := renderAll(t, testPlan(t, nil))
	for _, rel := range traced {
		if strings.Contains(off[rel], "OTEL_EXPORTER_OTLP_ENDPOINT") || strings.Contains(off[rel], "UNIFAI_OTEL_ENABLED") {
			t.Errorf("%s: OpenTelemetry must be off by default", rel)
		}
	}
	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) {
		s.OpenTelemetry = &unifaiv1.OpenTelemetrySpec{Endpoint: "http://collector.monitoring.svc:4318", Protocol: "http/protobuf",
			Sampler: "parentbased_traceidratio", SamplerArg: "0.25", DisableMetrics: true,
			ResourceAttributes: map[string]string{"deployment.environment": "demo"}}
	})
	on := renderAll(t, p)
	for _, rel := range traced {
		for _, want := range []string{"UNIFAI_OTEL_ENABLED", "http://collector.monitoring.svc:4318", "http/protobuf",
			"parentbased_traceidratio", "0.25", "OTEL_METRICS_EXPORTER",
			"deployment.environment=demo,k8s.namespace.name=team-a"} {
			if !strings.Contains(on[rel], want) {
				t.Errorf("%s lacks %s", rel, want)
			}
		}
		if !strings.Contains(on[rel], rel) {
			t.Errorf("%s: OTEL_SERVICE_NAME should be the release name", rel)
		}
	}
	for _, rel := range []string{"unifai-identity", "unifai-ui", "unifai-mongodb"} {
		if strings.Contains(on[rel], "OTEL_EXPORTER_OTLP_ENDPOINT") {
			t.Errorf("%s is not traced", rel)
		}
	}
	// Only the traced releases change: the others keep their hash (no needless Helm upgrade).
	pOff := testPlan(t, nil)
	for _, r := range Releases {
		if !r.IsEnabled(p) {
			continue
		}
		a, err := Render(pOff, r)
		if err != nil {
			t.Fatal(err)
		}
		b, err := Render(p, r)
		if err != nil {
			t.Fatal(err)
		}
		if (a.Hash != b.Hash) != r.Traced {
			t.Errorf("%s: hash changed=%v, traced=%v", r.Name, a.Hash != b.Hash, r.Traced)
		}
	}
}

func TestInternalAuthAndExtraEnv(t *testing.T) {
	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) {
		s.ExtraEnv = map[string][]corev1.EnvVar{
			"identity": {{Name: "DIRECTORY_PROVIDER", Value: "oidc-claims"},
				{Name: "DIRECTORY_OIDC_ISSUER", ValueFrom: &corev1.EnvVarSource{ConfigMapKeyRef: &corev1.ConfigMapKeySelector{
					LocalObjectReference: corev1.LocalObjectReference{Name: "directory"}, Key: "issuer"}}}},
			"backend": {{Name: "RAG_URL", Value: "http://override:1"}},
		}
	})
	p.Secrets[KeyInternalAuth] = testSecret
	out := renderAll(t, p)
	ref := "name: " + KeyInternalAuth + "\n          valueFrom:\n            secretKeyRef:\n              key: " + KeyInternalAuth +
		"\n              name: " + InternalAuthSecret
	for _, rel := range []string{"unifai-identity", "unifai-multiagent-be", "unifai-multiagent-temporal-worker",
		"unifai-rag-server", "unifai-rag-celery", "unifai-backend"} {
		if !strings.Contains(out[rel], ref) {
			t.Errorf("%s: no INTERNAL_AUTH_SECRET secretKeyRef", rel)
		}
	}
	for rel, m := range out {
		if strings.Contains(m, testSecret) {
			t.Errorf("%s: the internal secret must not be rendered in clear", rel)
		}
	}
	for _, rel := range []string{"unifai-ui", "unifai-mongodb"} {
		if strings.Contains(out[rel], KeyInternalAuth) {
			t.Errorf("%s must not get INTERNAL_AUTH_SECRET", rel)
		}
	}
	if !strings.Contains(out["unifai-identity"], "value: oidc-claims") || !strings.Contains(out["unifai-identity"], "DIRECTORY_OIDC_ISSUER") {
		t.Errorf("identity lacks its extraEnv")
	}
	if strings.Contains(out["unifai-multiagent-be"], "DIRECTORY_PROVIDER") {
		t.Errorf("extraEnv of identity leaked to multiagent")
	}
	if !strings.Contains(out["unifai-backend"], "http://override:1") || strings.Count(out["unifai-backend"], "name: RAG_URL") != 1 {
		t.Errorf("backend: extraEnv must replace the chart's RAG_URL, not duplicate it")
	}
	for _, h := range []string{InternalAuthHeader, InternalSecretHeader} {
		if !strings.Contains(out["unifai-ui"], "name: "+h) {
			t.Errorf("UI route does not delete %s", h)
		}
	}
	for _, rel := range []string{"unifai-rag-server", "unifai-rag-celery", "unifai-backend"} {
		if !strings.Contains(out[rel], "value: "+IdentityServiceURL) || strings.Contains(out[rel], "value: https://"+p.IdentityHost) {
			t.Errorf("%s: IDENTITY_HOST must be the identity Service, not the public route", rel)
		}
	}
	for _, rel := range []string{"unifai-multiagent-be", "unifai-multiagent-temporal-worker"} {
		if !strings.Contains(out[rel], "DIRECTORY_SSO_URL") || !strings.Contains(out[rel], "value: "+IdentityServiceURL) {
			t.Errorf("%s: DIRECTORY_SSO_URL must be the identity Service", rel)
		}
		if !strings.Contains(out[rel], "value: https://"+p.IdentityHost) {
			t.Errorf("%s: IDENTITY_HOST must stay public (OAuth callback)", rel)
		}
	}
	var found bool
	for _, o := range BaseObjects(p) {
		if s, ok := o.(*corev1.Secret); ok && s.Name == InternalAuthSecret {
			found = s.StringData[KeyInternalAuth] == testSecret || string(s.Data[KeyInternalAuth]) == testSecret
		}
	}
	if !found {
		t.Errorf("BaseObjects lacks %s with the effective secret", InternalAuthSecret)
	}
}
