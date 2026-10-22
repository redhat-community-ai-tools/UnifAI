package controller

import (
	"context"
	"time"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

const (
	// MetricsScraper is the ServiceAccount OLM creates in the operator namespace (CSV clusterPermissions, allowed to
	// GET /metrics) for the user-workload Prometheus, which cannot use a token file.
	MetricsScraper = "unifai-operator-metrics-scraper"
	// MetricsTokenSecret holds the scraper token referenced by the operator ServiceMonitor.
	MetricsTokenSecret = "unifai-operator-metrics-token"
)

// MetricsToken keeps the scraper token Secret of the operator ServiceMonitor. A token Secret shipped in the bundle
// could be created before OLM creates its ServiceAccount and be removed by the token controller, so the operator
// creates it once the ServiceAccount exists. Without that ServiceAccount (canary, make deploy) it does nothing.
type MetricsToken struct {
	Client client.Client
	// Reader reads without the informer cache (no cluster-wide Secret or ServiceAccount informer).
	Reader    client.Reader
	Namespace string
}

// NeedLeaderElection makes only the leader write the Secret.
func (m *MetricsToken) NeedLeaderElection() bool { return true }

// Start checks every minute until the Secret exists, then every 10 minutes (it is recreated if deleted).
func (m *MetricsToken) Start(ctx context.Context) error {
	if m.Namespace == "" {
		return nil
	}
	for {
		every := time.Minute
		ok, err := m.ensure(ctx)
		if err != nil {
			log.FromContext(ctx).Error(err, "metrics scraper token")
		} else if ok {
			every = 10 * time.Minute
		}
		select {
		case <-ctx.Done():
			return nil
		case <-time.After(every):
		}
	}
}

// ensure creates the token Secret when the scraper ServiceAccount exists; it reports whether the Secret exists.
func (m *MetricsToken) ensure(ctx context.Context) (bool, error) {
	sa := &corev1.ServiceAccount{}
	if err := m.Reader.Get(ctx, types.NamespacedName{Namespace: m.Namespace, Name: MetricsScraper}, sa); err != nil {
		return false, client.IgnoreNotFound(err)
	}
	err := m.Reader.Get(ctx, types.NamespacedName{Namespace: m.Namespace, Name: MetricsTokenSecret}, &corev1.Secret{})
	if err == nil || !apierrors.IsNotFound(err) {
		return err == nil, err
	}
	secret := &corev1.Secret{
		ObjectMeta: metav1.ObjectMeta{Name: MetricsTokenSecret, Namespace: m.Namespace,
			Annotations: map[string]string{corev1.ServiceAccountNameKey: MetricsScraper},
			Labels:      map[string]string{"app.kubernetes.io/name": "unifai-operator"}},
		Type: corev1.SecretTypeServiceAccountToken,
	}
	if err := m.Client.Create(ctx, secret); err != nil && !apierrors.IsAlreadyExists(err) {
		return false, err
	}
	log.FromContext(ctx).Info("created the metrics scraper token Secret", "namespace", m.Namespace)
	return true, nil
}
