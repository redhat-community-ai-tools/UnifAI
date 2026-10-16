package stack

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"strings"

	appsv1 "k8s.io/api/apps/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/types"
	utilyaml "k8s.io/apimachinery/pkg/util/yaml"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/yaml"
)

type ctrlObject = client.Object

// ManifestObject is the identity of one object of a rendered release.
type ManifestObject struct {
	Kind, Name string
	// Claim templates of a StatefulSet, with its replicas (for Delete-policy PVC cleanup).
	ClaimTemplates []string
	Replicas       int
}

// ParseManifest lists the objects of a Helm release manifest.
func ParseManifest(manifest string) ([]ManifestObject, error) {
	reader := utilyaml.NewYAMLReader(bufio.NewReader(strings.NewReader(manifest)))
	var out []ManifestObject
	for {
		doc, err := reader.Read()
		if err == io.EOF {
			return out, nil
		}
		if err != nil {
			return nil, err
		}
		var o struct {
			Kind     string `json:"kind"`
			Metadata struct {
				Name string `json:"name"`
			} `json:"metadata"`
			Spec struct {
				Replicas             *int `json:"replicas"`
				VolumeClaimTemplates []struct {
					Metadata struct {
						Name string `json:"name"`
					} `json:"metadata"`
				} `json:"volumeClaimTemplates"`
			} `json:"spec"`
		}
		if err := yaml.Unmarshal(doc, &o); err != nil || o.Kind == "" {
			continue
		}
		mo := ManifestObject{Kind: o.Kind, Name: o.Metadata.Name, Replicas: 1}
		if o.Spec.Replicas != nil {
			mo.Replicas = *o.Spec.Replicas
		}
		for _, t := range o.Spec.VolumeClaimTemplates {
			mo.ClaimTemplates = append(mo.ClaimTemplates, t.Metadata.Name)
		}
		out = append(out, mo)
	}
}

// WorkloadsReady checks the Deployments and StatefulSets of a release; it returns "" when all are ready,
// else a short description of what is not.
func WorkloadsReady(ctx context.Context, c client.Client, ns string, objs []ManifestObject) (string, error) {
	var waiting []string
	for _, o := range objs {
		key := types.NamespacedName{Namespace: ns, Name: o.Name}
		switch o.Kind {
		case "Deployment":
			var d appsv1.Deployment
			if err := c.Get(ctx, key, &d); err != nil {
				if apierrors.IsNotFound(err) {
					waiting = append(waiting, "deployment/"+o.Name+" missing")
					continue
				}
				return "", err
			}
			want := int32(1)
			if d.Spec.Replicas != nil {
				want = *d.Spec.Replicas
			}
			// Same rule as `kubectl rollout status`: no pod of an older revision may remain.
			if d.Status.ObservedGeneration < d.Generation || d.Status.UpdatedReplicas < want || d.Status.AvailableReplicas < want ||
				d.Status.Replicas > d.Status.UpdatedReplicas {
				waiting = append(waiting, fmt.Sprintf("deployment/%s %d/%d", o.Name, d.Status.AvailableReplicas, want))
			}
		case "StatefulSet":
			var s appsv1.StatefulSet
			if err := c.Get(ctx, key, &s); err != nil {
				if apierrors.IsNotFound(err) {
					waiting = append(waiting, "statefulset/"+o.Name+" missing")
					continue
				}
				return "", err
			}
			want := int32(1)
			if s.Spec.Replicas != nil {
				want = *s.Spec.Replicas
			}
			if s.Status.ObservedGeneration < s.Generation || s.Status.ReadyReplicas < want ||
				(s.Status.UpdateRevision != "" && s.Status.CurrentRevision != s.Status.UpdateRevision) {
				waiting = append(waiting, fmt.Sprintf("statefulset/%s %d/%d", o.Name, s.Status.ReadyReplicas, want))
			}
		}
	}
	return strings.Join(waiting, ", "), nil
}
