package controller

import (
	"context"
	"fmt"
	"regexp"
	"sort"
	"strings"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/stack"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// Restore phases.
const (
	restorePending   = "Pending"
	restoreStopping  = "Stopping"
	restoreRestoring = "Restoring"
	restoreStarting  = "Starting"
)

// restorePoll is how often an active restore is checked.
const restorePoll = 10 * time.Second

// RestoreReconciler runs UnifaiRestore: it stops the UnifAI applications of the stack (QuiesceAnnotation), runs
// the restore Job, then restarts them. One restore at a time per namespace.
type RestoreReconciler struct {
	client.Client
}

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairestores,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairestores/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairestores/finalizers,verbs=update

func (r *RestoreReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	rs := &unifaiv1.UnifaiRestore{}
	if err := r.Get(ctx, req.NamespacedName, rs); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	st := &unifaiv1.UnifaiStack{}
	stErr := r.Get(ctx, types.NamespacedName{Namespace: rs.Namespace, Name: unifaiv1.StackName}, st)
	if stErr != nil && !apierrors.IsNotFound(stErr) {
		return ctrl.Result{}, stErr
	}
	if !rs.DeletionTimestamp.IsZero() {
		// Deleted (while active, or after a failure that kept the applications stopped): the restore Job and its
		// pods go first, then the stack gets its applications back.
		if gone, err := r.jobGone(ctx, rs); err != nil || !gone {
			return ctrl.Result{RequeueAfter: restorePoll}, err
		}
		if stErr == nil {
			if err := r.release(ctx, st, rs.Name); err != nil {
				return ctrl.Result{}, err
			}
		}
		controllerutil.RemoveFinalizer(rs, Finalizer)
		return ctrl.Result{}, client.IgnoreNotFound(r.Update(ctx, rs))
	}
	switch rs.Status.Phase {
	case PhaseCompleted, PhaseFailed:
		// A failure that may have changed data keeps the applications stopped, and the finalizer that releases
		// them when this UnifaiRestore is deleted.
		if stErr == nil && st.Annotations[stack.QuiesceAnnotation] == rs.Name {
			return ctrl.Result{}, nil
		}
		if controllerutil.RemoveFinalizer(rs, Finalizer) {
			return ctrl.Result{}, r.Update(ctx, rs)
		}
		return ctrl.Result{}, nil
	}
	if stErr != nil {
		return ctrl.Result{}, r.finish(ctx, rs, nil, PhaseFailed, "no UnifaiStack in the namespace")
	}
	if controllerutil.AddFinalizer(rs, Finalizer) {
		if err := r.Update(ctx, rs); err != nil {
			return ctrl.Result{}, err
		}
	}
	res, err := r.step(ctx, rs, st)
	if err == nil && (rs.Status.Phase == PhaseCompleted || rs.Status.Phase == PhaseFailed) {
		// Its own status write does not trigger a reconcile: come back to drop the finalizer.
		return ctrl.Result{RequeueAfter: time.Second}, nil
	}
	if err != nil {
		log.FromContext(ctx).Error(err, "restore step", "phase", rs.Status.Phase)
		rs.Status.Message = unifai.Truncate(err.Error(), 500)
		_ = r.patchStatus(ctx, rs)
		return ctrl.Result{RequeueAfter: restorePoll}, nil
	}
	return res, nil
}

// step advances the restore by one phase.
func (r *RestoreReconciler) step(ctx context.Context, rs *unifaiv1.UnifaiRestore, st *unifaiv1.UnifaiStack) (ctrl.Result, error) {
	switch rs.Status.Phase {
	case "", restorePending:
		if other := st.Annotations[stack.QuiesceAnnotation]; other != "" && other != rs.Name {
			return r.wait(ctx, rs, restorePending, "waiting for the UnifaiRestore "+other)
		}
		src, _, err := stack.RestoreSource(rs.Namespace, st, rs)
		if err != nil {
			return ctrl.Result{}, r.finish(ctx, rs, nil, PhaseFailed, err.Error())
		}
		if msg, err := r.checkCredentials(ctx, rs, st, src); err != nil || msg != "" {
			if err != nil {
				return ctrl.Result{}, err
			}
			return ctrl.Result{}, r.finish(ctx, rs, nil, PhaseFailed, msg)
		}
		if st.Status.CredentialKeyFingerprint == "" {
			return r.wait(ctx, rs, restorePending, "waiting for the stack to report its credential key fingerprint")
		}
		if err := r.quiesce(ctx, st, rs.Name); err != nil {
			return ctrl.Result{}, err
		}
		now := metav1.Now()
		rs.Status.StartedAt = &now
		return r.wait(ctx, rs, restoreStopping, "stopping the UnifAI applications")

	case restoreStopping:
		if st.Annotations[stack.QuiesceAnnotation] != rs.Name {
			return ctrl.Result{}, r.finish(ctx, rs, nil, PhaseFailed, "the stack is no longer stopped for this restore")
		}
		if r.expired(rs) {
			return ctrl.Result{}, r.finish(ctx, rs, st, PhaseFailed, "the applications did not stop in time")
		}
		running, err := r.running(ctx, rs.Namespace)
		if err != nil {
			return ctrl.Result{}, err
		}
		if len(running) > 0 {
			return r.wait(ctx, rs, restoreStopping, "stopping "+strings.Join(running, ", "))
		}
		// The Job only needs the namespace and the backup/placement settings of the stack, not its hosts.
		p := &stack.Plan{Namespace: st.Namespace, Spec: &st.Spec}
		src, base, err := stack.RestoreSource(rs.Namespace, st, rs)
		if err != nil {
			return ctrl.Result{}, r.finish(ctx, rs, st, PhaseFailed, err.Error())
		}
		job := stack.RestoreJob(p, rs, src, base, st.Status.CredentialKeyFingerprint)
		if err := controllerutil.SetControllerReference(rs, job, r.Scheme()); err != nil {
			return ctrl.Result{}, err
		}
		if err := r.Create(ctx, job); err != nil && !apierrors.IsAlreadyExists(err) {
			return ctrl.Result{}, err
		}
		return r.wait(ctx, rs, restoreRestoring, "restoring from "+base)

	case restoreRestoring:
		return r.restoring(ctx, rs, st)

	case restoreStarting:
		waiting, err := r.notAvailable(ctx, rs.Namespace)
		if err != nil {
			return ctrl.Result{}, err
		}
		if len(waiting) > 0 && !r.expired(rs) {
			return r.wait(ctx, rs, restoreStarting, "restarting "+strings.Join(waiting, ", "))
		}
		return ctrl.Result{}, r.finish(ctx, rs, st, PhaseCompleted, "restored "+strings.Join(rs.Status.Restored, ", "))
	}
	return ctrl.Result{}, nil
}

// restoring follows the restore Job: on success the applications restart, on a failure that changed nothing too,
// otherwise they stay stopped.
func (r *RestoreReconciler) restoring(ctx context.Context, rs *unifaiv1.UnifaiRestore, st *unifaiv1.UnifaiStack) (ctrl.Result, error) {
	job := &batchv1.Job{}
	err := r.Get(ctx, types.NamespacedName{Namespace: rs.Namespace, Name: stack.RestoreJobName(rs.Name)}, job)
	switch {
	case apierrors.IsNotFound(err):
		return ctrl.Result{}, r.fail(ctx, rs, "the restore Job disappeared")
	case err != nil:
		return ctrl.Result{}, err
	}
	msg := r.jobMessage(ctx, job)
	switch {
	case jobCondition(job, batchv1.JobComplete):
		restored, notes := splitRestoreOutput(msg)
		rs.Status.Restored = restored
		if err := r.release(ctx, st, rs.Name); err != nil {
			return ctrl.Result{}, err
		}
		text := "restored " + strings.Join(restored, ", ")
		if len(notes) > 0 {
			text += " (" + strings.Join(notes, "; ") + ")"
		}
		return r.wait(ctx, rs, restoreStarting, text+": restarting the applications")
	case jobCondition(job, batchv1.JobFailed):
		if after, ok := strings.CutPrefix(msg, stack.RestoreUntouched); ok {
			return ctrl.Result{}, r.finish(ctx, rs, st, PhaseFailed, after+" (no data changed)")
		}
		if msg == "" {
			msg = "the restore Job failed (see its pod logs)"
		}
		return ctrl.Result{}, r.fail(ctx, rs, msg)
	case r.expired(rs):
		return ctrl.Result{}, r.fail(ctx, rs, "the restore did not finish in time")
	}
	return r.wait(ctx, rs, restoreRestoring, rs.Status.Message)
}

// restoreTimeout bounds a restore from its start; past it, a stopping or running restore fails and a restart
// that never completes is reported as done.
const restoreTimeout = 6 * time.Hour

func (r *RestoreReconciler) expired(rs *unifaiv1.UnifaiRestore) bool {
	return rs.Status.StartedAt != nil && time.Since(rs.Status.StartedAt.Time) > restoreTimeout
}

// BackupCredentialsLabel lets a Secret be used as the S3 credentials of an UnifaiRestore spec.source.
const BackupCredentialsLabel = "unifai.startx.fr/backup-credentials"

// checkCredentials returns why the restore may not use its S3 credentials Secret ("" when it may): the stack's
// own backup Secret, or a Secret labelled BackupCredentialsLabel=true. Whoever creates an UnifaiRestore must not
// hand any Secret of the namespace to a Job talking to an endpoint of their choice.
func (r *RestoreReconciler) checkCredentials(ctx context.Context, rs *unifaiv1.UnifaiRestore, st *unifaiv1.UnifaiStack,
	src *unifaiv1.BackupS3Spec) (string, error) {
	if b := st.Spec.Backup; b != nil && src.CredentialsSecret == b.S3.CredentialsSecret {
		return "", nil
	}
	s := &corev1.Secret{}
	if err := r.Get(ctx, types.NamespacedName{Namespace: rs.Namespace, Name: src.CredentialsSecret}, s); err != nil {
		if apierrors.IsNotFound(err) {
			return "credentials Secret " + src.CredentialsSecret + " not found", nil
		}
		return "", err
	}
	if s.Labels[BackupCredentialsLabel] != "true" {
		return "credentials Secret " + src.CredentialsSecret + " is neither the stack's backup Secret nor labelled " +
			BackupCredentialsLabel + "=true", nil
	}
	return "", nil
}

// jobGone deletes the restore Job (foreground: its pods first) and reports whether it and its pods are gone.
func (r *RestoreReconciler) jobGone(ctx context.Context, rs *unifaiv1.UnifaiRestore) (bool, error) {
	job := &batchv1.Job{ObjectMeta: metav1.ObjectMeta{Namespace: rs.Namespace, Name: stack.RestoreJobName(rs.Name)}}
	err := r.Delete(ctx, job, client.PropagationPolicy(metav1.DeletePropagationForeground))
	if err != nil && !apierrors.IsNotFound(err) {
		return false, err
	}
	pods := &corev1.PodList{}
	if err := r.List(ctx, pods, client.InNamespace(rs.Namespace), client.MatchingLabels{"job-name": job.Name}); err != nil {
		return false, err
	}
	return apierrors.IsNotFound(err) && len(pods.Items) == 0, nil
}

// fail ends a restore that may have changed data: the applications stay stopped (a visible condition says so)
// until the UnifaiRestore is deleted.
func (r *RestoreReconciler) fail(ctx context.Context, rs *unifaiv1.UnifaiRestore, msg string) error {
	meta.SetStatusCondition(&rs.Status.Conditions, metav1.Condition{Type: "ApplicationsStopped", Status: metav1.ConditionTrue,
		Reason: "DataMayBeInconsistent", ObservedGeneration: rs.Generation,
		Message: "the restore failed after changing data: check the stores, then delete this UnifaiRestore to restart the applications"})
	return r.finish(ctx, rs, nil, PhaseFailed, msg+"; the applications stay stopped until this UnifaiRestore is deleted")
}

// restoreLine is a restored backup in the Job output.
var restoreLine = regexp.MustCompile(`^(mongodb|qdrant)/[0-9]{8}T[0-9]{6}Z$`)

// splitRestoreOutput separates the restored backups (sorted) from the notes of the Job output.
func splitRestoreOutput(out string) (restored, notes []string) {
	for _, l := range strings.Split(out, "\n") {
		l = strings.TrimSpace(l)
		switch {
		case l == "":
		case restoreLine.MatchString(l):
			restored = append(restored, l)
		default:
			notes = append(notes, l)
		}
	}
	sort.Strings(restored)
	return restored, notes
}

// quiesce makes the stack stop its UnifAI applications on behalf of the restore.
func (r *RestoreReconciler) quiesce(ctx context.Context, st *unifaiv1.UnifaiStack, by string) error {
	if st.Annotations[stack.QuiesceAnnotation] == by {
		return nil
	}
	patch := client.MergeFromWithOptions(st.DeepCopy(), client.MergeFromWithOptimisticLock{})
	if st.Annotations == nil {
		st.Annotations = map[string]string{}
	}
	st.Annotations[stack.QuiesceAnnotation] = by
	return r.Patch(ctx, st, patch)
}

// release removes the restore's QuiesceAnnotation: the stack restarts its applications.
func (r *RestoreReconciler) release(ctx context.Context, st *unifaiv1.UnifaiStack, by string) error {
	if st.Annotations[stack.QuiesceAnnotation] != by {
		return nil
	}
	patch := client.MergeFromWithOptions(st.DeepCopy(), client.MergeFromWithOptimisticLock{})
	delete(st.Annotations, stack.QuiesceAnnotation)
	return r.Patch(ctx, st, patch)
}

// running lists the stopped Deployments that still have pods.
func (r *RestoreReconciler) running(ctx context.Context, ns string) ([]string, error) {
	var out []string
	for _, name := range stack.QuiescedDeployments {
		d := &appsv1.Deployment{}
		if err := r.Get(ctx, types.NamespacedName{Namespace: ns, Name: name}, d); err != nil {
			if apierrors.IsNotFound(err) {
				continue
			}
			return nil, err
		}
		if (d.Spec.Replicas != nil && *d.Spec.Replicas > 0) || d.Status.Replicas > 0 {
			out = append(out, name)
		}
	}
	return out, nil
}

// notAvailable lists the restarted Deployments not available yet.
func (r *RestoreReconciler) notAvailable(ctx context.Context, ns string) ([]string, error) {
	var out []string
	for _, name := range stack.QuiescedDeployments {
		d := &appsv1.Deployment{}
		if err := r.Get(ctx, types.NamespacedName{Namespace: ns, Name: name}, d); err != nil {
			if apierrors.IsNotFound(err) {
				continue
			}
			return nil, err
		}
		if d.Spec.Replicas == nil || *d.Spec.Replicas == 0 || d.Status.AvailableReplicas < *d.Spec.Replicas {
			out = append(out, name)
		}
	}
	return out, nil
}

// jobMessage returns the termination message of the Job pod (the restored backups, or why it failed).
func (r *RestoreReconciler) jobMessage(ctx context.Context, job *batchv1.Job) string {
	pods := &corev1.PodList{}
	if err := r.List(ctx, pods, client.InNamespace(job.Namespace), client.MatchingLabels{"job-name": job.Name}); err != nil {
		return ""
	}
	for _, p := range pods.Items {
		for _, cs := range append(p.Status.InitContainerStatuses, p.Status.ContainerStatuses...) {
			if t := cs.State.Terminated; t != nil && t.Message != "" && (t.ExitCode != 0 || cs.Name == "mongorestore") {
				return strings.TrimSpace(t.Message)
			}
		}
	}
	return ""
}

func jobCondition(job *batchv1.Job, t batchv1.JobConditionType) bool {
	for _, c := range job.Status.Conditions {
		if c.Type == t && c.Status == corev1.ConditionTrue {
			return true
		}
	}
	return false
}

// wait records a phase and polls again.
func (r *RestoreReconciler) wait(ctx context.Context, rs *unifaiv1.UnifaiRestore, phase, msg string) (ctrl.Result, error) {
	rs.Status.Phase, rs.Status.Message = phase, unifai.Truncate(msg, 500)
	return ctrl.Result{RequeueAfter: restorePoll}, r.patchStatus(ctx, rs)
}

// finish ends the restore, restarting the applications if they were stopped.
func (r *RestoreReconciler) finish(ctx context.Context, rs *unifaiv1.UnifaiRestore, st *unifaiv1.UnifaiStack, phase, msg string) error {
	if st != nil {
		if err := r.release(ctx, st, rs.Name); err != nil {
			return err
		}
	}
	now := metav1.Now()
	rs.Status.Phase, rs.Status.Message, rs.Status.CompletedAt = phase, unifai.Truncate(msg, 1000), &now
	cond := metav1.Condition{Type: "Completed", Status: metav1.ConditionTrue, Reason: phase, Message: rs.Status.Message,
		ObservedGeneration: rs.Generation}
	if phase != PhaseCompleted {
		cond.Status = metav1.ConditionFalse
	}
	meta.SetStatusCondition(&rs.Status.Conditions, cond)
	log.FromContext(ctx).Info("restore finished", "phase", phase, "message", msg)
	return r.patchStatus(ctx, rs)
}

func (r *RestoreReconciler) patchStatus(ctx context.Context, rs *unifaiv1.UnifaiRestore) error {
	base := rs.DeepCopy()
	base.Status = unifaiv1.UnifaiRestoreStatus{}
	if err := r.Status().Patch(ctx, rs, client.MergeFrom(base)); err != nil {
		return fmt.Errorf("restore status: %w", err)
	}
	return nil
}

// SetupWithManager registers the controller.
func (r *RestoreReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiRestore{}, specChanges).Owns(&batchv1.Job{}).
		Named("unifairestore").Complete(r)
}
