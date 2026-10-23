package controller

import (
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

var _ = Describe("Reconcile pacing", func() {
	It("does not reconcile a Ready object again because of its own status write", func() {
		ns := newNamespace("pacing")
		llm := &unifaiv1.UnifaiLLM{ObjectMeta: metav1.ObjectMeta{Name: "llm", Namespace: ns}, Spec: unifaiv1.UnifaiLLMSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "pacing-" + ns}, Type: "openai_compatible",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"model_name": "m", "base_url": "http://llm:8000/v1"})}}}
		Expect(k8sClient.Create(ctx, llm)).To(Succeed())
		Eventually(phaseOf(llm), 30*time.Second, 200*time.Millisecond).Should(Equal("Ready"))
		time.Sleep(time.Second) // the reconcile that made it Ready has ended
		Expect(k8sClient.Get(ctx, client.ObjectKeyFromObject(llm), llm)).To(Succeed())
		rv := llm.ResourceVersion
		Consistently(func() string {
			_ = k8sClient.Get(ctx, client.ObjectKeyFromObject(llm), llm)
			return llm.ResourceVersion
		}, 5*time.Second, 500*time.Millisecond).Should(Equal(rv), "the object keeps being rewritten (each write was a reconcile calling UnifAI)")
	})
})
