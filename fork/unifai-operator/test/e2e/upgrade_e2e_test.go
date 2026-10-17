//go:build e2e

package e2e

import (
	"crypto/tls"
	"net/http"
	"os"
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// newNamespace creates a namespace for one test and deletes it at the end (unless E2E_KEEP).
func newNamespace(t *testing.T, suffix string) string {
	t.Helper()
	name := ns + "-" + suffix
	must(t, c.Create(ctx, &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: name}}))
	t.Cleanup(func() {
		if os.Getenv("E2E_KEEP") == "" {
			_ = c.Delete(ctx, &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{Name: name}})
		}
	})
	return name
}

func waitStackReady(t *testing.T, st *unifaiv1.UnifaiStack, timeout time.Duration, extra func() bool) {
	t.Helper()
	eventually(t, "stack "+st.Namespace+" Ready", timeout, func() (bool, string) {
		if err := c.Get(ctx, client.ObjectKeyFromObject(st), st); err != nil {
			return false, err.Error()
		}
		ok := meta.IsStatusConditionTrue(st.Status.Conditions, "Ready") && (extra == nil || extra())
		return ok, st.Status.Phase + " (operator " + st.Status.OperatorVersion + "): " + st.Status.Message
	})
}

func deleteStack(t *testing.T, st *unifaiv1.UnifaiStack) {
	t.Helper()
	must(t, c.Delete(ctx, st))
	eventually(t, "stack "+st.Namespace+" deleted", 15*time.Minute, func() (bool, string) {
		err := c.Get(ctx, client.ObjectKeyFromObject(st), st)
		return apierrors.IsNotFound(err), st.Status.Phase + " " + st.Status.Message
	})
}

// TestUpgrade deploys a stack with the default (OLM) instance, hands it to the instance under test, and checks the
// candidate takes it over without losing data: same encryption key, same UnifAI objects, a working chat.
func TestUpgrade(t *testing.T) {
	if os.Getenv("E2E_UPGRADE") == "" || instance == "" {
		t.Skip("E2E_UPGRADE=1 with E2E_OPERATOR_INSTANCE (canary) required")
	}
	timeout, _ := time.ParseDuration(env("E2E_TIMEOUT", "30m"))
	n := newNamespace(t, "up")
	must(t, c.Create(ctx, &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "e2e-oidc", Namespace: n},
		StringData: map[string]string{"client-secret": "not-used-by-the-e2e"}}))
	st := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: unifaiv1.StackName, Namespace: n},
		Spec: stackSpec(unifaiv1.IdentitySpec{External: &unifaiv1.ExternalOIDCSpec{URL: "https://keycloak.example.invalid",
			ClientSecret: unifaiv1.SecretKeySelector{Name: "e2e-oidc", Key: "client-secret"}}})}
	must(t, c.Create(ctx, st)) // default instance (production operator)
	waitStackReady(t, st, timeout, nil)
	from := st.Status.OperatorVersion
	t.Logf("deployed by operator %s", from)

	deployMockLLM(t, n)
	llm := &unifaiv1.UnifaiLLM{ObjectMeta: metav1.ObjectMeta{Name: "up-llm", Namespace: n}, Spec: unifaiv1.UnifaiLLMSpec{
		CommonSpec: unifaiv1.CommonSpec{UnifaiName: "up-llm"}, Type: "openai_compatible",
		ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"model_name": "mock-model", "base_url": "http://e2e-llm:8000/v1", "api_key": "EMPTY"})}}}
	must(t, c.Create(ctx, llm))
	waitPhase(t, llm, "Ready", 5*time.Minute)
	rid := llm.Status.RID
	gen := &corev1.Secret{}
	must(t, c.Get(ctx, client.ObjectKey{Namespace: n, Name: "unifai-generated"}, gen))
	key := string(gen.Data["CREDENTIAL_ENCRYPTION_KEY"])

	By := func(s string) { t.Log(s) }
	By("handing the stack and its objects to the instance under test")
	for _, o := range []client.Object{st, llm} {
		must(t, c.Get(ctx, client.ObjectKeyFromObject(o), o))
		label(o, instance)
		must(t, c.Update(ctx, o))
	}
	want := os.Getenv("E2E_CANDIDATE_VERSION")
	waitStackReady(t, st, timeout, func() bool { return want == "" || st.Status.OperatorVersion == want })
	t.Logf("upgraded from operator %s to %s", from, st.Status.OperatorVersion)

	must(t, c.Get(ctx, client.ObjectKey{Namespace: n, Name: "unifai-generated"}, gen))
	if string(gen.Data["CREDENTIAL_ENCRYPTION_KEY"]) != key {
		t.Fatalf("the encryption key changed during the upgrade")
	}
	eventually(t, "LLM reconciled by the candidate", 5*time.Minute, func() (bool, string) {
		must(t, c.Get(ctx, client.ObjectKeyFromObject(llm), llm))
		return llm.Status.Phase == "Ready" && llm.Status.LastReconciled != nil &&
			time.Since(llm.Status.LastReconciled.Time) < 2*time.Minute, llm.Status.Phase + " " + llm.Status.Message
	})
	if llm.Status.RID != rid {
		t.Errorf("LLM recreated in UnifAI: rid %s -> %s", rid, llm.Status.RID)
	}
	agent := &unifaiv1.UnifaiAgent{ObjectMeta: metav1.ObjectMeta{Name: "up-agent", Namespace: n}, Spec: unifaiv1.UnifaiAgentSpec{
		Type: "custom_agent_node", ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"llm": "$ref:llm/up-llm", "hitl_mode": "skip"})}}}
	wf := &unifaiv1.UnifaiWorkflow{ObjectMeta: metav1.ObjectMeta{Name: "up-wf", Namespace: n}, Spec: unifaiv1.UnifaiWorkflowSpec{
		Blueprint: *raw(map[string]any{
			"nodes": []any{
				map[string]any{"rid": "user_question", "name": "User Question Node", "type": "user_question_node", "config": map[string]any{"type": "user_question_node"}},
				map[string]any{"rid": "final_answer", "name": "Final Answer Node", "type": "final_answer_node", "config": map[string]any{"type": "final_answer_node"}},
				map[string]any{"rid": "$ref:agent/up-agent"}},
			"plan": []any{
				map[string]any{"uid": "ask", "node": "user_question"},
				map[string]any{"uid": "agent", "node": "$rid:agent/up-agent", "after": "ask"},
				map[string]any{"uid": "finish", "node": "final_answer", "after": "agent"}},
		})}}
	chat := &unifaiv1.UnifaiChat{ObjectMeta: metav1.ObjectMeta{Name: "up-chat", Namespace: n}, Spec: unifaiv1.UnifaiChatSpec{Workflow: "up-wf", Prompt: "ping"}}
	for _, o := range []client.Object{agent, wf} {
		create(t, o)
	}
	waitPhase(t, wf, "Ready", 5*time.Minute)
	create(t, chat)
	waitPhase(t, chat, "Completed", 5*time.Minute)
	deleteStack(t, st)
}

// TestManagedKeycloak deploys a stack with a Keycloak managed by the operator (RHBK installed in the namespace,
// realm imported) and checks it is removed with the stack. Slow: E2E_KEYCLOAK=1.
func TestManagedKeycloak(t *testing.T) {
	if os.Getenv("E2E_KEYCLOAK") == "" {
		t.Skip("E2E_KEYCLOAK=1 required")
	}
	timeout, _ := time.ParseDuration(env("E2E_TIMEOUT", "30m"))
	n := newNamespace(t, "kc")
	st := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: unifaiv1.StackName, Namespace: n},
		Spec: stackSpec(unifaiv1.IdentitySpec{Keycloak: &unifaiv1.ManagedKeycloakSpec{}})}
	create(t, st)
	waitStackReady(t, st, timeout, nil)
	hc := &http.Client{Timeout: 30 * time.Second, Transport: &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}} //nolint:gosec
	resp, err := hc.Get(st.Status.Endpoints.Keycloak + "/realms/unifai/.well-known/openid-configuration")
	if err != nil {
		t.Fatal(err)
	}
	_ = resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Errorf("realm unifai: %s", resp.Status)
	}
	deleteStack(t, st)
	sub := &unstructured.Unstructured{}
	sub.SetAPIVersion("operators.coreos.com/v1alpha1")
	sub.SetKind("Subscription")
	if err := c.Get(ctx, client.ObjectKey{Namespace: n, Name: "rhbk-operator"}, sub); !apierrors.IsNotFound(err) {
		t.Errorf("RHBK subscription left after the stack deletion (err=%v)", err)
	}
}
