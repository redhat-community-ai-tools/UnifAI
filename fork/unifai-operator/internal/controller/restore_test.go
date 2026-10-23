package controller

import (
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	appsv1 "k8s.io/api/apps/v1"
	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/utils/ptr"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/stack"
)

var _ = Describe("UnifaiRestore", func() {
	const timeout, interval = 30 * time.Second, 200 * time.Millisecond

	// The envtest has no stack controller: the test plays its part (scaling the applications down and up).
	newStack := func(ns string, backup bool) *unifaiv1.UnifaiStack {
		st := &unifaiv1.UnifaiStack{ObjectMeta: metav1.ObjectMeta{Name: unifaiv1.StackName, Namespace: ns}, Spec: unifaiv1.UnifaiStackSpec{
			Identity: unifaiv1.IdentitySpec{External: &unifaiv1.ExternalOIDCSpec{URL: "https://kc", ClientSecret: unifaiv1.SecretKeySelector{Name: "s", Key: "k"}}}}}
		if backup {
			st.Spec.Backup = &unifaiv1.BackupSpec{S3: unifaiv1.BackupS3Spec{Bucket: "b", CredentialsSecret: "s3"}}
		}
		Expect(k8sClient.Create(ctx, st)).To(Succeed())
		st.Status.CredentialKeyFingerprint = "0123456789abcdef"
		Expect(k8sClient.Status().Update(ctx, st)).To(Succeed())
		return st
	}
	newApp := func(ns, name string) *appsv1.Deployment {
		d := &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: ns}, Spec: appsv1.DeploymentSpec{
			Replicas: ptr.To(int32(1)),
			Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"app": name}},
			Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"app": name}},
				Spec: corev1.PodSpec{Containers: []corev1.Container{{Name: "c", Image: "x"}}}}}}
		Expect(k8sClient.Create(ctx, d)).To(Succeed())
		d.Status.Replicas, d.Status.ReadyReplicas, d.Status.AvailableReplicas = 1, 1, 1
		Expect(k8sClient.Status().Update(ctx, d)).To(Succeed())
		return d
	}
	scale := func(d *appsv1.Deployment, n int32) {
		Expect(k8sClient.Get(ctx, client.ObjectKeyFromObject(d), d)).To(Succeed())
		d.Spec.Replicas = ptr.To(n)
		Expect(k8sClient.Update(ctx, d)).To(Succeed())
		d.Status.Replicas, d.Status.ReadyReplicas, d.Status.AvailableReplicas = n, n, n
		Expect(k8sClient.Status().Update(ctx, d)).To(Succeed())
	}
	quiescedBy := func(st *unifaiv1.UnifaiStack) func() string {
		return func() string {
			_ = k8sClient.Get(ctx, client.ObjectKeyFromObject(st), st)
			return st.Annotations[stack.QuiesceAnnotation]
		}
	}
	restorePhase := func(rs *unifaiv1.UnifaiRestore) func() string {
		return func() string {
			_ = k8sClient.Get(ctx, client.ObjectKeyFromObject(rs), rs)
			GinkgoWriter.Printf("restore %s: %s %s\n", rs.Name, rs.Status.Phase, rs.Status.Message)
			return rs.Status.Phase
		}
	}
	// finishJob plays the Job: its pod reports msg in the given container, then the Job gets the condition.
	finishJob := func(ns, restore, container, msg string, code int32, cond batchv1.JobConditionType) {
		job := &batchv1.Job{}
		Eventually(func() error {
			return k8sClient.Get(ctx, client.ObjectKey{Namespace: ns, Name: stack.RestoreJobName(restore)}, job)
		}, timeout, interval).Should(Succeed())
		pod := &corev1.Pod{ObjectMeta: metav1.ObjectMeta{Name: job.Name + "-x", Namespace: ns, Labels: map[string]string{"job-name": job.Name}},
			Spec: corev1.PodSpec{Containers: []corev1.Container{{Name: "mongorestore", Image: "x"}}}}
		Expect(k8sClient.Create(ctx, pod)).To(Succeed())
		pod.Status.ContainerStatuses = []corev1.ContainerStatus{{Name: container,
			State: corev1.ContainerState{Terminated: &corev1.ContainerStateTerminated{ExitCode: code, Message: msg}}}}
		Expect(k8sClient.Status().Update(ctx, pod)).To(Succeed())
		now := metav1.Now()
		job.Status.StartTime = &now
		if cond == batchv1.JobComplete {
			job.Status.Conditions = []batchv1.JobCondition{
				{Type: batchv1.JobSuccessCriteriaMet, Status: corev1.ConditionTrue, LastTransitionTime: now},
				{Type: cond, Status: corev1.ConditionTrue, LastTransitionTime: now}}
			job.Status.Succeeded, job.Status.CompletionTime = 1, &now
		} else {
			job.Status.Conditions = []batchv1.JobCondition{
				{Type: batchv1.JobFailureTarget, Status: corev1.ConditionTrue, LastTransitionTime: now},
				{Type: cond, Status: corev1.ConditionTrue, LastTransitionTime: now}}
			job.Status.Failed = 1
		}
		Expect(k8sClient.Status().Update(ctx, job)).To(Succeed())
	}

	It("stops the applications, runs the restore Job, then restarts them", func() {
		ns := newNamespace("restore")
		st := newStack(ns, true)
		apps := []*appsv1.Deployment{newApp(ns, "unifai-multiagent-be"), newApp(ns, "unifai-rag-server")}
		rs := &unifaiv1.UnifaiRestore{ObjectMeta: metav1.ObjectMeta{Name: "r1", Namespace: ns},
			Spec: unifaiv1.UnifaiRestoreSpec{Backup: "20261023T020000Z", Collections: []string{"docs"}}}
		Expect(k8sClient.Create(ctx, rs)).To(Succeed())

		Eventually(quiescedBy(st), timeout, interval).Should(Equal("r1"))
		Eventually(func() string { restorePhase(rs)(); return rs.Status.Message }, timeout, interval).
			Should(ContainSubstring("unifai-multiagent-be"))
		job := &batchv1.Job{}
		Consistently(func() error {
			return k8sClient.Get(ctx, client.ObjectKey{Namespace: ns, Name: stack.RestoreJobName("r1")}, job)
		}, 2*time.Second, interval).ShouldNot(Succeed(), "no restore while an application runs")

		for _, d := range apps {
			scale(d, 0)
		}
		Eventually(restorePhase(rs), timeout, interval).Should(Equal(restoreRestoring))
		Expect(k8sClient.Get(ctx, client.ObjectKey{Namespace: ns, Name: stack.RestoreJobName("r1")}, job)).To(Succeed())
		env := map[string]string{}
		for _, e := range job.Spec.Template.Spec.InitContainers[0].Env {
			env[e.Name] = e.Value
		}
		Expect(env).To(HaveKeyWithValue("SRC", "s3://b/unifai/"+ns))
		Expect(env).To(HaveKeyWithValue("BACKUP", "20261023T020000Z"))
		Expect(env).To(HaveKeyWithValue("FINGERPRINT", "0123456789abcdef"))
		Expect(env).To(HaveKeyWithValue("MONGODB", "true"))
		Expect(env).To(HaveKeyWithValue("COLLECTIONS", "docs"))
		Expect(*job.Spec.BackoffLimit).To(BeZero())

		finishJob(ns, "r1", "mongorestore", "mongodb/20261023T020000Z\nqdrant/20261023T020001Z\n", 0, batchv1.JobComplete)
		Eventually(restorePhase(rs), timeout, interval).Should(Equal(restoreStarting))
		Expect(quiescedBy(st)()).To(BeEmpty(), "applications released")
		Expect(rs.Status.Restored).To(ConsistOf("mongodb/20261023T020000Z", "qdrant/20261023T020001Z"))

		for _, d := range apps {
			scale(d, 1)
		}
		Eventually(restorePhase(rs), timeout, interval).Should(Equal(PhaseCompleted))
		Expect(rs.Status.CompletedAt).NotTo(BeNil())
		Eventually(func() []string { restorePhase(rs)(); return rs.Finalizers }, timeout, interval).Should(BeEmpty())
	})

	It("restarts the applications when the restore fails, and fails without a backup location", func() {
		ns := newNamespace("restorefail")
		st := newStack(ns, true)
		rs := &unifaiv1.UnifaiRestore{ObjectMeta: metav1.ObjectMeta{Name: "r2", Namespace: ns}}
		Expect(k8sClient.Create(ctx, rs)).To(Succeed())
		Eventually(restorePhase(rs), timeout, interval).Should(Equal(restoreRestoring))
		finishJob(ns, "r2", "fetch", "MongoDB backup x was taken with another credential encryption key", 1, batchv1.JobFailed)
		Eventually(restorePhase(rs), timeout, interval).Should(Equal(PhaseFailed))
		Expect(rs.Status.Message).To(ContainSubstring("another credential encryption key"))
		Expect(quiescedBy(st)()).To(BeEmpty())

		other := newNamespace("restorenosrc")
		newStack(other, false)
		bad := &unifaiv1.UnifaiRestore{ObjectMeta: metav1.ObjectMeta{Name: "r3", Namespace: other}}
		Expect(k8sClient.Create(ctx, bad)).To(Succeed())
		Eventually(restorePhase(bad), timeout, interval).Should(Equal(PhaseFailed))
		Expect(bad.Status.Message).To(ContainSubstring("spec.backup"))
	})

	It("runs one restore at a time per namespace", func() {
		ns := newNamespace("restoreone")
		st := newStack(ns, true)
		newApp(ns, "unifai-ui")
		first := &unifaiv1.UnifaiRestore{ObjectMeta: metav1.ObjectMeta{Name: "a", Namespace: ns}}
		Expect(k8sClient.Create(ctx, first)).To(Succeed())
		Eventually(quiescedBy(st), timeout, interval).Should(Equal("a"))
		second := &unifaiv1.UnifaiRestore{ObjectMeta: metav1.ObjectMeta{Name: "b", Namespace: ns}}
		Expect(k8sClient.Create(ctx, second)).To(Succeed())
		Eventually(restorePhase(second), timeout, interval).Should(Equal(restorePending))
		Expect(second.Status.Message).To(ContainSubstring("UnifaiRestore a"))

		By("deleting the active restore gives the applications back")
		Expect(k8sClient.Delete(ctx, first)).To(Succeed())
		Eventually(quiescedBy(st), timeout, interval).Should(Equal("b"))
	})
})

var _ = Describe("Secret and ConfigMap cache", func() {
	It("reads a Secret without the part-of label (user Secrets are not cached, they are read live)", func() {
		ns := newNamespace("secretread")
		s := &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "user-owned", Namespace: ns}, StringData: map[string]string{"k": "v"}}
		Expect(k8sClient.Create(ctx, s)).To(Succeed())
		got := &corev1.Secret{}
		Expect(mgrClient.Get(ctx, client.ObjectKeyFromObject(s), got)).To(Succeed())
		Expect(string(got.Data["k"])).To(Equal("v"))
	})
})
