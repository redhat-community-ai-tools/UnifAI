package controller

import (
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
)

var _ = Describe("Metrics scraper token", func() {
	It("waits for the scraper ServiceAccount, then creates its token Secret once", func() {
		ns := newNamespace("metrics")
		m := &MetricsToken{Client: k8sClient, Reader: k8sClient, Namespace: ns}
		ok, err := m.ensure(ctx)
		Expect(err).NotTo(HaveOccurred())
		Expect(ok).To(BeFalse())
		key := types.NamespacedName{Namespace: ns, Name: MetricsTokenSecret}
		Expect(k8sClient.Get(ctx, key, &corev1.Secret{})).NotTo(Succeed())

		Expect(k8sClient.Create(ctx, &corev1.ServiceAccount{ObjectMeta: metav1.ObjectMeta{Name: MetricsScraper, Namespace: ns}})).To(Succeed())
		ok, err = m.ensure(ctx)
		Expect(err).NotTo(HaveOccurred())
		Expect(ok).To(BeTrue())
		secret := &corev1.Secret{}
		Expect(k8sClient.Get(ctx, key, secret)).To(Succeed())
		Expect(secret.Type).To(Equal(corev1.SecretTypeServiceAccountToken))
		Expect(secret.Annotations).To(HaveKeyWithValue(corev1.ServiceAccountNameKey, MetricsScraper))

		ok, err = m.ensure(ctx)
		Expect(err).NotTo(HaveOccurred())
		Expect(ok).To(BeTrue())
	})
})
