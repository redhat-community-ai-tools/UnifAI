package controller

import (
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

var _ = Describe("A2A delegation refused until its contract ships", func() {
	const timeout, interval = 20 * time.Second, 200 * time.Millisecond
	a2aNode := map[string]any{"rid": "remote", "name": "Remote agent", "type": a2aNodeType,
		"config": map[string]any{"type": a2aNodeType, "base_url": "http://a2a.example:9999"}}

	It("refuses a standalone A2A agent at admission", func() {
		ns := newNamespace("a2a-agent")
		agent := &unifaiv1.UnifaiAgent{ObjectMeta: metav1.ObjectMeta{Name: "remote", Namespace: ns}, Spec: unifaiv1.UnifaiAgentSpec{
			Type: a2aNodeType, ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"base_url": "http://a2a.example:9999"})}}}
		Expect(k8sClient.Create(ctx, agent)).To(MatchError(ContainSubstring("Unsupported value")))
	})

	It("puts a workflow with an A2A node in Error", func() {
		ns := newNamespace("a2a-wf")
		wf := &unifaiv1.UnifaiWorkflow{ObjectMeta: metav1.ObjectMeta{Name: "wf", Namespace: ns}, Spec: unifaiv1.UnifaiWorkflowSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "a2a-wf-" + ns},
			Blueprint:  *raw(map[string]any{"nodes": []any{a2aNode}, "plan": []any{map[string]any{"uid": "call", "node": "remote"}}})}}
		Expect(k8sClient.Create(ctx, wf)).To(Succeed())
		Eventually(phaseOf(wf), timeout, interval).Should(Equal(PhaseError))
		Expect(wf.Status.Message).To(ContainSubstring("A2A delegation is disabled"))
		Expect(wf.Status.BlueprintID).To(BeEmpty())
	})

	It("puts a template with an A2A node in Error", func() {
		ns := newNamespace("a2a-tpl")
		tpl := &unifaiv1.UnifaiTemplate{ObjectMeta: metav1.ObjectMeta{Name: "tpl", Namespace: ns}, Spec: unifaiv1.UnifaiTemplateSpec{
			Draft: *raw(map[string]any{"name": "A2A", "agents": []any{a2aNode}})}}
		Expect(k8sClient.Create(ctx, tpl)).To(Succeed())
		Eventually(phaseOf(tpl), timeout, interval).Should(Equal(PhaseError))
		Expect(tpl.Status.Message).To(ContainSubstring("A2A delegation is disabled"))
	})
})

var _ = Describe("hasA2ANode", func() {
	It("finds an A2A node however deep the blueprint nests it, and nothing else", func() {
		Expect(hasA2ANode(map[string]any{"nodes": []any{map[string]any{"config": map[string]any{"type": a2aNodeType}}}})).To(BeTrue())
		Expect(hasA2ANode(map[string]any{"nodes": []any{map[string]any{"type": "custom_agent_node", "name": a2aNodeType}}})).To(BeFalse())
	})
})
