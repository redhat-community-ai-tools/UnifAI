package stack

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/utils/ptr"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// Backup CronJob names (also used to delete them when spec.backup is removed).
const (
	BackupMongoName  = "unifai-backup-mongodb"
	BackupQdrantName = "unifai-backup-qdrant"

	DefaultAWSCLIImage = "public.ecr.aws/aws-cli/aws-cli:2.22.35"
	DefaultMongoImage  = "docker.io/library/mongo:7.0.16"
)

// BackupNames lists every backup CronJob the operator may own.
var BackupNames = []string{BackupMongoName, BackupQdrantName}

// The upload half shared by both jobs: $AWS is `aws` plus the endpoint, $DEST the store's S3 prefix.
// prune keeps the $KEEP newest entries (names sort by their UTC timestamp).
const backupShellHelpers = `set -eu
export HOME=/tmp
AWS="aws ${S3_ENDPOINT:+--endpoint-url $S3_ENDPOINT}"
TS=$(date -u +%Y%m%dT%H%M%SZ)
# Keeps the KEEP newest backups: a backup is every key starting with its timestamp (<ts>.archive.gz and
# <ts>.meta.json, or the <ts>/ folder of snapshots).
prune() {
  $AWS s3 ls "$1/" | awk '{print $NF}' | sed 's#[./].*##' | sort -u | head -n "-$KEEP" | while read -r old; do
    [ -n "$old" ] && $AWS s3 rm --recursive "$1/" --exclude "*" --include "$old*"
  done
}
`

// mongoUpload uploads the archive the init container dumped, then prunes.
const mongoUpload = backupShellHelpers + `
$AWS s3 cp /backup/mongodb.archive.gz "$DEST/$TS.archive.gz"
printf '{"credentialKeyFingerprint":"%s"}' "$FINGERPRINT" > /backup/meta.json
$AWS s3 cp /backup/meta.json "$DEST/$TS.meta.json"
prune "$DEST"
echo "mongodb backup $DEST/$TS.archive.gz"
`

// qdrantBackup snapshots every collection, downloads and uploads each snapshot, deletes it from Qdrant, then
// prunes whole runs. Restore: POST /collections/<c>/snapshots/upload?priority=snapshot with the file.
const qdrantBackup = backupShellHelpers + `
Q=${QDRANT_URL:-http://qdrant:6333}
cols=$(curl -sf "$Q/collections" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)
for c in $cols; do
  snap=$(curl -sf -X POST "$Q/collections/$c/snapshots?wait=true" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
  curl -sf -o "/backup/$c.snapshot" "$Q/collections/$c/snapshots/$snap"
  $AWS s3 cp "/backup/$c.snapshot" "$DEST/$TS/$c.snapshot"
  curl -sf -X DELETE "$Q/collections/$c/snapshots/$snap" >/dev/null
  rm -f "/backup/$c.snapshot"
done
prune "$DEST"
echo "qdrant backup $DEST/$TS ($(echo $cols | wc -w) collections)"
`

// KeyFingerprint identifies the credential encryption key without revealing it.
func KeyFingerprint(key string) string {
	if key == "" {
		return ""
	}
	sum := sha256.Sum256([]byte(key))
	return hex.EncodeToString(sum[:8])
}

// BackupObjects renders the two backup CronJobs, or nothing when spec.backup is unset.
func BackupObjects(p *Plan) []ctrlObject {
	b := p.Spec.Backup
	if b == nil {
		return nil
	}
	prefix := strings.Trim(b.S3.Prefix, "/")
	if prefix == "" {
		prefix = "unifai/" + p.Namespace
	}
	base := fmt.Sprintf("s3://%s/%s", b.S3.Bucket, prefix)
	awsImage, mongoImage := DefaultAWSCLIImage, DefaultMongoImage
	if b.Images.AWSCLI != "" {
		awsImage = b.Images.AWSCLI
	}
	if b.Images.Mongo != "" {
		mongoImage = b.Images.Mongo
	}
	keep := b.Retention
	if keep < 1 {
		keep = 7
	}
	region := b.S3.Region
	if region == "" {
		region = "us-east-1"
	}
	env := func(store string) []corev1.EnvVar {
		return []corev1.EnvVar{
			{Name: "DEST", Value: base + "/" + store},
			{Name: "KEEP", Value: fmt.Sprint(keep)},
			{Name: "S3_ENDPOINT", Value: b.S3.Endpoint},
			{Name: "AWS_DEFAULT_REGION", Value: region},
		}
	}
	creds := []corev1.EnvFromSource{{SecretRef: &corev1.SecretEnvSource{
		LocalObjectReference: corev1.LocalObjectReference{Name: b.S3.CredentialsSecret}}}}
	scratch := corev1.Volume{Name: "backup", VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{}}}
	mount := []corev1.VolumeMount{{Name: "backup", MountPath: "/backup"}}
	uploader := func(script string) corev1.Container {
		return corev1.Container{Name: "upload", Image: awsImage, Command: []string{"/bin/sh", "-c", script},
			Env: nil, EnvFrom: creds, VolumeMounts: mount, SecurityContext: restricted()}
	}

	mongo := uploader(mongoUpload)
	mongo.Env = append(env("mongodb"), corev1.EnvVar{Name: "FINGERPRINT", Value: KeyFingerprint(p.Secrets[KeyCredentialKey])})
	mongoJob := cronJob(p, BackupMongoName, b, corev1.PodSpec{
		RestartPolicy: corev1.RestartPolicyNever,
		InitContainers: []corev1.Container{{Name: "dump", Image: mongoImage, SecurityContext: restricted(),
			Command:      []string{"mongodump", "--uri=mongodb://mongodb:27017", "--archive=/backup/mongodb.archive.gz", "--gzip"},
			VolumeMounts: mount}},
		Containers: []corev1.Container{mongo},
		Volumes:    []corev1.Volume{scratch},
	})

	qdrant := uploader(qdrantBackup)
	qdrant.Name = "snapshot-and-upload"
	qdrant.Env = env("qdrant")
	qdrantJob := cronJob(p, BackupQdrantName, b, corev1.PodSpec{
		RestartPolicy: corev1.RestartPolicyNever,
		Containers:    []corev1.Container{qdrant},
		Volumes:       []corev1.Volume{scratch},
	})
	return []ctrlObject{mongoJob, qdrantJob}
}

func cronJob(p *Plan, name string, b *unifaiv1.BackupSpec, pod corev1.PodSpec) *batchv1.CronJob {
	schedule := b.Schedule
	if schedule == "" {
		schedule = "0 2 * * *"
	}
	meta := objMeta(p, name, "backup")
	return &batchv1.CronJob{ObjectMeta: meta, Spec: batchv1.CronJobSpec{
		Schedule:                   schedule,
		Suspend:                    ptr.To(b.Suspend),
		ConcurrencyPolicy:          batchv1.ForbidConcurrent,
		StartingDeadlineSeconds:    ptr.To(int64(3600)),
		SuccessfulJobsHistoryLimit: ptr.To(int32(3)),
		FailedJobsHistoryLimit:     ptr.To(int32(3)),
		JobTemplate: batchv1.JobTemplateSpec{Spec: batchv1.JobSpec{
			BackoffLimit: ptr.To(int32(2)),
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{Labels: meta.Labels},
				Spec:       pod,
			},
		}},
	}}
}

func restricted() *corev1.SecurityContext {
	return &corev1.SecurityContext{
		AllowPrivilegeEscalation: ptr.To(false),
		RunAsNonRoot:             ptr.To(true),
		Capabilities:             &corev1.Capabilities{Drop: []corev1.Capability{"ALL"}},
		SeccompProfile:           &corev1.SeccompProfile{Type: corev1.SeccompProfileTypeRuntimeDefault},
	}
}
