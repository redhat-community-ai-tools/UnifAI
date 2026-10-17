package stack

import (
	"context"
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"
)

func TestKeycloakRepair(t *testing.T) {
	now := time.Date(2026, 10, 17, 12, 0, 0, 0, time.UTC)
	pod := func(ready bool, runningFor time.Duration) *corev1.Pod {
		return &corev1.Pod{
			ObjectMeta: metav1.ObjectMeta{Namespace: "ns", Name: KeycloakName + "-0"},
			Status: corev1.PodStatus{Phase: corev1.PodRunning, ContainerStatuses: []corev1.ContainerStatus{{
				Name: "keycloak", Ready: ready,
				State: corev1.ContainerState{Running: &corev1.ContainerStateRunning{StartedAt: metav1.NewTime(now.Add(-runningFor))}},
			}}},
		}
	}
	cases := []struct {
		name       string
		pod        *corev1.Pod
		lastRepair string
		want       bool
	}{
		{"unready for 20 min", pod(false, 20*time.Minute), "", true},
		{"unready for 2 min", pod(false, 2*time.Minute), "", false},
		{"ready", pod(true, 2*time.Hour), "", false},
		{"repaired 5 min ago", pod(false, 20*time.Minute), now.Add(-5 * time.Minute).Format(time.RFC3339), false},
		{"repaired 1 h ago", pod(false, 20*time.Minute), now.Add(-time.Hour).Format(time.RFC3339), true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			kc := newU(GVKKeycloak, "ns", KeycloakName)
			if tc.lastRepair != "" {
				kc.SetAnnotations(map[string]string{repairAnnotation: tc.lastRepair})
			}
			scheme := runtime.NewScheme()
			_ = corev1.AddToScheme(scheme)
			scheme.AddKnownTypeWithName(GVKKeycloak, &unstructured.Unstructured{})
			c := fake.NewClientBuilder().WithScheme(scheme).WithObjects(tc.pod, kc).Build()
			k := &Keycloak{Client: c}
			got, err := k.Repair(context.Background(), kc, now)
			if err != nil {
				t.Fatal(err)
			}
			if got != tc.want {
				t.Fatalf("repaired=%v, want %v", got, tc.want)
			}
			err = c.Get(context.Background(), client.ObjectKeyFromObject(tc.pod), &corev1.Pod{})
			if deleted := apierrors.IsNotFound(err); deleted != tc.want {
				t.Fatalf("pod deleted=%v, want %v", deleted, tc.want)
			}
		})
	}
}
