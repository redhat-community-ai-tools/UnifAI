//go:build e2e

package e2e

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/util/intstr"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// docSitePages is a small site: an index linking a second page.
func docSitePages() map[string]string {
	return map[string]string{
		"index.html": `<html><head><title>E2E docs</title></head><body><h1>E2E documentation</h1>
<p>The UnifAI operator keeps this site in sync as a RAG web source.</p><a href="page2.html">Second page</a></body></html>`,
		"page2.html": `<html><head><title>E2E page 2</title></head><body><h1>Second page</h1><p>Served in the cluster.</p></body></html>`,
	}
}

// deployDocSite serves docSitePages under http://e2e-docs:8080/docs/ (Deployment and Service e2e-docs).
func deployDocSite(t *testing.T, ns string) {
	t.Helper()
	labels := map[string]string{"app": "e2e-docs"}
	must(t, c.Create(ctx, &corev1.ConfigMap{ObjectMeta: metav1.ObjectMeta{Name: "e2e-docs", Namespace: ns}, Data: docSitePages()}))
	one := int32(1)
	must(t, c.Create(ctx, &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "e2e-docs", Namespace: ns}, Spec: appsv1.DeploymentSpec{
		Replicas: &one, Selector: &metav1.LabelSelector{MatchLabels: labels},
		Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{Labels: labels}, Spec: corev1.PodSpec{
			Containers: []corev1.Container{{Name: "web", Image: pythonImage,
				Command: []string{"python", "-m", "http.server", "8080", "-d", "/site"}, Ports: []corev1.ContainerPort{{ContainerPort: 8080}},
				VolumeMounts: []corev1.VolumeMount{{Name: "docs", MountPath: "/site/docs"}}}},
			Volumes: []corev1.Volume{{Name: "docs", VolumeSource: corev1.VolumeSource{ConfigMap: &corev1.ConfigMapVolumeSource{
				LocalObjectReference: corev1.LocalObjectReference{Name: "e2e-docs"}}}}},
		}}}}))
	must(t, c.Create(ctx, &corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: "e2e-docs", Namespace: ns}, Spec: corev1.ServiceSpec{
		Selector: labels, Ports: []corev1.ServicePort{{Port: 8080, TargetPort: intstr.FromInt32(8080)}}}}))
	eventually(t, "doc site ready", 5*time.Minute, func() (bool, string) {
		d := &appsv1.Deployment{}
		if err := c.Get(ctx, client.ObjectKey{Namespace: ns, Name: "e2e-docs"}, d); err != nil {
			return false, err.Error()
		}
		return d.Status.AvailableReplicas == 1, fmt.Sprintf("%d available", d.Status.AvailableReplicas)
	})
}

// waitSynced waits until the source is Ready after a sync that started after since.
func waitSynced(t *testing.T, src *unifaiv1.UnifaiRAGSource, since time.Time, timeout time.Duration) {
	t.Helper()
	eventually(t, "source "+src.Name+" synced", timeout, func() (bool, string) {
		if err := getObj(src); err != nil {
			return false, err.Error()
		}
		st := src.Status
		synced := st.LastSyncTime != nil && !st.LastSyncTime.Time.Before(since.Truncate(time.Second))
		return synced && st.Phase == "Ready", fmt.Sprintf("%s: %s (pipeline %s)", st.Phase, st.Message, st.PipelineStatus)
	})
}

// checkWebSourceRefusesPrivateHosts points a web source at a site served in the cluster: the RAG service must not
// fetch it (its host resolves to a non-public address, the SSRF guard), so the sync ends with no page.
func checkWebSourceRefusesPrivateHosts(t *testing.T, ns string) {
	deployDocSite(t, ns)
	src := &unifaiv1.UnifaiRAGSource{ObjectMeta: metav1.ObjectMeta{Name: "e2e-web-private", Namespace: ns}, Spec: unifaiv1.UnifaiRAGSourceSpec{
		Type: "web", Tags: []string{"e2e"},
		Web: &unifaiv1.RAGWebSource{URLs: []string{"http://e2e-docs:8080/docs/index.html"}, Crawl: "generic", MaxPages: 5}}}
	start := time.Now()
	create(t, src)
	waitSynced(t, src, start, 15*time.Minute)
	if src.Status.Pages != 0 {
		t.Fatalf("a web source on an in-cluster host ingested %d pages, want none (SSRF guard)", src.Status.Pages)
	}
	eventually(t, "the RAG workers log the refusal", 2*time.Minute, func() (bool, string) {
		logs := podLogs(t, ns, "unifai-rag-celery")
		return strings.Contains(logs, "e2e-docs resolves to a non-public address"), "no refusal logged yet"
	})
}

// podLogs returns the logs of the pods of the namespace whose name starts with prefix.
func podLogs(t *testing.T, ns, prefix string) string {
	t.Helper()
	var pods corev1.PodList
	must(t, c.List(ctx, &pods, client.InNamespace(ns)))
	var out strings.Builder
	for _, p := range pods.Items {
		if !strings.HasPrefix(p.Name, prefix) {
			continue
		}
		for _, ct := range p.Spec.Containers {
			b, err := kc.CoreV1().Pods(ns).GetLogs(p.Name, &corev1.PodLogOptions{Container: ct.Name}).DoRaw(ctx)
			if err == nil {
				out.Write(b)
			}
		}
	}
	return out.String()
}

// checkRedHatSource ingests one real Red Hat documentation page (needs Internet access from the cluster).
func checkRedHatSource(t *testing.T, ns string) {
	src := &unifaiv1.UnifaiRAGSource{ObjectMeta: metav1.ObjectMeta{Name: "e2e-rh", Namespace: ns}, Spec: unifaiv1.UnifaiRAGSourceSpec{
		Type: "web", Tags: []string{"product:openshift-gitops"},
		Web: &unifaiv1.RAGWebSource{URLs: []string{env("E2E_RH_URL",
			"https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.17/html-single/understanding_openshift_gitops/index")},
			Crawl: "none", MaxPages: 1}}}
	start := time.Now()
	create(t, src)
	waitSynced(t, src, start, 20*time.Minute)
	if src.Status.Pages != 1 {
		t.Fatalf("red hat page: %s, want 1 page", src.Status.Message)
	}

	must(t, getObj(src))
	src.Spec.Tags = append(src.Spec.Tags, "e2e") // a spec change queues a sync of the same page
	start = time.Now()
	must(t, c.Update(ctx, src))
	waitSynced(t, src, start, 20*time.Minute)
	if src.Status.Pages != 1 || src.Status.PagesChanged != 0 {
		t.Errorf("resync of an unchanged page: %s, want 1 page and none changed (incremental sync)", src.Status.Message)
	}
}

// checkAdmissionRules checks the installed CRDs refuse an invalid spec with the rule's message (R-304).
func checkAdmissionRules(t *testing.T, ns string) {
	const msg = "interval is an ISO-8601 duration of at least PT1M"
	crd := &unstructured.Unstructured{}
	crd.SetAPIVersion("apiextensions.k8s.io/v1")
	crd.SetKind("CustomResourceDefinition")
	must(t, c.Get(ctx, client.ObjectKey{Name: "unifaischedules.unifai.startx.fr"}, crd))
	if b, _ := json.Marshal(crd.Object); !strings.Contains(string(b), msg) {
		t.Skip("the installed CRDs have no spec rules (operator older than 0.1.34)")
	}
	sch := &unifaiv1.UnifaiSchedule{ObjectMeta: metav1.ObjectMeta{Name: "e2e-invalid", Namespace: ns}, Spec: unifaiv1.UnifaiScheduleSpec{
		Workflow: "e2e-wf", Inputs: map[string]string{"user_prompt": "ping"}, Schedule: unifaiv1.ScheduleDefinition{Interval: "PT30S"}}}
	err := c.Create(ctx, sch, client.DryRunAll)
	if err == nil || !strings.Contains(err.Error(), msg) {
		t.Errorf("a 30s schedule interval: got %v, want a refusal with %q", err, msg)
	}
}
