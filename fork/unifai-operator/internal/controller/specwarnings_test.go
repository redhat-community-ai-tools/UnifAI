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

var _ = Describe("Spec warnings (R-304)", func() {
	It("admits an object breaking a static rule and reports it, then clears the report once fixed", func() {
		ns := newNamespace("specwarn")
		tool := &unifaiv1.UnifaiTool{ObjectMeta: metav1.ObjectMeta{Name: "t", Namespace: ns}, Spec: unifaiv1.UnifaiToolSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "t-" + ns}, Type: "web_fetch",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"type": "ssh_exec"})}}}
		Expect(k8sClient.Create(ctx, tool)).To(Succeed(), "warnings only: nothing is refused at admission yet")
		warning := func() *metav1.Condition {
			_ = k8sClient.Get(ctx, client.ObjectKeyFromObject(tool), tool)
			return meta.FindStatusCondition(tool.Status.Conditions, ConditionSpecWarnings)
		}
		Eventually(warning, 30*time.Second, 200*time.Millisecond).ShouldNot(BeNil())
		Expect(warning().Message).To(ContainSubstring("spec.config.type"))

		tool.Spec.Config = raw(map[string]any{"type": "web_fetch"})
		Expect(k8sClient.Update(ctx, tool)).To(Succeed())
		Eventually(warning, 30*time.Second, 200*time.Millisecond).Should(BeNil())
	})
})
