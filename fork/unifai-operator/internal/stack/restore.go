package stack

import (
	"fmt"
	"strings"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/utils/ptr"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// QuiescedDeployments are the Deployments of the Quiescable releases, stopped during a restore.
var QuiescedDeployments = []string{"unifai-ui", "unifai-multiagent-be", "unifai-multiagent-temporal-worker",
	"unifai-rag-server", "unifai-rag-celery", "unifai-backend", "unifai-identity"}

// restoreFetch resolves the backups, checks the MongoDB key fingerprint, downloads the MongoDB archive and
// restores the Qdrant collections (Qdrant keeps running). Its outcome goes to /restore/summary.
const restoreFetch = `set -eu
export HOME=/tmp
AWS="aws ${S3_ENDPOINT:+--endpoint-url $S3_ENDPOINT}"
fail() { echo "$1" > /dev/termination-log; echo "$1" >&2; exit 1; }
# Newest backup timestamp of a store at or before $BACKUP.
pick() {
  $AWS s3 ls "$1/" | awk '{print $NF}' | sed 's#[./].*##' | sort -u | awk -v b="$BACKUP" 'b == "latest" || $0 <= b' | tail -n 1
}
: > /restore/summary
if [ "$MONGODB" = true ]; then
  ts=$(pick "$SRC/mongodb")
  [ -n "$ts" ] || fail "no MongoDB backup at or before $BACKUP in $SRC/mongodb"
  if $AWS s3 cp "$SRC/mongodb/$ts.meta.json" /restore/meta.json >/dev/null 2>&1; then
    fp=$(sed -n 's/.*"credentialKeyFingerprint":"\([0-9a-f]*\)".*/\1/p' /restore/meta.json)
    if [ "$fp" != "$FINGERPRINT" ] && [ "$ALLOW_KEY_MISMATCH" != true ]; then
      fail "MongoDB backup $ts was taken with another credential encryption key ($fp, this stack $FINGERPRINT): set spec.allowKeyMismatch to restore it anyway"
    fi
  else
    echo "mongodb/$ts: key not verified (backup without fingerprint)" >> /restore/notes
  fi
  $AWS s3 cp --only-show-errors "$SRC/mongodb/$ts.archive.gz" /restore/mongodb.archive.gz
  echo "mongodb/$ts" >> /restore/summary
fi
if [ "$QDRANT" = true ]; then
  ts=$(pick "$SRC/qdrant")
  [ -n "$ts" ] || fail "no Qdrant backup at or before $BACKUP in $SRC/qdrant"
  Q=${QDRANT_URL:-http://qdrant:6333}
  n=0
  for f in $($AWS s3 ls "$SRC/qdrant/$ts/" | awk '{print $NF}'); do
    c=${f%.snapshot}
    if [ -n "$COLLECTIONS" ] && ! echo " $COLLECTIONS " | grep -q " $c "; then continue; fi
    $AWS s3 cp --only-show-errors "$SRC/qdrant/$ts/$f" /restore/collection.snapshot
    curl -sf -X POST "$Q/collections/$c/snapshots/upload?priority=snapshot&wait=true" \
      -F snapshot=@/restore/collection.snapshot >/dev/null || fail "restore of the Qdrant collection $c failed"
    rm -f /restore/collection.snapshot
    n=$((n + 1))
  done
  echo "qdrant/$ts" >> /restore/summary
  echo "qdrant/$ts: $n collections" >> /restore/notes
fi
`

// restoreMongo replaces the dumped databases, then reports the summary as the termination message.
const restoreMongo = `set -eu
if [ -f /restore/mongodb.archive.gz ]; then
  mongorestore --uri=mongodb://mongodb:27017 --archive=/restore/mongodb.archive.gz --gzip --drop --quiet
fi
cat /restore/summary > /dev/termination-log
`

// RestoreSource returns the S3 location of the backups an UnifaiRestore reads, and the "s3://bucket/prefix" base.
func RestoreSource(ns string, st *unifaiv1.UnifaiStack, r *unifaiv1.UnifaiRestore) (*unifaiv1.BackupS3Spec, string, error) {
	src := r.Spec.Source
	if src == nil {
		if st.Spec.Backup == nil {
			return nil, "", fmt.Errorf("the stack has no spec.backup: set spec.source")
		}
		src = &st.Spec.Backup.S3
	}
	prefix := strings.Trim(src.Prefix, "/")
	if prefix == "" {
		prefix = "unifai/" + ns
	}
	return src, fmt.Sprintf("s3://%s/%s", src.Bucket, prefix), nil
}

// RestoreJob is the Job of an UnifaiRestore: an init container fetches the backups and restores Qdrant, the
// main container restores MongoDB. It runs once (no retry: a half-restored store needs a look first).
func RestoreJob(p *Plan, r *unifaiv1.UnifaiRestore, src *unifaiv1.BackupS3Spec, base, fingerprint string) *batchv1.Job {
	stores := map[unifaiv1.RestoreStore]bool{}
	for _, s := range r.Spec.Stores {
		stores[s] = true
	}
	all := len(stores) == 0
	awsImage, mongoImage := DefaultAWSCLIImage, DefaultMongoImage
	if b := p.Spec.Backup; b != nil {
		if b.Images.AWSCLI != "" {
			awsImage = b.Images.AWSCLI
		}
		if b.Images.Mongo != "" {
			mongoImage = b.Images.Mongo
		}
	}
	region := src.Region
	if region == "" {
		region = "us-east-1"
	}
	backup := r.Spec.Backup
	if backup == "" {
		backup = "latest"
	}
	env := []corev1.EnvVar{
		{Name: "SRC", Value: base},
		{Name: "BACKUP", Value: backup},
		{Name: "MONGODB", Value: fmt.Sprint(all || stores[unifaiv1.RestoreMongoDB])},
		{Name: "QDRANT", Value: fmt.Sprint(all || stores[unifaiv1.RestoreQdrant])},
		{Name: "COLLECTIONS", Value: strings.Join(r.Spec.Collections, " ")},
		{Name: "FINGERPRINT", Value: fingerprint},
		{Name: "ALLOW_KEY_MISMATCH", Value: fmt.Sprint(r.Spec.AllowKeyMismatch)},
		{Name: "S3_ENDPOINT", Value: src.Endpoint},
		{Name: "AWS_DEFAULT_REGION", Value: region},
	}
	mount := []corev1.VolumeMount{{Name: "restore", MountPath: "/restore"}}
	meta := objMeta(p, RestoreJobName(r.Name), "restore")
	return &batchv1.Job{ObjectMeta: meta, Spec: batchv1.JobSpec{
		BackoffLimit:          ptr.To(int32(0)),
		ActiveDeadlineSeconds: ptr.To(int64(4 * 3600)),
		Template: corev1.PodTemplateSpec{
			ObjectMeta: metav1.ObjectMeta{Labels: meta.Labels},
			Spec: corev1.PodSpec{
				RestartPolicy: corev1.RestartPolicyNever,
				NodeSelector:  p.Spec.NodeSelector, Tolerations: p.Spec.Tolerations,
				InitContainers: []corev1.Container{{Name: "fetch", Image: awsImage, Command: []string{"/bin/sh", "-c", restoreFetch},
					Env: env, VolumeMounts: mount, SecurityContext: restricted(),
					EnvFrom: []corev1.EnvFromSource{{SecretRef: &corev1.SecretEnvSource{
						LocalObjectReference: corev1.LocalObjectReference{Name: src.CredentialsSecret}}}}}},
				Containers: []corev1.Container{{Name: "mongorestore", Image: mongoImage, Command: []string{"/bin/sh", "-c", restoreMongo},
					VolumeMounts: mount, SecurityContext: restricted()}},
				Volumes: []corev1.Volume{{Name: "restore", VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{}}}},
			},
		},
	}}
}

// RestoreJobName is the Job of an UnifaiRestore.
func RestoreJobName(restore string) string { return "unifai-restore-" + restore }
