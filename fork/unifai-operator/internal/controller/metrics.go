package controller

import (
	"github.com/prometheus/client_golang/prometheus"
	"sigs.k8s.io/controller-runtime/pkg/metrics"
)

// Operator metrics, served with the controller-runtime ones on the manager metrics endpoint.
var (
	phaseTransitions = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "unifai_operator_phase_transitions_total",
		Help: "Phase changes of the objects reconciled by the operator, by kind and new phase.",
	}, []string{"kind", "phase"})
	stackReady = prometheus.NewGaugeVec(prometheus.GaugeOpts{
		Name: "unifai_operator_stack_ready",
		Help: "1 when the UnifaiStack of the namespace is Ready, 0 otherwise.",
	}, []string{"namespace"})
	helmApplySeconds = prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "unifai_operator_helm_apply_seconds",
		Help:    "Duration of the Helm install/upgrade of a stack release.",
		Buckets: []float64{1, 5, 15, 30, 60, 120, 300, 600},
	}, []string{"release", "result"})
	specWarningsGauge = prometheus.NewGaugeVec(prometheus.GaugeOpts{
		Name: "unifai_operator_spec_warnings",
		Help: "Static rules an object breaks (they will be refused at admission in a later release), by object.",
	}, []string{"namespace", "kind", "name"})
)

func init() {
	metrics.Registry.MustRegister(phaseTransitions, stackReady, helmApplySeconds, specWarningsGauge)
}
