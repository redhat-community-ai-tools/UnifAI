package controller

import (
	"sync"
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// testClock lets the specs move time forward for the sync interval.
type testClock struct {
	mu     sync.Mutex
	offset time.Duration
}

var ragClock = &testClock{}

func (c *testClock) now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return time.Now().Add(c.offset)
}

func (c *testClock) advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.offset += d
}

var _ = Describe("UnifaiRAGSource controller", func() {
	const timeout, interval = 20 * time.Second, 200 * time.Millisecond

	newSource := func(ns, space string, mutate func(*unifaiv1.UnifaiRAGSource)) *unifaiv1.UnifaiRAGSource {
		s := &unifaiv1.UnifaiRAGSource{ObjectMeta: metav1.ObjectMeta{Name: "kb", Namespace: ns}, Spec: unifaiv1.UnifaiRAGSourceSpec{
			Type:       "confluence",
			Confluence: &unifaiv1.RAGConfluenceSource{BaseURL: "https://x.atlassian.net", SpaceKey: space, RootTitle: "Procedures"},
		}}
		if mutate != nil {
			mutate(s)
		}
		return s
	}
	get := func(s *unifaiv1.UnifaiRAGSource) func() unifaiv1.UnifaiRAGSourceStatus {
		return func() unifaiv1.UnifaiRAGSourceStatus {
			var out unifaiv1.UnifaiRAGSource
			_ = k8sClient.Get(ctx, client.ObjectKeyFromObject(s), &out)
			return out.Status
		}
	}

	It("registers the source, reports its pages and resyncs only on spec change", func() {
		ns := newNamespace("ragsrc")
		s := newSource(ns, "SX1", nil)
		Expect(k8sClient.Create(ctx, s)).To(Succeed())
		Eventually(func() string { return get(s)().Phase }, timeout, interval).Should(Equal("Ready"))
		st := get(s)()
		Expect(st.SourceID).To(Equal("conf-https://x.atlassian.net-SX1-Procedures"))
		Expect(st.Pages).To(Equal(3))
		Expect(st.NextSyncTime).To(BeNil())
		Consistently(func() int { return mas.ragSyncCount(st.SourceID) }, 2*time.Second, interval).Should(Equal(1))

		Expect(k8sClient.Get(ctx, client.ObjectKeyFromObject(s), s)).To(Succeed())
		s.Spec.Confluence.ExcludeLabels = []string{"archived"}
		Expect(k8sClient.Update(ctx, s)).To(Succeed())
		Eventually(func() int { return mas.ragSyncCount(st.SourceID) }, timeout, interval).Should(Equal(2))

		Expect(k8sClient.Delete(ctx, s)).To(Succeed())
		Eventually(func() bool { return mas.hasRAGSource(st.SourceID) }, timeout, interval).Should(BeFalse())
	})

	It("resyncs when the interval has elapsed", func() {
		ns := newNamespace("ragsrc-sched")
		s := newSource(ns, "SX2", func(s *unifaiv1.UnifaiRAGSource) {
			s.Spec.SyncInterval = &metav1.Duration{Duration: 10 * time.Minute}
		})
		Expect(k8sClient.Create(ctx, s)).To(Succeed())
		Eventually(func() string { return get(s)().Phase }, timeout, interval).Should(Equal("Ready"))
		id := get(s)().SourceID
		Expect(get(s)().NextSyncTime).NotTo(BeNil())

		ragClock.advance(11 * time.Minute)
		// Poke the object so the controller reconciles now instead of at its requeue time.
		Expect(k8sClient.Get(ctx, client.ObjectKeyFromObject(s), s)).To(Succeed())
		s.Annotations = map[string]string{"poke": "1"}
		Expect(k8sClient.Update(ctx, s)).To(Succeed())
		Eventually(func() int { return mas.ragSyncCount(id) }, timeout, interval).Should(Equal(2))
	})

	It("surfaces the RAG service refusing a shared source", func() {
		ns := newNamespace("ragsrc-shared")
		s := newSource(ns, "SX3", func(s *unifaiv1.UnifaiRAGSource) {
			s.Spec.Owner, s.Spec.Visibility, s.Spec.ACLGroups = "mallory", "shared", []string{"agent_tekos"}
		})
		Expect(k8sClient.Create(ctx, s)).To(Succeed())
		Eventually(func() string { return get(s)().Phase }, timeout, interval).Should(Equal("Error"))
		Expect(get(s)().Message).To(ContainSubstring("ACCESS_DENIED"))

		ok := newSource(newNamespace("ragsrc-shared-ok"), "SX4", func(s *unifaiv1.UnifaiRAGSource) {
			s.Spec.Owner, s.Spec.Visibility, s.Spec.ACLGroups = "publisher", "shared", []string{"agent_tekos"}
		})
		Expect(k8sClient.Create(ctx, ok)).To(Succeed())
		Eventually(func() string { return get(ok)().Phase }, timeout, interval).Should(Equal("Ready"))
	})

	It("rejects a shared source without ACL groups at admission", func() {
		s := newSource(newNamespace("ragsrc-cel"), "SX5", func(s *unifaiv1.UnifaiRAGSource) { s.Spec.Visibility = "shared" })
		err := k8sClient.Create(ctx, s)
		Expect(err).To(HaveOccurred())
		Expect(err.Error()).To(ContainSubstring("at least one ACL group"))
	})
})
