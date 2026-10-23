package stack

import (
	"strings"
	"testing"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/labels"
	"sigs.k8s.io/yaml"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// renderedPods returns the pod template labels of every rendered workload, by "<release>/<kind>/<name>".
func renderedPods(t *testing.T, p *Plan) map[string]labels.Set {
	t.Helper()
	out := map[string]labels.Set{}
	for rel, manifest := range renderAll(t, p) {
		for _, doc := range strings.Split(manifest, "\n---") {
			u := &unstructured.Unstructured{}
			if err := yaml.Unmarshal([]byte(doc), &u.Object); err != nil || u.Object == nil {
				continue
			}
			path := []string{"spec", "template", "metadata", "labels"}
			if u.GetKind() == "CronJob" {
				path = []string{"spec", "jobTemplate", "spec", "template", "metadata", "labels"}
			}
			if l, found, _ := unstructured.NestedStringMap(u.Object, path...); found {
				out[rel+"/"+u.GetKind()+"/"+u.GetName()] = l
			}
		}
	}
	return out
}

func TestInternalAPIsPolicy(t *testing.T) {
	p := testPlan(t, nil)
	stackNP, apisNP := networkPolicy(p), internalAPIsPolicy(p)
	sel := func(s *metav1.LabelSelector) labels.Selector {
		out, err := metav1.LabelSelectorAsSelector(s)
		if err != nil {
			t.Fatal(err)
		}
		return out
	}
	stackPods, apiPods := sel(&stackNP.Spec.PodSelector), sel(&apisNP.Spec.PodSelector)
	clients := sel(apisNP.Spec.Ingress[0].From[0].PodSelector)

	pods := renderedPods(t, p)
	apis := map[string]bool{}
	for name, l := range pods {
		// Every pod is covered by exactly one of the two policies (the union would undo the API restriction).
		if stackPods.Matches(l) == apiPods.Matches(l) {
			t.Errorf("%s: selected by both or neither policy (%v)", name, l)
		}
		if apiPods.Matches(l) {
			apis[l["app.kubernetes.io/name"]] = true
			if !clients.Matches(l) {
				t.Errorf("%s: an API pod that cannot call the other APIs", name)
			}
		}
	}
	for _, want := range internalAPIs {
		if !apis[want] {
			t.Errorf("no rendered pod named %s: the API policy selects nothing for it", want)
		}
	}
	// The UI and the RAG workers call the APIs without being one.
	for _, caller := range []string{"unifai-ui/Deployment/unifai-ui", "unifai-rag-celery/Deployment/unifai-rag-celery"} {
		if l, ok := pods[caller]; !ok || !clients.Matches(l) || apiPods.Matches(l) {
			t.Errorf("%s: not an API client (%v, rendered %v)", caller, l, ok)
		}
	}
	// Other pods of the namespace (models, MCP servers, tools) only reach the APIs with the opt-in label.
	if clients.Matches(labels.Set{"app": "my-mcp"}) {
		t.Error("an arbitrary pod is an API client")
	}
	optIn := sel(apisNP.Spec.Ingress[0].From[1].PodSelector)
	if !optIn.Matches(labels.Set{InternalClientLabel: "true"}) {
		t.Error("the internal-client label does not admit a pod")
	}
}

func TestNoChartNetworkPolicy(t *testing.T) {
	for rel, manifest := range renderAll(t, testPlan(t, nil)) {
		if strings.Contains(manifest, "kind: NetworkPolicy") {
			t.Errorf("%s renders a NetworkPolicy of its chart (it would open the stack to other namespaces)", rel)
		}
	}
}

func TestRAGClientsPolicy(t *testing.T) {
	if objs := BaseObjects(testPlan(t, nil)); hasObject(objs, RAGClientsPolicyName) {
		t.Error("RAG clients policy without spec.exposure.ragClients")
	}
	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) {
		s.Exposure.RAGClients = []unifaiv1.RAGClient{
			{Namespace: "zuno-ai-run", PodLabels: map[string]string{"app": "mcp-gateway"}}, {Namespace: "ragas"}}
	})
	if !hasObject(BaseObjects(p), RAGClientsPolicyName) {
		t.Fatal("no RAG clients policy")
	}
	np := ragClientsPolicy(p)
	target, _ := metav1.LabelSelectorAsSelector(&np.Spec.PodSelector)
	for name, l := range renderedPods(t, p) {
		if target.Matches(l) != strings.HasPrefix(name, "unifai-rag-server/Deployment/") {
			t.Errorf("%s: selected=%v, only the RAG server may be opened", name, target.Matches(l))
		}
	}
	from := np.Spec.Ingress[0].From
	if len(from) != 2 || from[0].NamespaceSelector.MatchLabels["kubernetes.io/metadata.name"] != "zuno-ai-run" ||
		from[0].PodSelector.MatchLabels["app"] != "mcp-gateway" || from[1].PodSelector != nil {
		t.Errorf("peers %+v", from)
	}
}

func hasObject(objs []ctrlObject, name string) bool {
	for _, o := range objs {
		if o.GetName() == name {
			return true
		}
	}
	return false
}

func TestRAGTokenReview(t *testing.T) {
	off := renderAll(t, testPlan(t, nil))
	if strings.Contains(off["unifai-rag-server"], "RAG_TOKENREVIEW_ENABLED") ||
		strings.Contains(off["unifai-rag-server"], "serviceAccountName: "+RAGServiceAccount) {
		t.Error("token review enabled by default")
	}
	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) { s.RAG.TokenReview = true })
	on := renderAll(t, p)
	rag := on["unifai-rag-server"]
	for _, want := range []string{"kind: ServiceAccount", "name: " + RAGServiceAccount, "serviceAccountName: " + RAGServiceAccount,
		"RAG_TOKENREVIEW_ENABLED"} {
		if !strings.Contains(rag, want) {
			t.Errorf("rag-server manifest without %q", want)
		}
	}
	if strings.Contains(on["unifai-rag-celery"], "serviceAccountName: "+RAGServiceAccount) || strings.Contains(on["unifai-rag-celery"], "RAG_TOKENREVIEW") {
		t.Error("the celery workers get the token review identity")
	}
	crb := RAGTokenReviewBinding(p)
	if crb.Name != "unifai-rag-auth-delegator-team-a" || crb.Namespace != "" || crb.RoleRef.Name != "system:auth-delegator" ||
		len(crb.Subjects) != 1 || crb.Subjects[0].Name != RAGServiceAccount || crb.Subjects[0].Namespace != "team-a" ||
		crb.Labels[LabelStackNamespace] != "team-a" {
		t.Errorf("binding %+v", crb)
	}
}
