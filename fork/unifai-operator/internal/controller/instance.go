package controller

import (
	"os"
	"strings"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/apimachinery/pkg/runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// InstanceLabel assigns an UnifAI custom resource to one operator instance. Objects without it belong to the
// default instance (the one installed by OLM); a canary instance (OPERATOR_INSTANCE=canary, used to test a
// release candidate) only sees objects labelled with its name, and the default instance never sees those.
const InstanceLabel = "unifai.startx.fr/operator-instance"

// Instance is the name of this operator instance ("" = default).
var Instance = os.Getenv("OPERATOR_INSTANCE")

// OperatorVersion is the version of this operator build (set at link time), reported in UnifaiStack status.
var OperatorVersion = "dev"

// InstanceSelector selects the custom resources this instance reconciles.
func InstanceSelector() labels.Selector {
	if Instance == "" {
		sel, _ := labels.Parse("!" + InstanceLabel)
		return sel
	}
	return labels.SelectorFromSet(labels.Set{InstanceLabel: Instance})
}

// OwnedByInstance reports whether this instance reconciles the object.
func OwnedByInstance(o metav1.Object) bool { return o.GetLabels()[InstanceLabel] == Instance }

// CacheByObject restricts the informers of every unifai.startx.fr kind to this instance's objects, so a
// controller never receives events (nor cached reads) for objects of another instance.
func CacheByObject(scheme *runtime.Scheme) map[client.Object]cache.ByObject {
	out := map[client.Object]cache.ByObject{}
	sel := InstanceSelector()
	for gvk := range scheme.AllKnownTypes() {
		if gvk.GroupVersion() != unifaiv1.GroupVersion || strings.HasSuffix(gvk.Kind, "List") {
			continue
		}
		obj, err := scheme.New(gvk)
		if err != nil {
			continue
		}
		if co, ok := obj.(client.Object); ok {
			out[co] = cache.ByObject{Label: sel}
		}
	}
	return out
}
