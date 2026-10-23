package stack

import (
	"strings"
	"testing"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/labels"
	"sigs.k8s.io/yaml"
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
