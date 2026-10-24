package controller

import (
	"fmt"
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/validate"
)

// refusals returns what the API server must answer for the fields a fixture breaks ("" entries: reported only).
func refusals(fields []string) []string {
	var out []string
	for _, f := range fields {
		for _, rules := range validate.Rules {
			for _, r := range rules {
				if r.Field == f && r.Refused() != "" {
					out = append(out, r.Refused())
				}
			}
		}
	}
	return out
}

var _ = Describe("Spec rules at admission", func() {
	It("refuses every invalid fixture with the rule's message and admits the valid ones", func() {
		ns := newNamespace("admission")
		for i, f := range validate.Fixtures() {
			obj := f.Obj
			obj.SetNamespace(ns)
			obj.SetName(fmt.Sprintf("fx-%d", i))
			if _, ok := obj.(*unifaiv1.UnifaiStack); ok {
				obj.SetName("unifai")
			}
			err := k8sClient.Create(ctx, obj, client.DryRunAll)
			want := refusals(f.Fields)
			if len(want) == 0 {
				Expect(err).NotTo(HaveOccurred(), f.Name)
				continue
			}
			Expect(err).To(HaveOccurred(), f.Name)
			for _, w := range want {
				Expect(err.Error()).To(ContainSubstring(w), f.Name)
			}
		}
	})

	It("keeps an object stored before a rule existed updatable while the invalid field is unchanged (ratcheting)", func() {
		ns := newNamespace("ratchet")
		crd := &unstructured.Unstructured{}
		crd.SetGroupVersionKind(schema.GroupVersionKind{Group: "apiextensions.k8s.io", Version: "v1", Kind: "CustomResourceDefinition"})
		Expect(k8sClient.Get(ctx, client.ObjectKey{Name: "unifaischedules.unifai.startx.fr"}, crd)).To(Succeed())
		versions, _, _ := unstructured.NestedSlice(crd.Object, "spec", "versions")
		original := runtime.DeepCopyJSONValue(versions).([]any)
		path := []string{"schema", "openAPIV3Schema", "properties", "spec", "properties", "schedule", "properties", "interval", "x-kubernetes-validations"}
		setVersions := func(v []any) {
			Eventually(func() error {
				if err := k8sClient.Get(ctx, client.ObjectKeyFromObject(crd), crd); err != nil {
					return err
				}
				Expect(unstructured.SetNestedSlice(crd.Object, v, "spec", "versions")).To(Succeed())
				return k8sClient.Update(ctx, crd)
			}, 10*time.Second, 200*time.Millisecond).Should(Succeed())
		}
		DeferCleanup(setVersions, original)

		By("storing a schedule with a 30s interval while the CRD has no interval rule")
		relaxed := runtime.DeepCopyJSONValue(versions).([]any)
		unstructured.RemoveNestedField(relaxed[0].(map[string]any), path...)
		setVersions(relaxed)
		sched := func(name, interval string) *unifaiv1.UnifaiSchedule {
			return &unifaiv1.UnifaiSchedule{ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: ns}, Spec: unifaiv1.UnifaiScheduleSpec{
				Workflow: "w", Inputs: map[string]string{"user_prompt": "hi"}, Suspend: true,
				Schedule: unifaiv1.ScheduleDefinition{Interval: interval}}}
		}
		old := sched("old", "PT30S")
		Eventually(func() error { return k8sClient.Create(ctx, old) }, 10*time.Second, 200*time.Millisecond).Should(Succeed())

		By("restoring the rule")
		setVersions(original)
		Eventually(func() error { return k8sClient.Create(ctx, sched("new", "PT30S"), client.DryRunAll) },
			10*time.Second, 200*time.Millisecond).Should(MatchError(ContainSubstring("interval is an ISO-8601 duration of at least PT1M")))

		By("the operator writing the status of the stored object")
		Eventually(func() string {
			_ = k8sClient.Get(ctx, client.ObjectKeyFromObject(old), old)
			if c := meta.FindStatusCondition(old.Status.Conditions, ConditionSpecWarnings); c != nil && c.Status == metav1.ConditionTrue {
				return c.Message
			}
			return ""
		}, 10*time.Second, 200*time.Millisecond).Should(ContainSubstring("at least PT1M"))

		By("changing another field of the stored object, then the invalid one")
		Eventually(func() error {
			if err := k8sClient.Get(ctx, client.ObjectKeyFromObject(old), old); err != nil {
				return err
			}
			old.Spec.Inputs["user_prompt"] = "hello"
			return k8sClient.Update(ctx, old)
		}, 10*time.Second, 200*time.Millisecond).Should(Succeed())
		Expect(k8sClient.Get(ctx, client.ObjectKeyFromObject(old), old)).To(Succeed())
		old.Spec.Schedule.Interval = "PT20S"
		Expect(k8sClient.Update(ctx, old)).To(MatchError(ContainSubstring("interval is an ISO-8601 duration of at least PT1M")))
	})
})
