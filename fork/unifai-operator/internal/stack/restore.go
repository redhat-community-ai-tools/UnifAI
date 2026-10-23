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

// RestoreUntouched prefixes the failure message of a restore that stopped before changing any data: only then
// does the operator restart the applications on its own.
const RestoreUntouched = "untouched: "

// restoreFetch resolves the backups, checks the MongoDB key fingerprint (fails closed), downloads the MongoDB
// archive and restores the Qdrant collections (Qdrant keeps running). Its outcome goes to /restore/summary and
// /restore/notes. The endpoint is an argument of aws, never word-split; object names are checked before use.
const restoreFetch = `set -eu
export HOME=/tmp
s3() { if [ -n "${S3_ENDPOINT:-}" ]; then aws --endpoint-url "$S3_ENDPOINT" "$@"; else aws "$@"; fi; }
# Failure before any data changed (the operator restarts the applications), and after (they stay stopped).
untouched() { echo "` + RestoreUntouched + `$1" > /dev/termination-log; echo "$1" >&2; exit 1; }
fail() { echo "$1" > /dev/termination-log; echo "$1" >&2; exit 1; }
# Newest backup timestamp of a store at or before $BACKUP.
pick() {
  s3 s3 ls "$1/" | awk '{print $NF}' | sed 's#[./].*##' | grep -E '^[0-9]{8}T[0-9]{6}Z$' | sort -u |
    awk -v b="$BACKUP" 'b == "latest" || $0 <= b' | tail -n 1
}
: > /restore/summary
: > /restore/notes
mongo_ts= qdrant_ts=
if [ "$MONGODB" = true ]; then
  mongo_ts=$(pick "$SRC/mongodb")
  [ -n "$mongo_ts" ] || untouched "no MongoDB backup at or before $BACKUP in $SRC/mongodb"
  if s3 s3 ls "$SRC/mongodb/" | awk '{print $NF}' | grep -Fxq "$mongo_ts.meta.json"; then
    s3 s3 cp --only-show-errors "$SRC/mongodb/$mongo_ts.meta.json" /restore/meta.json ||
      untouched "cannot read $SRC/mongodb/$mongo_ts.meta.json"
    fp=$(sed -n 's/.*"credentialKeyFingerprint":"\([0-9a-f]*\)".*/\1/p' /restore/meta.json)
    if [ "$fp" != "$FINGERPRINT" ]; then
      [ "$ALLOW_KEY_MISMATCH" = true ] ||
        untouched "MongoDB backup $mongo_ts was taken with another credential encryption key ($fp, this stack $FINGERPRINT): set spec.allowKeyMismatch to restore it anyway"
      echo "mongodb/$mongo_ts: other credential key ($fp), restored with allowKeyMismatch" >> /restore/notes
    fi
  else
    [ "$ALLOW_KEY_MISMATCH" = true ] ||
      untouched "MongoDB backup $mongo_ts has no key fingerprint (taken before operator 0.1.30): set spec.allowKeyMismatch to restore it anyway"
    echo "mongodb/$mongo_ts: no key fingerprint, restored with allowKeyMismatch" >> /restore/notes
  fi
  s3 s3 cp --only-show-errors "$SRC/mongodb/$mongo_ts.archive.gz" /restore/mongodb.archive.gz ||
    untouched "cannot download $SRC/mongodb/$mongo_ts.archive.gz"
fi
if [ "$QDRANT" = true ]; then
  qdrant_ts=$(pick "$SRC/qdrant")
  [ -n "$qdrant_ts" ] || untouched "no Qdrant backup at or before $BACKUP in $SRC/qdrant"
  s3 s3 ls "$SRC/qdrant/$qdrant_ts/" | awk '{print $NF}' > /restore/snapshots
  # Downloaded first: a missing or unreadable snapshot stops the restore before any collection is replaced.
  : > /restore/collections
  while read -r f; do
    c=${f%.snapshot}
    case "$c" in *[!A-Za-z0-9_.-]*|"") untouched "unexpected Qdrant snapshot name: $f" ;; esac
    if [ -n "$COLLECTIONS" ] && ! printf '%s\n' $COLLECTIONS | grep -Fxq "$c"; then continue; fi
    s3 s3 cp --only-show-errors "$SRC/qdrant/$qdrant_ts/$f" "/restore/$c.snapshot" ||
      untouched "cannot download the Qdrant snapshot $f"
    echo "$c" >> /restore/collections
  done < /restore/snapshots
  Q=${QDRANT_URL:-http://qdrant:6333}
  n=0
  while read -r c; do
    curl -gsf -X POST "$Q/collections/$c/snapshots/upload?priority=snapshot&wait=true" \
      -F "snapshot=@/restore/$c.snapshot" >/dev/null || fail "restore of the Qdrant collection $c failed"
    rm -f "/restore/$c.snapshot"
    n=$((n + 1))
  done < /restore/collections
  echo "qdrant/$qdrant_ts" >> /restore/summary
  echo "qdrant/$qdrant_ts: $n collections" >> /restore/notes
fi
[ -z "$mongo_ts" ] || echo "mongodb/$mongo_ts" >> /restore/summary
`

// restoreMongo replaces the dumped databases, then reports the restored backups and the notes as the termination
// message (one per line).
const restoreMongo = `set -eu
if [ -f /restore/mongodb.archive.gz ]; then
  mongorestore --uri=mongodb://mongodb:27017 --archive=/restore/mongodb.archive.gz --gzip --drop --quiet
fi
cat /restore/summary /restore/notes > /dev/termination-log
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
	job := &batchv1.Job{ObjectMeta: meta, Spec: batchv1.JobSpec{
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
	hardenJobPod(&job.Spec.Template.Spec)
	return job
}

// RestoreJobName is the Job of an UnifaiRestore.
func RestoreJobName(restore string) string { return "unifai-restore-" + restore }
