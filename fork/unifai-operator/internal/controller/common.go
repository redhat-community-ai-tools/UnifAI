package controller

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

const (
	// Finalizer removes the UnifAI object when the CR is deleted.
	Finalizer = "unifai.startx.fr/finalizer"
	retry     = 10 * time.Second
	resync    = 10 * time.Minute
)

// PermanentError is a spec problem: the object is not retried until its spec changes.
type PermanentError struct{ Err error }

func (e *PermanentError) Error() string { return e.Err.Error() }

func permanent(format string, a ...any) error { return &PermanentError{Err: fmt.Errorf(format, a...)} }

// permanentOn turns API errors with one of the statuses into a PermanentError.
func permanentOn(err error, statuses ...int) error {
	if err != nil && unifai.IsStatus(err, statuses...) {
		return &PermanentError{Err: err}
	}
	return err
}

// Base holds what every UnifAI object reconciler needs.
type Base struct {
	client.Client
	Scheme *runtime.Scheme
	// Endpoints returns the MAS and RAG base URLs for a namespace (overridable in tests).
	Endpoints func(namespace string) (mas, rag string)
	// APIReader reads without the informer cache: the status holds the ids of the UnifAI objects, and a stale
	// cached copy right after a write would make the controller create duplicates or refuse its own objects.
	APIReader client.Reader
}

// get reads the object from the API server when an uncached reader is set.
func (b *Base) get(ctx context.Context, key client.ObjectKey, obj client.Object) error {
	if b.APIReader != nil {
		return b.APIReader.Get(ctx, key, obj)
	}
	return b.Get(ctx, key, obj)
}

func (b *Base) endpoints(ns string) (string, string) {
	if b.Endpoints != nil {
		return b.Endpoints(ns)
	}
	return unifai.Endpoints(ns)
}

func (b *Base) mas(o unifaiv1.Object) *unifai.Client {
	m, _ := b.endpoints(o.GetNamespace())
	return unifai.New(m, o.GetCommon().Owner, o.GetCommon().TeamID)
}

func (b *Base) rag(o unifaiv1.Object) *unifai.Client {
	_, r := b.endpoints(o.GetNamespace())
	c := unifai.New(r, o.GetCommon().Owner, o.GetCommon().TeamID)
	c.HTTP.Timeout = 5 * time.Minute
	return c
}

func unifaiName(o unifaiv1.Object) string {
	if n := o.GetCommon().UnifaiName; n != "" {
		return n
	}
	return o.GetName()
}

func adopting(o unifaiv1.Object) bool { return o.GetAnnotations()[unifaiv1.AdoptAnnotation] == "true" }

func notManaged(what string) error {
	return permanent("%s already exists in UnifAI and is not managed by this resource; annotate it with %s=\"true\" to take it over",
		what, unifaiv1.AdoptAnnotation)
}

// hash is a truncated SHA-256 of the JSON encoding of v.
func hash(v any) string {
	b, _ := json.Marshal(v)
	s := sha256.Sum256(b)
	return hex.EncodeToString(s[:])[:16]
}

// rawMap decodes a RawExtension holding a JSON object (nil = empty map).
func rawMap(r *runtime.RawExtension) (map[string]any, error) {
	m := map[string]any{}
	if r == nil || len(r.Raw) == 0 {
		return m, nil
	}
	if err := json.Unmarshal(r.Raw, &m); err != nil {
		return nil, permanent("invalid object: %v", err)
	}
	return m, nil
}

func (b *Base) secretValue(ctx context.Context, ns string, sel unifaiv1.SecretKeySelector) (string, error) {
	var s corev1.Secret
	if err := b.Get(ctx, types.NamespacedName{Namespace: ns, Name: sel.Name}, &s); err != nil {
		return "", fmt.Errorf("secret %s: %w", sel.Name, err)
	}
	v, ok := s.Data[sel.Key]
	if !ok {
		return "", fmt.Errorf("secret %s has no key %s", sel.Name, sel.Key)
	}
	return string(v), nil
}

func (b *Base) applySecrets(ctx context.Context, ns string, refs []unifaiv1.SecretRef, target map[string]any) error {
	for _, r := range refs {
		v, err := b.secretValue(ctx, ns, r.SecretKeyRef)
		if err != nil {
			return err
		}
		unifai.SetPath(target, r.Path, v)
	}
	return nil
}

// stackGate returns an error while the namespace's UnifaiStack exists and is not Ready.
// Namespaces without an UnifaiStack (UnifAI deployed another way) are not gated.
func (b *Base) stackGate(ctx context.Context, ns string) error {
	var st unifaiv1.UnifaiStack
	err := b.Get(ctx, types.NamespacedName{Namespace: ns, Name: unifaiv1.StackName}, &st)
	if apierrors.IsNotFound(err) {
		return nil
	}
	if err != nil {
		return err
	}
	if !meta.IsStatusConditionTrue(st.Status.Conditions, "Ready") {
		return fmt.Errorf("waiting for UnifaiStack %s/%s to be Ready", ns, unifaiv1.StackName)
	}
	return nil
}

// Handlers is what a kind implements; the generic loop handles finalizers, status and retries.
type Handlers struct {
	// Apply pushes the spec to UnifAI and fills the status; it returns a requeue delay (0 = periodic resync).
	Apply func(ctx context.Context) (time.Duration, error)
	// Delete removes the UnifAI object (nil = nothing to delete).
	Delete func(ctx context.Context) error
}

// run is the reconcile loop shared by every UnifAI object kind.
func (b *Base) run(ctx context.Context, obj unifaiv1.Object, h Handlers) (reconcile.Result, error) {
	logger := log.FromContext(ctx)
	st := obj.GetObjectStatus()

	if !obj.GetDeletionTimestamp().IsZero() {
		if !controllerutil.ContainsFinalizer(obj, Finalizer) {
			return reconcile.Result{}, nil
		}
		if h.Delete != nil {
			if err := h.Delete(ctx); err != nil {
				logger.Info("delete failed, retrying", "error", err.Error())
				orig := obj.DeepCopyObject().(client.Object)
				st.Phase, st.Message = "Deleting", unifai.Truncate("cannot delete (still referenced?): "+err.Error(), 500)
				_ = b.Status().Patch(ctx, obj, client.MergeFrom(orig))
				return reconcile.Result{RequeueAfter: 3 * retry}, nil
			}
		}
		controllerutil.RemoveFinalizer(obj, Finalizer)
		return reconcile.Result{}, b.Update(ctx, obj)
	}
	if !controllerutil.ContainsFinalizer(obj, Finalizer) {
		controllerutil.AddFinalizer(obj, Finalizer)
		if err := b.Update(ctx, obj); err != nil {
			return reconcile.Result{}, err
		}
	}
	// A permanent failure is retried when the spec changes, when the adopt annotation is added after a takeover
	// refusal, or at the periodic resync (the cause may be outside the spec, e.g. UnifAI configuration).
	if st.Phase == "Error" && st.ObservedGeneration == obj.GetGeneration() &&
		!(adopting(obj) && strings.Contains(st.Message, unifaiv1.AdoptAnnotation)) &&
		st.LastReconciled != nil && time.Since(st.LastReconciled.Time) < resync {
		return reconcile.Result{RequeueAfter: resync - time.Since(st.LastReconciled.Time)}, nil
	}

	// Status is written with a merge patch: no resourceVersion conflict can drop the ids of objects just created.
	orig := obj.DeepCopyObject().(client.Object)
	var requeue time.Duration
	err := b.stackGate(ctx, obj.GetNamespace())
	if err != nil && (st.Phase == "Completed" || st.Phase == "Failed") {
		return reconcile.Result{RequeueAfter: resync}, nil // finished one-shot runs do not depend on the stack
	}
	if err == nil {
		requeue, err = h.Apply(ctx)
	}
	now := metav1.Now()
	st.LastReconciled = &now
	var perm *PermanentError
	switch {
	case errors.As(err, &perm):
		st.Phase, st.Message, st.ObservedGeneration = "Error", unifai.Truncate(perm.Error(), 500), obj.GetGeneration()
		meta.SetStatusCondition(&st.Conditions, metav1.Condition{Type: "Ready", Status: metav1.ConditionFalse, Reason: "InvalidSpec",
			Message: st.Message, ObservedGeneration: obj.GetGeneration()})
		requeue = resync
	case err != nil:
		if st.Phase == "" || st.Phase == "Ready" {
			st.Phase = "Pending"
		}
		st.Message = unifai.Truncate(err.Error(), 500)
		meta.SetStatusCondition(&st.Conditions, metav1.Condition{Type: "Ready", Status: metav1.ConditionFalse, Reason: "Retrying",
			Message: st.Message, ObservedGeneration: obj.GetGeneration()})
		requeue = retry
	default:
		st.ObservedGeneration = obj.GetGeneration()
		status := metav1.ConditionFalse
		if st.Phase == "Ready" || st.Phase == "Completed" || st.Phase == "Suspended" {
			status = metav1.ConditionTrue
		}
		meta.SetStatusCondition(&st.Conditions, metav1.Condition{Type: "Ready", Status: status, Reason: strings.ReplaceAll(st.Phase, " ", ""),
			Message: st.Message, ObservedGeneration: obj.GetGeneration()})
		if requeue == 0 {
			requeue = resync
		}
	}
	if uerr := b.Status().Patch(ctx, obj, client.MergeFrom(orig)); uerr != nil {
		return reconcile.Result{}, uerr
	}
	if requeue == 0 {
		return reconcile.Result{}, nil
	}
	return reconcile.Result{RequeueAfter: requeue}, nil
}

func setReady(st *unifaiv1.ObjectStatus, phase, msg string) {
	st.Phase, st.Message = phase, unifai.Truncate(msg, 500)
}
