package controller

import (
	"context"
	"encoding/json"
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

func raw(v any) *runtime.RawExtension {
	b, _ := json.Marshal(v)
	return &runtime.RawExtension{Raw: b}
}

func newNamespace(name string) string {
	ns := &corev1.Namespace{ObjectMeta: metav1.ObjectMeta{GenerateName: name + "-"}}
	Expect(k8sClient.Create(ctx, ns)).To(Succeed())
	return ns.Name
}

func phaseOf(obj unifaiv1.Object) func() string {
	return func() string {
		if err := k8sClient.Get(ctx, client.ObjectKeyFromObject(obj), obj); err != nil {
			return "get: " + err.Error()
		}
		if obj.GetObjectStatus().Phase == "Error" {
			GinkgoWriter.Printf("%s %s: %s\n", obj.GetObjectKind().GroupVersionKind().Kind, obj.GetName(), obj.GetObjectStatus().Message)
		}
		return obj.GetObjectStatus().Phase
	}
}

var _ = Describe("UnifAI object controllers", func() {
	const timeout, interval = 20 * time.Second, 200 * time.Millisecond

	It("creates an LLM with a secret, resolves references and deletes it", func() {
		ns := newNamespace("llm")
		Expect(k8sClient.Create(ctx, &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "keys", Namespace: ns},
			StringData: map[string]string{"openai": "sk-test"}})).To(Succeed())
		llm := &unifaiv1.UnifaiLLM{ObjectMeta: metav1.ObjectMeta{Name: "gpt", Namespace: ns}, Spec: unifaiv1.UnifaiLLMSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "gpt-" + ns}, Type: "openai",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"model_name": "m", "base_url": "https://api.example.com/v1"}),
				SecretRefs: []unifaiv1.SecretRef{{Path: "api_key", SecretKeyRef: unifaiv1.SecretKeySelector{Name: "keys", Key: "openai"}}}},
		}}
		// The agent is created first: it waits for the LLM.
		agent := &unifaiv1.UnifaiAgent{ObjectMeta: metav1.ObjectMeta{Name: "helper", Namespace: ns}, Spec: unifaiv1.UnifaiAgentSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "helper-" + ns}, Type: "custom_agent_node",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"llm": "$ref:llm/gpt-" + ns, "system_message": "hi"})},
		}}
		Expect(k8sClient.Create(ctx, agent)).To(Succeed())
		Eventually(func() string { _ = k8sClient.Get(ctx, client.ObjectKeyFromObject(agent), agent); return agent.Status.Message },
			timeout, interval).Should(ContainSubstring("not found in UnifAI"))
		Expect(k8sClient.Create(ctx, llm)).To(Succeed())
		Eventually(phaseOf(llm), timeout, interval).Should(Equal("Ready"))
		Expect(llm.Status.RID).NotTo(BeEmpty())
		stored := mas.resourceByName("llms", "gpt-"+ns)
		Expect(stored["cfg_dict"]).To(HaveKeyWithValue("api_key", "sk-test"))
		Expect(stored["cfg_dict"]).To(HaveKeyWithValue("type", "openai"))
		Eventually(phaseOf(agent), timeout, interval).Should(Equal("Ready"))
		Expect(mas.resourceByName("nodes", "helper-"+ns)["cfg_dict"]).To(HaveKeyWithValue("llm", "$ref:"+llm.Status.RID))

		By("updating the config in place")
		Expect(k8sClient.Get(ctx, client.ObjectKeyFromObject(llm), llm)).To(Succeed())
		llm.Spec.Config = raw(map[string]any{"model_name": "m2", "base_url": "https://api.example.com/v1"})
		Expect(k8sClient.Update(ctx, llm)).To(Succeed())
		Eventually(func() any { return mas.resourceByName("llms", "gpt-" + ns)["cfg_dict"].(map[string]any)["model_name"] },
			timeout, interval).Should(Equal("m2"))

		By("refusing to delete a referenced LLM until the agent is gone")
		Expect(k8sClient.Delete(ctx, llm)).To(Succeed())
		Eventually(phaseOf(llm), timeout, interval).Should(Equal("Deleting"))
		Expect(k8sClient.Delete(ctx, agent)).To(Succeed())
		Eventually(func() bool { return apierrors.IsNotFound(k8sClient.Get(ctx, client.ObjectKeyFromObject(llm), llm)) },
			40*time.Second, interval).Should(BeTrue())
		Expect(mas.resourceByName("llms", "gpt-"+ns)).To(BeNil())
	})

	It("marks invalid specs as permanent errors", func() {
		ns := newNamespace("invalid")
		bad := &unifaiv1.UnifaiLLM{ObjectMeta: metav1.ObjectMeta{Name: "bad", Namespace: ns}, Spec: unifaiv1.UnifaiLLMSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "bad-" + ns}, Type: "openai",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"model_name": "m", "base_url": "nope"})},
		}}
		Expect(k8sClient.Create(ctx, bad)).To(Succeed())
		Eventually(phaseOf(bad), timeout, interval).Should(Equal("Error"))
		Expect(bad.Status.Message).To(ContainSubstring("Schema validation failed"))
		Expect(mas.resourceByName("llms", "bad-"+ns)).To(BeNil())
	})

	It("does not take over an existing UnifAI object without the adopt annotation", func() {
		ns := newNamespace("adopt")
		mas.mu.Lock()
		mas.resources["preexisting"] = map[string]any{"rid": "preexisting", "name": "ui-" + ns, "type": "web_fetch", "category": "tools", "cfg_dict": map[string]any{}}
		mas.mu.Unlock()
		tool := &unifaiv1.UnifaiTool{ObjectMeta: metav1.ObjectMeta{Name: "fetch", Namespace: ns}, Spec: unifaiv1.UnifaiToolSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "ui-" + ns}, Type: "web_fetch"}}
		Expect(k8sClient.Create(ctx, tool)).To(Succeed())
		Eventually(phaseOf(tool), timeout, interval).Should(Equal("Error"))
		Expect(tool.Status.Message).To(ContainSubstring(unifaiv1.AdoptAnnotation))
		tool.Annotations = map[string]string{unifaiv1.AdoptAnnotation: "true"}
		Expect(k8sClient.Update(ctx, tool)).To(Succeed())
		Eventually(phaseOf(tool), timeout, interval).Should(Equal("Ready"))
		Expect(tool.Status.RID).To(Equal("preexisting"))
	})

	It("deploys a workflow with library nodes, a schedule and a chat", func() {
		ns := newNamespace("wf")
		llm := &unifaiv1.UnifaiLLM{ObjectMeta: metav1.ObjectMeta{Name: "llm", Namespace: ns}, Spec: unifaiv1.UnifaiLLMSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "llm-" + ns}, Type: "openai_compatible",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"model_name": "m", "base_url": "http://llm:8000/v1"})}}}
		agent := &unifaiv1.UnifaiAgent{ObjectMeta: metav1.ObjectMeta{Name: "agent", Namespace: ns}, Spec: unifaiv1.UnifaiAgentSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "agent-" + ns}, Type: "custom_agent_node",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"llm": "$ref:llm/llm-" + ns})}}}
		wf := &unifaiv1.UnifaiWorkflow{ObjectMeta: metav1.ObjectMeta{Name: "wf", Namespace: ns}, Spec: unifaiv1.UnifaiWorkflowSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "wf-" + ns},
			Blueprint: *raw(map[string]any{
				"nodes": []any{map[string]any{"rid": "user_question", "type": "user_question_node", "config": map[string]any{"type": "user_question_node"}},
					map[string]any{"rid": "$ref:agent/agent-" + ns}},
				"plan": []any{map[string]any{"uid": "ask", "node": "user_question"}, map[string]any{"uid": "a", "node": "$rid:agent/agent-" + ns, "after": "ask"}},
			})}}
		sch := &unifaiv1.UnifaiSchedule{ObjectMeta: metav1.ObjectMeta{Name: "every", Namespace: ns}, Spec: unifaiv1.UnifaiScheduleSpec{
			Workflow: "wf-" + ns, Inputs: map[string]string{"user_prompt": "hello"}, Schedule: unifaiv1.ScheduleDefinition{Interval: "PT30M"}}}
		chat := &unifaiv1.UnifaiChat{ObjectMeta: metav1.ObjectMeta{Name: "smoke", Namespace: ns}, Spec: unifaiv1.UnifaiChatSpec{
			Workflow: "wf-" + ns, Prompt: "ping"}}
		for _, o := range []client.Object{chat, sch, wf, agent, llm} { // reverse dependency order on purpose
			Expect(k8sClient.Create(ctx, o)).To(Succeed())
		}
		Eventually(phaseOf(wf), timeout, interval).Should(Equal("Ready"))
		Eventually(phaseOf(agent), timeout, interval).Should(Equal("Ready"))
		mas.mu.Lock()
		spec := mas.blueprints[wf.Status.BlueprintID]["spec"].(map[string]any)
		mas.mu.Unlock()
		node := spec["nodes"].([]any)[1].(map[string]any)
		Expect(node["rid"]).To(Equal("$ref:" + agent.Status.RID))
		Expect(node["config"]).To(HaveKeyWithValue("type", "custom_agent_node")) // expanded from the library
		Expect(spec["plan"].([]any)[1].(map[string]any)["node"]).To(Equal(agent.Status.RID))
		Expect(spec["name"]).To(Equal("wf-" + ns))

		Eventually(phaseOf(sch), timeout, interval).Should(Equal("Ready"))
		Expect(sch.Status.ScheduleID).NotTo(BeEmpty())
		Eventually(phaseOf(chat), timeout, interval).Should(Equal("Completed"))
		Expect(chat.Status.Result).To(ContainSubstring("pong"))

		By("suspending the schedule")
		sch.Spec.Suspend = true
		Expect(k8sClient.Update(ctx, sch)).To(Succeed())
		Eventually(phaseOf(sch), timeout, interval).Should(Equal("Suspended"))
		mas.mu.Lock()
		Expect(mas.schedules[sch.Status.ScheduleID]["schedule"]).To(HaveKeyWithValue("enabled", false))
		mas.mu.Unlock()
	})

	It("ingests documents, re-ingests a changed one and removes them on delete", func() {
		ns := newNamespace("rag")
		rag := &unifaiv1.UnifaiRAGPipeline{ObjectMeta: metav1.ObjectMeta{Name: "docs", Namespace: ns}, Spec: unifaiv1.UnifaiRAGPipelineSpec{
			Documents: []unifaiv1.RAGDocument{
				{Name: "a-" + ns + ".md", Source: unifaiv1.DocumentSource{Inline: "alpha"}},
				{Name: "b-" + ns + ".md", Source: unifaiv1.DocumentSource{Inline: "beta"}},
			}}}
		Expect(k8sClient.Create(ctx, rag)).To(Succeed())
		Eventually(phaseOf(rag), 60*time.Second, interval).Should(Equal("Ready"))
		Expect(mas.ragSourceNames()).To(HaveKey("a-" + ns + ".md"))
		before := mas.ragSourceNames()["a-"+ns+".md"]

		By("changing one document")
		rag.Spec.Documents[0].Source.Inline = "alpha v2"
		Expect(k8sClient.Update(ctx, rag)).To(Succeed())
		Eventually(func() string { return mas.ragSourceNames()["a-"+ns+".md"] }, 60*time.Second, interval).ShouldNot(Equal(before))
		Eventually(phaseOf(rag), 60*time.Second, interval).Should(Equal("Ready"))
		Expect(rag.Status.Message).To(Equal("2 document(s) ingested"))

		By("deleting the resource")
		Expect(k8sClient.Delete(ctx, rag)).To(Succeed())
		Eventually(func() map[string]string { return mas.ragSourceNames() }, 30*time.Second, interval).ShouldNot(HaveKey("b-" + ns + ".md"))
	})

	It("waits for the namespace UnifaiStack to be Ready", func() {
		ns := newNamespace("gate")
		st := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: "unifai", Namespace: ns}, Spec: unifaiv1.UnifaiStackSpec{
			Identity: unifaiv1.IdentitySpec{External: &unifaiv1.ExternalOIDCSpec{URL: "https://kc", ClientSecret: unifaiv1.SecretKeySelector{Name: "s", Key: "k"}}}}}
		Expect(k8sClient.Create(ctx, st)).To(Succeed())
		cond := &unifaiv1.UnifaiCondition{ObjectMeta: metav1.ObjectMeta{Name: "direct", Namespace: ns}, Spec: unifaiv1.UnifaiConditionSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "direct-" + ns}, Type: "router_direct"}}
		Expect(k8sClient.Create(ctx, cond)).To(Succeed())
		Eventually(func() string { _ = k8sClient.Get(ctx, client.ObjectKeyFromObject(cond), cond); return cond.Status.Message },
			timeout, interval).Should(ContainSubstring("waiting for UnifaiStack"))
		Expect(cond.Status.Phase).To(Equal("Pending"))
		meta.SetStatusCondition(&st.Status.Conditions, metav1.Condition{Type: "Ready", Status: metav1.ConditionTrue, Reason: "Ready"})
		Expect(k8sClient.Status().Update(ctx, st)).To(Succeed())
		Eventually(phaseOf(cond), 30*time.Second, interval).Should(Equal("Ready"))
	})
})

var _ = Describe("UnifaiStack API validation", func() {
	identity := unifaiv1.IdentitySpec{External: &unifaiv1.ExternalOIDCSpec{URL: "https://kc", ClientSecret: unifaiv1.SecretKeySelector{Name: "s", Key: "k"}}}

	It("allows a single stack per namespace, named unifai", func() {
		ns := newNamespace("single")
		other := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: "second", Namespace: ns}, Spec: unifaiv1.UnifaiStackSpec{Identity: identity}}
		err := k8sClient.Create(ctx, other)
		Expect(apierrors.IsInvalid(err)).To(BeTrue(), "got %v", err)
		Expect(err.Error()).To(ContainSubstring("only one UnifaiStack per namespace"))
		ok := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: "unifai", Namespace: ns}, Spec: unifaiv1.UnifaiStackSpec{Identity: identity}}
		Expect(k8sClient.Create(ctx, ok)).To(Succeed())
		Expect(ok.Spec.Profile).To(Equal("dev"))
		Expect(ok.Spec.DeletionPolicy).To(Equal("Retain"))
	})

	It("requires exactly one identity provider", func() {
		ns := newNamespace("identity")
		none := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: "unifai", Namespace: ns}}
		Expect(apierrors.IsInvalid(k8sClient.Create(context.Background(), none))).To(BeTrue())
		both := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: "unifai", Namespace: ns}, Spec: unifaiv1.UnifaiStackSpec{
			Identity: unifaiv1.IdentitySpec{External: identity.External, Keycloak: &unifaiv1.ManagedKeycloakSpec{}}}}
		Expect(apierrors.IsInvalid(k8sClient.Create(ctx, both))).To(BeTrue())
	})

	It("rejects a document with two sources and a chat spec change", func() {
		ns := newNamespace("cel")
		rag := &unifaiv1.UnifaiRAGPipeline{ObjectMeta: metav1.ObjectMeta{Name: "docs", Namespace: ns}, Spec: unifaiv1.UnifaiRAGPipelineSpec{
			Documents: []unifaiv1.RAGDocument{{Name: "a.md", Source: unifaiv1.DocumentSource{Inline: "x", URL: "http://x"}}}}}
		Expect(apierrors.IsInvalid(k8sClient.Create(ctx, rag))).To(BeTrue())
		chat := &unifaiv1.UnifaiChat{ObjectMeta: metav1.ObjectMeta{Name: "c", Namespace: ns}, Spec: unifaiv1.UnifaiChatSpec{Workflow: "none", Prompt: "a"}}
		Expect(k8sClient.Create(ctx, chat)).To(Succeed())
		Expect(k8sClient.Get(ctx, types.NamespacedName{Namespace: ns, Name: "c"}, chat)).To(Succeed())
		chat.Spec.Prompt = "b"
		Eventually(func() error {
			_ = k8sClient.Get(ctx, types.NamespacedName{Namespace: ns, Name: "c"}, chat)
			chat.Spec.Prompt = "b"
			return k8sClient.Update(ctx, chat)
		}, 10*time.Second, 200*time.Millisecond).Should(Satisfy(apierrors.IsInvalid))
	})
})
