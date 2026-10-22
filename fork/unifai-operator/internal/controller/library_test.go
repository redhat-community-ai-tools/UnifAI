package controller

import (
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	corev1 "k8s.io/api/core/v1"
	eventsv1 "k8s.io/api/events/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

var _ = Describe("Library kinds without a dedicated scenario", func() {
	const timeout, interval = 20 * time.Second, 200 * time.Millisecond

	gone := func(obj client.Object) func() bool {
		return func() bool { return apierrors.IsNotFound(k8sClient.Get(ctx, client.ObjectKeyFromObject(obj), obj)) }
	}

	It("saves a provider, a retriever and a sandbox in their categories and deletes them", func() {
		ns := newNamespace("library")
		Expect(k8sClient.Create(ctx, &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "mcp", Namespace: ns},
			StringData: map[string]string{"token": "t0k"}})).To(Succeed())
		provider := &unifaiv1.UnifaiProvider{ObjectMeta: metav1.ObjectMeta{Name: "mcp", Namespace: ns}, Spec: unifaiv1.UnifaiProviderSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "mcp-" + ns}, Type: "mcp_server",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"sse_endpoint": "http://mcp:8080/sse"}),
				SecretRefs: []unifaiv1.SecretRef{{Path: "headers.Authorization", SecretKeyRef: unifaiv1.SecretKeySelector{Name: "mcp", Key: "token"}}}},
		}}
		retriever := &unifaiv1.UnifaiRetriever{ObjectMeta: metav1.ObjectMeta{Name: "docs", Namespace: ns}, Spec: unifaiv1.UnifaiRetrieverSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "docs-" + ns}, Type: "docs_rag",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"top_k": 3})},
		}}
		sandbox := &unifaiv1.UnifaiSandbox{ObjectMeta: metav1.ObjectMeta{Name: "py", Namespace: ns}, Spec: unifaiv1.UnifaiSandboxSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "py-" + ns}, Type: "openshell_sandbox",
		}}
		for _, o := range []client.Object{provider, retriever, sandbox} {
			Expect(k8sClient.Create(ctx, o)).To(Succeed())
		}
		for _, c := range []struct {
			obj      unifaiv1.Object
			category string
		}{{provider, "providers"}, {retriever, "retrievers"}, {sandbox, "sandboxes"}} {
			Eventually(phaseOf(c.obj), timeout, interval).Should(Equal("Ready"))
			stored := mas.resourceByName(c.category, c.obj.GetName()+"-"+ns)
			Expect(stored).NotTo(BeNil(), "%s not saved in %s", c.obj.GetName(), c.category)
			Expect(stored["rid"]).To(Equal(c.obj.GetObjectStatus().RID))
		}
		cfg := mas.resourceByName("providers", "mcp-"+ns)["cfg_dict"].(map[string]any)
		Expect(cfg).To(HaveKeyWithValue("headers", HaveKeyWithValue("Authorization", "t0k")))
		Expect(cfg).To(HaveKeyWithValue("type", "mcp_server"))
		Expect(mas.resourceByName("retrievers", "docs-"+ns)["cfg_dict"]).To(HaveKeyWithValue("top_k", BeNumerically("==", 3)))

		By("recording the phase change as an Event")
		Eventually(func() []string {
			var list eventsv1.EventList
			_ = k8sClient.List(ctx, &list, client.InNamespace(ns))
			var out []string
			for _, e := range list.Items {
				out = append(out, e.Regarding.Kind+"/"+e.Regarding.Name+" "+e.Type+" "+e.Reason+" "+e.ReportingController)
			}
			return out
		}, timeout, interval).Should(ContainElement("UnifaiProvider/mcp Normal Ready " + EventSource))

		By("deleting them")
		for _, o := range []client.Object{provider, retriever, sandbox} {
			Expect(k8sClient.Delete(ctx, o)).To(Succeed())
			Eventually(gone(o), timeout, interval).Should(BeTrue())
		}
		Expect(mas.resourceByName("providers", "mcp-"+ns)).To(BeNil())
		Expect(mas.resourceByName("retrievers", "docs-"+ns)).To(BeNil())
		Expect(mas.resourceByName("sandboxes", "py-"+ns)).To(BeNil())
	})

	It("creates a template with secrets, recreates it on change and deletes it", func() {
		ns := newNamespace("template")
		Expect(k8sClient.Create(ctx, &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "llm", Namespace: ns},
			StringData: map[string]string{"key": "sk-tpl"}})).To(Succeed())
		tpl := &unifaiv1.UnifaiTemplate{ObjectMeta: metav1.ObjectMeta{Name: "starter", Namespace: ns}, Spec: unifaiv1.UnifaiTemplateSpec{
			Draft:        *raw(map[string]any{"name": "starter-" + ns, "llms": []any{map[string]any{"name": "m", "config": map[string]any{}}}}),
			Placeholders: raw(map[string]any{"api_key": "PLACEHOLDER_API_KEY"}),
			Metadata:     raw(map[string]any{"description": "v1"}),
			SecretRefs:   []unifaiv1.SecretRef{{Path: "secret_value", SecretKeyRef: unifaiv1.SecretKeySelector{Name: "llm", Key: "key"}}},
		}}
		Expect(k8sClient.Create(ctx, tpl)).To(Succeed())
		Eventually(phaseOf(tpl), timeout, interval).Should(Equal("Ready"))
		first := tpl.Status.TemplateID
		Expect(first).NotTo(BeEmpty())
		mas.mu.Lock()
		body := mas.templates[first]
		mas.mu.Unlock()
		Expect(body["draft"]).To(HaveKeyWithValue("secret_value", "sk-tpl"))
		Expect(body["placeholders"]).To(HaveKeyWithValue("categories", BeEmpty())) // defaulted
		Expect(body["metadata"]).To(HaveKeyWithValue("description", "v1"))

		By("recreating it when the spec changes (UnifAI has no template update)")
		Expect(k8sClient.Get(ctx, client.ObjectKeyFromObject(tpl), tpl)).To(Succeed())
		tpl.Spec.Metadata = raw(map[string]any{"description": "v2"})
		Expect(k8sClient.Update(ctx, tpl)).To(Succeed())
		Eventually(func() string {
			_ = k8sClient.Get(ctx, client.ObjectKeyFromObject(tpl), tpl)
			return tpl.Status.TemplateID
		}, timeout, interval).ShouldNot(Equal(first))
		mas.mu.Lock()
		Expect(mas.templates).NotTo(HaveKey(first))
		Expect(mas.templates[tpl.Status.TemplateID]["metadata"]).To(HaveKeyWithValue("description", "v2"))
		mas.mu.Unlock()

		By("deleting it")
		id := tpl.Status.TemplateID
		Expect(k8sClient.Delete(ctx, tpl)).To(Succeed())
		Eventually(gone(tpl), timeout, interval).Should(BeTrue())
		mas.mu.Lock()
		Expect(mas.templates).NotTo(HaveKey(id))
		mas.mu.Unlock()
	})
})
