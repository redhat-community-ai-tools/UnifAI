package controller

import (
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

var _ = Describe("UnifaiWorkflow display", func() {
	const timeout, interval = 30 * time.Second, 200 * time.Millisecond

	It("stays Ready on a multiagent image without the display key, and stores it once accepted", func() {
		ns := newNamespace("wfdisplay")
		mas.mu.Lock()
		mas.noDisplay = true
		mas.mu.Unlock()
		DeferCleanup(func() {
			mas.mu.Lock()
			mas.noDisplay = false
			mas.mu.Unlock()
		})
		wf := &unifaiv1.UnifaiWorkflow{ObjectMeta: metav1.ObjectMeta{Name: "wf", Namespace: ns}, Spec: unifaiv1.UnifaiWorkflowSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "wfd-" + ns},
			Display:    &unifaiv1.AgentDisplay{Agent: "demo", Title: "Demo agent"},
			Blueprint: *raw(map[string]any{
				"nodes": []any{map[string]any{"rid": "user_question", "type": "user_question_node", "config": map[string]any{"type": "user_question_node"}}},
				"plan":  []any{map[string]any{"uid": "ask", "node": "user_question"}},
			})}}
		Expect(k8sClient.Create(ctx, wf)).To(Succeed())
		Eventually(phaseOf(wf), timeout, interval).Should(Equal("Ready"))
		Expect(wf.Status.Message).To(ContainSubstring("display not stored"))
		Expect(meta.IsStatusConditionFalse(wf.Status.Conditions, conditionDisplay)).To(BeTrue())

		By("the image accepts the key: the sheet is stored at the next reconcile, without a spec change")
		mas.mu.Lock()
		mas.noDisplay = false
		mas.mu.Unlock()
		Expect(k8sClient.Get(ctx, client.ObjectKeyFromObject(wf), wf)).To(Succeed())
		wf.Annotations = map[string]string{"test/nudge": "1"} // stands for the periodic resync
		Expect(k8sClient.Update(ctx, wf)).To(Succeed())
		Eventually(func() bool {
			_ = k8sClient.Get(ctx, client.ObjectKeyFromObject(wf), wf)
			return meta.IsStatusConditionTrue(wf.Status.Conditions, conditionDisplay)
		}, timeout, interval).Should(BeTrue())
		Expect(wf.Status.Message).NotTo(ContainSubstring("display not stored"))
		mas.mu.Lock()
		defer mas.mu.Unlock()
		Expect(mas.blueprints[wf.Status.BlueprintID]["metadata"]).To(HaveKey("display"))
	})
})
