package stack

import (
	"github.com/prometheus/client_golang/prometheus"
	"sigs.k8s.io/controller-runtime/pkg/metrics"
)

// keycloakRepairs counts the restarts of a managed Keycloak left unready for too long (Keycloak.Repair).
var keycloakRepairs = prometheus.NewCounterVec(prometheus.CounterOpts{
	Name: "unifai_operator_keycloak_repairs_total",
	Help: "Restarts of a managed Keycloak left unready for too long, by namespace.",
}, []string{"namespace"})

func init() {
	metrics.Registry.MustRegister(keycloakRepairs)
}
