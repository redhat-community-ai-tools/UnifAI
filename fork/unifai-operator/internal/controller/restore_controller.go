package controller

import (
	"context"
	"fmt"
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
		// Deleted while active: give the stack its applications back.
		if stErr == nil {
			if err := r.release(ctx, st, rs.Name); err != nil {
				return ctrl.Result{}, err
			}
		}
		controllerutil.RemoveFinalizer(rs, Finalizer)
		return ctrl.Result{}, client.IgnoreNotFound(r.Update(ctx, rs))
	}
	status := rs.Status
	switch status.Phase {
	case PhaseCompleted, PhaseFailed:
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
		if _, _, err := stack.RestoreSource(rs.Namespace, st, rs); err != nil {
			return ctrl.Result{}, r.finish(ctx, rs, nil, PhaseFailed, err.Error())
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
		job := &batchv1.Job{}
		if err := r.Get(ctx, types.NamespacedName{Namespace: rs.Namespace, Name: stack.RestoreJobName(rs.Name)}, job); err != nil {
			return ctrl.Result{}, err
		}
		msg := r.jobMessage(ctx, job)
		switch {
		case jobCondition(job, batchv1.JobComplete):
			rs.Status.Restored = strings.Fields(msg)
			if err := r.release(ctx, st, rs.Name); err != nil {
				return ctrl.Result{}, err
			}
			return r.wait(ctx, rs, restoreStarting, "restored "+strings.Join(rs.Status.Restored, ", ")+": restarting the applications")
		case jobCondition(job, batchv1.JobFailed):
			if msg == "" {
				msg = "the restore Job failed (see its pod logs)"
			}
			return ctrl.Result{}, r.finish(ctx, rs, st, PhaseFailed, msg)
		}
		return r.wait(ctx, rs, restoreRestoring, rs.Status.Message)

	case restoreStarting:
		waiting, err := r.notAvailable(ctx, rs.Namespace)
		if err != nil {
			return ctrl.Result{}, err
		}
		if len(waiting) > 0 {
			return r.wait(ctx, rs, restoreStarting, "restarting "+strings.Join(waiting, ", "))
		}
		return ctrl.Result{}, r.finish(ctx, rs, st, PhaseCompleted, "restored "+strings.Join(rs.Status.Restored, ", "))
	}
	return ctrl.Result{}, nil
}

// quiesce makes the stack stop its UnifAI applications on behalf of the restore.
func (r *RestoreReconciler) quiesce(ctx context.Context, st *unifaiv1.UnifaiStack, by string) error {
	if st.Annotations[stack.QuiesceAnnotation] == by {
		return nil
	}
	patch := client.MergeFrom(st.DeepCopy())
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
	patch := client.MergeFrom(st.DeepCopy())
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
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiRestore{}).Owns(&batchv1.Job{}).
		Named("unifairestore").Complete(r)
}
