//go:build e2e

package e2e

import (
	"fmt"
	"strings"
	"testing"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
	"k8s.io/utils/ptr"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// Images of the restore test: an S3 service and the clients writing and reading the data.
const (
	minioImage  = "quay.io/minio/minio:RELEASE.2024-12-18T13-15-44Z"
	awsImage    = "public.ecr.aws/aws-cli/aws-cli:2.22.35"
	mongoImage  = "docker.io/library/mongo:7.0.16"
	pythonImage = "registry.access.redhat.com/ubi9/python-312:latest"
	minioUser   = "e2e-access"
	minioSecret = "e2e-secret-key"
)

// runPod runs a command in a throwaway pod of the namespace and returns whether it succeeded and its output
// (the termination message, or the last log lines when the command fails before writing it).
func runPod(t *testing.T, ns, name, image string, cmd []string, env ...corev1.EnvVar) (bool, string) {
	t.Helper()
	pod := &corev1.Pod{ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: ns}, Spec: corev1.PodSpec{
		RestartPolicy: corev1.RestartPolicyNever,
		Containers: []corev1.Container{{Name: "run", Image: image, Command: cmd, Env: env,
			TerminationMessagePolicy: corev1.TerminationMessageFallbackToLogsOnError}},
	}}
	must(t, c.Create(ctx, pod))
	defer func() { _ = c.Delete(ctx, pod) }()
	var msg string
	eventually(t, name+" finished", 5*time.Minute, func() (bool, string) {
		if err := c.Get(ctx, client.ObjectKeyFromObject(pod), pod); err != nil {
			return false, err.Error()
		}
		for _, cs := range pod.Status.ContainerStatuses {
			if term := cs.State.Terminated; term != nil {
				msg = strings.TrimSpace(term.Message)
			}
		}
		return pod.Status.Phase == corev1.PodSucceeded || pod.Status.Phase == corev1.PodFailed, string(pod.Status.Phase)
	})
	return pod.Status.Phase == corev1.PodSucceeded, msg
}

// sh runs a shell script in a pod and fails the test when it fails.
func sh(t *testing.T, ns, name, image, script string, env ...corev1.EnvVar) string {
	t.Helper()
	ok, out := runPod(t, ns, name, image, []string{"/bin/sh", "-c", "set -eu\n" + script}, env...)
	if !ok {
		t.Fatalf("%s: %s", name, out)
	}
	return out
}

// deployMinIO runs an S3 service (Deployment and Service e2e-minio) with the bucket e2e and the credentials Secret
// e2e-s3 the backup and restore jobs read.
func deployMinIO(t *testing.T, ns string) {
	t.Helper()
	labels := map[string]string{"app": "e2e-minio"}
	must(t, c.Create(ctx, &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "e2e-s3", Namespace: ns},
		StringData: map[string]string{"AWS_ACCESS_KEY_ID": minioUser, "AWS_SECRET_ACCESS_KEY": minioSecret}}))
	must(t, c.Create(ctx, &appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: "e2e-minio", Namespace: ns}, Spec: appsv1.DeploymentSpec{
		Replicas: ptr.To(int32(1)), Selector: &metav1.LabelSelector{MatchLabels: labels},
		Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{Labels: labels}, Spec: corev1.PodSpec{
			Containers: []corev1.Container{{Name: "minio", Image: minioImage, Args: []string{"server", "/data"},
				Env: []corev1.EnvVar{{Name: "MINIO_ROOT_USER", Value: minioUser}, {Name: "MINIO_ROOT_PASSWORD", Value: minioSecret}},
				Ports:        []corev1.ContainerPort{{ContainerPort: 9000}},
				VolumeMounts: []corev1.VolumeMount{{Name: "data", MountPath: "/data"}}}},
			Volumes: []corev1.Volume{{Name: "data", VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{}}}},
		}}}}))
	must(t, c.Create(ctx, &corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: "e2e-minio", Namespace: ns}, Spec: corev1.ServiceSpec{
		Selector: labels, Ports: []corev1.ServicePort{{Port: 9000, TargetPort: intstr.FromInt32(9000)}}}}))
	eventually(t, "MinIO ready", 5*time.Minute, func() (bool, string) {
		d := &appsv1.Deployment{}
		if err := c.Get(ctx, client.ObjectKey{Namespace: ns, Name: "e2e-minio"}, d); err != nil {
			return false, err.Error()
		}
		return d.Status.AvailableReplicas == 1, fmt.Sprintf("%d available", d.Status.AvailableReplicas)
	})
	sh(t, ns, "e2e-minio-bucket", awsImage, `export HOME=/tmp
for i in 1 2 3 4 5 6; do aws --endpoint-url http://e2e-minio:9000 s3 mb s3://e2e && exit 0; sleep 5; done; exit 1`, s3Env()...)
}

func s3Env() []corev1.EnvVar {
	return []corev1.EnvVar{{Name: "AWS_ACCESS_KEY_ID", Value: minioUser}, {Name: "AWS_SECRET_ACCESS_KEY", Value: minioSecret},
		{Name: "AWS_DEFAULT_REGION", Value: "us-east-1"}}
}

// runBackupNow runs the backup CronJob as a Job and waits for it.
func runBackupNow(t *testing.T, ns, cronJob string) {
	t.Helper()
	cj := &batchv1.CronJob{}
	eventually(t, cronJob+" rendered", 3*time.Minute, func() (bool, string) {
		err := c.Get(ctx, client.ObjectKey{Namespace: ns, Name: cronJob}, cj)
		return err == nil, fmt.Sprint(err)
	})
	job := &batchv1.Job{ObjectMeta: metav1.ObjectMeta{Name: cronJob + "-e2e", Namespace: ns}, Spec: cj.Spec.JobTemplate.Spec}
	must(t, c.Create(ctx, job))
	eventually(t, job.Name+" complete", 5*time.Minute, func() (bool, string) {
		if err := c.Get(ctx, client.ObjectKeyFromObject(job), job); err != nil {
			return false, err.Error()
		}
		if job.Status.Failed > 0 {
			t.Fatalf("%s failed", job.Name)
		}
		return job.Status.Succeeded > 0, fmt.Sprintf("active %d", job.Status.Active)
	})
}

// checkRestore backs up a MongoDB marker and a Qdrant collection to MinIO, changes both, restores them with an
// UnifaiRestore and checks the data, the applications and a chat afterwards.
func checkRestore(t *testing.T, ns string, st *unifaiv1.UnifaiStack) {
	deployMinIO(t, ns)
	must(t, c.Get(ctx, client.ObjectKeyFromObject(st), st))
	st.Spec.Backup = &unifaiv1.BackupSpec{Schedule: "0 0 1 1 *", Retention: 2, S3: unifaiv1.BackupS3Spec{
		Endpoint: "http://e2e-minio:9000", Bucket: "e2e", CredentialsSecret: "e2e-s3"}}
	must(t, c.Update(ctx, st))

	mongo := func(name, js string) string {
		return sh(t, ns, name, mongoImage, `mongosh --quiet mongodb://mongodb:27017/e2e_restore --eval '`+js+`' > /dev/termination-log`)
	}
	qdrant := func(name, py string) string {
		return sh(t, ns, name, pythonImage, `python - <<'EOF'
import json, urllib.request
Q = "http://qdrant:6333/collections/e2e_restore"
def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        return {"status": e.code}
`+py+`
EOF`)
	}

	mongo("e2e-seed-mongo", `db.marker.deleteMany({}); db.marker.insertOne({v: "before"}); print("ok")`)
	qdrant("e2e-seed-qdrant", `call("PUT", Q, {"vectors": {"size": 2, "distance": "Cosine"}})
call("PUT", Q + "/points?wait=true", {"points": [{"id": 1, "vector": [0.1, 0.9], "payload": {"v": "before"}}]})
open("/dev/termination-log", "w").write("ok")`)
	runBackupNow(t, ns, "unifai-backup-mongodb")
	runBackupNow(t, ns, "unifai-backup-qdrant")

	mongo("e2e-change-mongo", `db.marker.deleteMany({}); db.marker.insertOne({v: "after"}); print("ok")`)
	qdrant("e2e-change-qdrant", `call("DELETE", Q)
open("/dev/termination-log", "w").write("ok")`)

	rs := &unifaiv1.UnifaiRestore{ObjectMeta: metav1.ObjectMeta{Name: "e2e-restore", Namespace: ns},
		Spec: unifaiv1.UnifaiRestoreSpec{Collections: []string{"e2e_restore"}}}
	create(t, rs)
	eventually(t, "restore", 15*time.Minute, func() (bool, string) {
		if err := c.Get(ctx, client.ObjectKeyFromObject(rs), rs); err != nil {
			return false, err.Error()
		}
		if rs.Status.Phase == "Failed" {
			t.Fatalf("restore failed: %s", rs.Status.Message)
		}
		return rs.Status.Phase == "Completed", rs.Status.Phase + " " + rs.Status.Message
	})
	if len(rs.Status.Restored) != 2 || !strings.HasPrefix(rs.Status.Restored[0], "mongodb/") ||
		!strings.HasPrefix(rs.Status.Restored[1], "qdrant/") {
		t.Errorf("restored %v", rs.Status.Restored)
	}

	if got := mongo("e2e-check-mongo", `print(db.marker.find().toArray().map(d => d.v).join(","))`); got != "before" {
		t.Errorf("MongoDB marker after the restore: %q, want before", got)
	}
	if got := qdrant("e2e-check-qdrant", `r = call("POST", Q + "/points", {"ids": [1], "with_payload": True})
open("/dev/termination-log", "w").write(",".join(p["payload"]["v"] for p in r.get("result", [])))`); got != "before" {
		t.Errorf("Qdrant point after the restore: %q, want before", got)
	}

	waitStackReady(t, st, 10*time.Minute, func() bool { return st.Annotations["unifai.startx.fr/quiesced-by"] == "" })
	chat := &unifaiv1.UnifaiChat{ObjectMeta: metav1.ObjectMeta{Name: "e2e-chat-after-restore", Namespace: ns},
		Spec: unifaiv1.UnifaiChatSpec{Workflow: "e2e-wf", Prompt: "ping"}}
	create(t, chat)
	waitPhase(t, chat, "Completed", 10*time.Minute)

	must(t, c.Get(ctx, client.ObjectKeyFromObject(st), st))
	st.Spec.Backup = nil
	must(t, c.Update(ctx, st))
}
