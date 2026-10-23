package controller

import (
	"fmt"
	"reflect"
	"strings"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/recorder"

	"github.com/startxfr/unifai-operator/internal/unifai"
	"github.com/startxfr/unifai-operator/internal/validate"
)

// EventSource is the reporting controller of the Events the operator records.
const EventSource = "unifai-operator"

// PhaseDeleting is the phase of an object whose deletion is in progress.
const PhaseDeleting = "Deleting"

// PhaseReady is the phase of an object in sync with UnifAI.
const PhaseReady = "Ready"

// Terminal and error phases.
const (
	PhaseCompleted = "Completed"
	PhaseFailed    = "Failed"
	PhaseError     = "Error"
)

// UnifAI job statuses (RAG ingestion).
const (
	statusDone   = "DONE"
	statusFailed = "FAILED"
)

// +kubebuilder:rbac:groups=events.k8s.io,resources=events,verbs=create;patch

// warningPhases are the phases recorded as Warning Events.
var warningPhases = map[string]bool{PhaseError: true, PhaseFailed: true}

// recordPhase records an Event when an object moves to another phase (rec may be nil).
// Only transitions are recorded: a periodic resync in the same phase stays silent.
func recordPhase(rec recorder.EventRecorder, obj runtime.Object, from, to, msg string) {
	if to == "" || to == from {
		return
	}
	// Typed objects read from the API have no TypeMeta: the Go type name is the kind.
	phaseTransitions.WithLabelValues(reflect.TypeOf(obj).Elem().Name(), to).Inc()
	if rec == nil {
		return
	}
	typ := corev1.EventTypeNormal
	if warningPhases[to] {
		typ = corev1.EventTypeWarning
	}
	record(rec, obj, typ, strings.ReplaceAll(to, " ", ""), msg)
}

// recordDeleteFailed records a Warning Event the first time the UnifAI side of an object cannot be deleted.
func recordDeleteFailed(rec recorder.EventRecorder, obj runtime.Object, from, msg string) {
	if rec == nil || from == PhaseDeleting {
		return
	}
	record(rec, obj, corev1.EventTypeWarning, "DeleteFailed", msg)
}

func record(rec recorder.EventRecorder, obj runtime.Object, typ, reason, msg string) {
	// Event notes are limited to 1 kB; the message may hold API answers with format verbs.
	rec.Eventf(obj, nil, typ, reason, "Reconcile", "%s", unifai.Truncate(msg, 1000))
}

// ConditionSpecWarnings lists the static rules the spec breaks (R-304): reported now, refused at admission later.
const ConditionSpecWarnings = "SpecWarnings"

// specWarnings records the static rules the object breaks in its conditions, as a Warning Event when they change
// and in the unifai_operator_spec_warnings metric. Nothing is refused.
func specWarnings(rec recorder.EventRecorder, obj client.Object, conds *[]metav1.Condition) {
	kind := fmt.Sprintf("%T", obj)
	kind = kind[strings.LastIndex(kind, ".")+1:]
	vs := validate.Check(obj)
	if len(vs) == 0 {
		meta.RemoveStatusCondition(conds, ConditionSpecWarnings)
		specWarningsGauge.DeleteLabelValues(obj.GetNamespace(), kind, obj.GetName())
		return
	}
	msgs := make([]string, 0, len(vs))
	for _, v := range vs {
		msgs = append(msgs, v.String())
	}
	msg := unifai.Truncate("refused at admission in a later release: "+strings.Join(msgs, "; "), 1000)
	if prev := meta.FindStatusCondition(*conds, ConditionSpecWarnings); rec != nil && (prev == nil || prev.Message != msg) {
		record(rec, obj, corev1.EventTypeWarning, "SpecInvalid", msg)
	}
	meta.SetStatusCondition(conds, metav1.Condition{Type: ConditionSpecWarnings, Status: metav1.ConditionTrue,
		Reason: "InvalidSpec", Message: msg, ObservedGeneration: obj.GetGeneration()})
	specWarningsGauge.WithLabelValues(obj.GetNamespace(), kind, obj.GetName()).Set(float64(len(vs)))
}
