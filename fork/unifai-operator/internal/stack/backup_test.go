package stack

import (
	"os/exec"
	"strings"
	"testing"

	batchv1 "k8s.io/api/batch/v1"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

func TestBackupObjects(t *testing.T) {
	if objs := BackupObjects(testPlan(t, nil)); objs != nil {
		t.Fatalf("no backup CronJobs without spec.backup, got %d", len(objs))
	}
	p := testPlan(t, func(s *unifaiv1.UnifaiStackSpec) {
		s.Backup = &unifaiv1.BackupSpec{S3: unifaiv1.BackupS3Spec{Bucket: "bk", Endpoint: "https://s3.example.com",
			CredentialsSecret: "s3-creds"}, Retention: 5}
	})
	objs := BackupObjects(p)
	if len(objs) != 2 {
		t.Fatalf("want 2 CronJobs, got %d", len(objs))
	}
	byName := map[string]*batchv1.CronJob{}
	for _, o := range objs {
		byName[o.GetName()] = o.(*batchv1.CronJob)
	}
	mongo, qdrant := byName[BackupMongoName], byName[BackupQdrantName]
	if mongo == nil || qdrant == nil {
		t.Fatalf("missing CronJobs: %v", byName)
	}
	if mongo.Spec.Schedule != "0 2 * * *" || mongo.Spec.ConcurrencyPolicy != batchv1.ForbidConcurrent {
		t.Errorf("schedule/concurrency: %s %s", mongo.Spec.Schedule, mongo.Spec.ConcurrencyPolicy)
	}
	pod := mongo.Spec.JobTemplate.Spec.Template.Spec
	if pod.InitContainers[0].Image != DefaultMongoImage || !strings.Contains(strings.Join(pod.InitContainers[0].Command, " "), "--archive") {
		t.Errorf("mongodump init container: %+v", pod.InitContainers[0])
	}
	env := map[string]string{}
	for _, e := range pod.Containers[0].Env {
		env[e.Name] = e.Value
	}
	if env["DEST"] != "s3://bk/unifai/team-a/mongodb" || env["KEEP"] != "5" || env["S3_ENDPOINT"] != "https://s3.example.com" {
		t.Errorf("upload env: %v", env)
	}
	if pod.Containers[0].EnvFrom[0].SecretRef.Name != "s3-creds" {
		t.Errorf("credentials secret not mounted")
	}
	qenv := qdrant.Spec.JobTemplate.Spec.Template.Spec.Containers[0].Env
	if qenv[0].Value != "s3://bk/unifai/team-a/qdrant" {
		t.Errorf("qdrant destination: %v", qenv)
	}
}

func TestBackupScriptsParse(t *testing.T) {
	for name, script := range map[string]string{"mongo": mongoUpload, "qdrant": qdrantBackup} {
		if out, err := exec.Command("sh", "-n", "-c", script).CombinedOutput(); err != nil {
			t.Errorf("%s script does not parse: %v %s", name, err, out)
		}
	}
}
