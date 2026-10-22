package controller

import (
	"reflect"
	"strings"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"sigs.k8s.io/controller-runtime/pkg/recorder"

	"github.com/startxfr/unifai-operator/internal/unifai"
)

// EventSource is the reporting controller of the Events the operator records.
const EventSource = "unifai-operator"

// +kubebuilder:rbac:groups=events.k8s.io,resources=events,verbs=create;patch

// warningPhases are the phases recorded as Warning Events.
var warningPhases = map[string]bool{"Error": true, "Failed": true}

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
	if rec == nil || from == "Deleting" {
		return
	}
	record(rec, obj, corev1.EventTypeWarning, "DeleteFailed", msg)
}

func record(rec recorder.EventRecorder, obj runtime.Object, typ, reason, msg string) {
	// Event notes are limited to 1 kB; the message may hold API answers with format verbs.
	rec.Eventf(obj, nil, typ, reason, "Reconcile", "%s", unifai.Truncate(msg, 1000))
}
