package stack

import (
	"context"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"strings"
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

func TestFillGenerated(t *testing.T) {
	data := map[string][]byte{KeyClientSecret: []byte("provided")}
	if !FillGenerated(data) {
		t.Fatal("missing keys not reported as a change")
	}
	for k := range generators {
		if len(data[k]) == 0 {
			t.Errorf("%s not generated", k)
		}
	}
	if string(data[KeyClientSecret]) != "provided" {
		t.Error("an existing value was replaced")
	}
	// Formats the UnifAI services expect.
	if b, err := base64.URLEncoding.DecodeString(string(data[KeyCredentialKey])); err != nil || len(b) != 32 {
		t.Errorf("credential key is not a Fernet key (%d bytes, %v)", len(b), err)
	}
	for _, k := range []string{KeySecretKey, KeyOAuthState, KeyInternalAuth} {
		if b, err := hex.DecodeString(string(data[k])); err != nil || len(b) != 32 {
			t.Errorf("%s is not 32 random bytes in hex", k)
		}
	}
	for _, k := range []string{KeyRedisPassword, KeyKeycloakAdminPass, KeyKeycloakDBPass} {
		if strings.Trim(string(data[k]), alnum) != "" {
			t.Errorf("%s has characters outside [A-Za-z0-9] (it ends up in URLs and shell)", k)
		}
	}
	before := string(data[KeyInternalAuth])
	if FillGenerated(data) || string(data[KeyInternalAuth]) != before {
		t.Error("a complete secret was changed")
	}
	other := map[string][]byte{}
	FillGenerated(other)
	if string(other[KeyInternalAuth]) == before {
		t.Error("two stacks got the same internal secret")
	}
}

func TestWorkloadsReady(t *testing.T) {
	two := int32(2)
	dep := func(name string, gen, observed int64, replicas, updated, available int32) *appsv1.Deployment {
		return &appsv1.Deployment{
			ObjectMeta: metav1.ObjectMeta{Namespace: "ns", Name: name, Generation: gen},
			Spec:       appsv1.DeploymentSpec{Replicas: &two},
			Status: appsv1.DeploymentStatus{ObservedGeneration: observed, Replicas: replicas,
				UpdatedReplicas: updated, AvailableReplicas: available},
		}
	}
	sts := func(name, current, update string, ready int32) *appsv1.StatefulSet {
		return &appsv1.StatefulSet{
			ObjectMeta: metav1.ObjectMeta{Namespace: "ns", Name: name, Generation: 1},
			Status: appsv1.StatefulSetStatus{ObservedGeneration: 1, ReadyReplicas: ready,
				CurrentRevision: current, UpdateRevision: update},
		}
	}
	c := fake.NewClientBuilder().WithObjects(
		dep("ready", 2, 2, 2, 2, 2),
		dep("rolling", 2, 2, 3, 2, 2), // an old pod remains
		dep("stale", 3, 2, 2, 2, 2),   // new generation not observed yet
		sts("db", "r1", "r1", 1),
		sts("db-upgrading", "r1", "r2", 1),
	).Build()
	objs := func(kind string, names ...string) []ManifestObject {
		out := make([]ManifestObject, 0, len(names))
		for _, n := range names {
			out = append(out, ManifestObject{Kind: kind, Name: n})
		}
		return out
	}
	cases := []struct {
		name string
		objs []ManifestObject
		want string
	}{
		{"ready", append(objs(kindDeployment, "ready"), objs(kindStatefulSet, "db")...), ""},
		{"rolling", objs(kindDeployment, "rolling"), "deployment/rolling 2/2"},
		{"stale", objs(kindDeployment, "stale"), "deployment/stale 2/2"},
		{"missing", append(objs(kindDeployment, "nope"), objs(kindStatefulSet, "nodb")...),
			"deployment/nope missing, statefulset/nodb missing"},
		{"statefulset revision", objs(kindStatefulSet, "db-upgrading"), "statefulset/db-upgrading 1/1"},
		{"other kinds ignored", objs("ConfigMap", "anything"), ""},
	}
	for _, tc := range cases {
		got, err := WorkloadsReady(context.Background(), c, "ns", tc.objs)
		if err != nil || got != tc.want {
			t.Errorf("%s: got %q (%v), want %q", tc.name, got, err, tc.want)
		}
	}
}

func TestEmbeddingObjects(t *testing.T) {
	remote := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) { s.RAG.Embedding.Mode = modeRemote })
	if objs := EmbeddingObjects(remote); objs != nil {
		t.Fatalf("remote embedding deployed %d objects", len(objs))
	}

	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) {
		s.RAG.Embedding.Model = "BAAI/bge-small-en-v1.5"
		s.NodeSelector = map[string]string{"workload": "unifai"}
		s.Tolerations = []corev1.Toleration{{Key: "unifai", Operator: corev1.TolerationOpExists}}
	})
	objs := EmbeddingObjects(p)
	if len(objs) != 2 {
		t.Fatalf("got %d objects, want a Deployment and a Service", len(objs))
	}
	d := objs[0].(*appsv1.Deployment)
	pod := d.Spec.Template.Spec
	c := pod.Containers[0]
	if !strings.Contains(strings.Join(c.Args, " "), "--model-id BAAI/bge-small-en-v1.5") {
		t.Errorf("model not passed: %v", c.Args)
	}
	if pod.NodeSelector["workload"] != "unifai" || len(pod.Tolerations) != 1 {
		t.Error("node placement not applied")
	}
	if c.Resources.Requests.Cpu().String() != "100m" {
		t.Errorf("dev profile CPU request %s, want 100m", c.Resources.Requests.Cpu())
	}
	if d.Labels[LabelPartOf] != PartOf || d.Spec.Template.Labels["app"] != EmbeddingName {
		t.Error("labels missing")
	}
	svc := objs[1].(*corev1.Service)
	if svc.Spec.Selector["app"] != EmbeddingName || svc.Spec.Ports[0].Port != 8080 {
		t.Error("Service does not select the embedding pods on 8080")
	}

	custom := corev1.ResourceRequirements{Requests: corev1.ResourceList{corev1.ResourceCPU: resource.MustParse("3")}}
	p = testPlan(t, func(s *unifaiv1.UnifaiStackSpec) {
		s.Profile = ProfileProd
		s.Resources = map[string]corev1.ResourceRequirements{"embedding": custom}
	})
	got := EmbeddingObjects(p)[0].(*appsv1.Deployment).Spec.Template.Spec.Containers[0].Resources
	if got.Requests.Cpu().String() != "3" {
		t.Errorf("spec.resources.embedding not applied: %v", got.Requests)
	}
}

func keycloakPlan(t *testing.T) *Plan {
	t.Helper()
	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) {
		s.Identity.External = nil
		s.Identity.Keycloak = &unifaiv1.ManagedKeycloakSpec{}
		s.Identity.AdminUsers = []string{"alice", "bob"}
	})
	p.Secrets = map[string]string{KeyClientSecret: "client-s3cret", KeyKeycloakAdminPass: "admin-s3cret"}
	return p
}

func TestKeycloakRealmImport(t *testing.T) {
	ctx := context.Background()
	p := keycloakPlan(t)
	c := fake.NewClientBuilder().Build()
	k := &Keycloak{Client: c}
	if err := k.ensureRealm(ctx, p); err != nil {
		t.Fatal(err)
	}
	ri := newU(GVKRealmImport, p.Namespace, RealmImportName)
	if err := c.Get(ctx, client.ObjectKeyFromObject(ri), ri); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(ri.Object)
	for _, s := range []string{"client-s3cret", "admin-s3cret"} {
		if strings.Contains(string(raw), s) {
			t.Errorf("secret %s written in the KeycloakRealmImport (must be a placeholder)", s)
		}
	}
	realm, _, _ := unstructured.NestedMap(ri.Object, "spec", "realm")
	clients := realm["clients"].([]any)
	cl := clients[0].(map[string]any)
	if cl["secret"] != "${CLIENT_SECRET}" || cl["publicClient"] != false || cl["directAccessGrantsEnabled"] != false {
		t.Errorf("client not confidential or secret not a placeholder: %v", cl)
	}
	uris := cl["redirectUris"].([]any)
	if len(uris) != 2 || uris[0] != "https://"+p.IdentityHost+"/*" || uris[1] != "https://"+p.UIHost+"/*" {
		t.Errorf("redirect URIs %v", uris)
	}
	users := realm["users"].([]any)
	if len(users) != 2 || users[0].(map[string]any)["username"] != "alice" {
		t.Errorf("admin users %v", users)
	}
	if realm["registrationAllowed"] != false {
		t.Error("self-registration enabled")
	}

	// RHBK never re-imports an existing realm: the operator does not rewrite it either.
	p.Spec.Identity.AdminUsers = []string{"carol"}
	if err := k.ensureRealm(ctx, p); err != nil {
		t.Fatal(err)
	}
	_ = c.Get(ctx, client.ObjectKeyFromObject(ri), ri)
	users, _, _ = unstructured.NestedSlice(ri.Object, "spec", "realm", "users")
	if users[0].(map[string]any)["username"] != "alice" {
		t.Error("the realm import was rewritten")
	}
}

func TestKeycloakDeleteKeepsData(t *testing.T) {
	ctx := context.Background()
	objs := func() []client.Object {
		return []client.Object{
			newU(GVKRealmImport, "ns", RealmImportName), newU(GVKKeycloak, "ns", KeycloakName),
			newU(GVKPostgres, "ns", KeycloakDBName),
			&corev1.Secret{ObjectMeta: metav1.ObjectMeta{Namespace: "ns", Name: KeycloakDBName}},
		}
	}
	exists := func(c client.Client, o client.Object) bool {
		cp := o.DeepCopyObject().(client.Object)
		return c.Get(ctx, client.ObjectKeyFromObject(o), cp) == nil
	}
	for _, removeData := range []bool{false, true} {
		c := fake.NewClientBuilder().WithObjects(objs()...).Build()
		k := &Keycloak{Client: c}
		// Each pass deletes what remains and reports gone only once nothing was left to delete.
		gone, err := k.Delete(ctx, "ns", removeData)
		if err != nil || gone {
			t.Fatalf("removeData=%v first pass: gone=%v err=%v", removeData, gone, err)
		}
		for i := 0; i < 3 && !gone; i++ {
			if gone, err = k.Delete(ctx, "ns", removeData); err != nil {
				t.Fatal(err)
			}
		}
		if !gone {
			t.Fatalf("removeData=%v: never gone", removeData)
		}
		all := objs()
		if exists(c, all[1]) || exists(c, all[0]) {
			t.Errorf("removeData=%v: Keycloak or realm import kept", removeData)
		}
		if kept := exists(c, all[2]) && exists(c, all[3]); kept == removeData {
			t.Errorf("removeData=%v: database kept=%v", removeData, kept)
		}
	}
}
