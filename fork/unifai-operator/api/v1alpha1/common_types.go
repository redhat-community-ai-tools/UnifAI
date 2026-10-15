package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

// AdoptAnnotation lets a CR take over an object that already exists in UnifAI under the same name.
const AdoptAnnotation = "unifai.startx.fr/adopt"

// SecretKeySelector selects a key of a Secret in the CR's namespace.
type SecretKeySelector struct {
	Name string `json:"name"`
	Key  string `json:"key"`
}

// SecretRef injects a Secret value at a dotted path of the UnifAI config.
type SecretRef struct {
	// Dotted path in the config, e.g. `api_key` or `headers.token`.
	Path         string            `json:"path"`
	SecretKeyRef SecretKeySelector `json:"secretKeyRef"`
}

// CommonSpec is shared by every UnifAI object kind.
type CommonSpec struct {
	// UnifAI user owning the object (workspace identity).
	// +kubebuilder:default=admin
	// +optional
	Owner string `json:"owner,omitempty"`
	// Team workspace to use instead of the user's personal one.
	// +optional
	TeamID string `json:"teamId,omitempty"`
	// Name in UnifAI (defaults to metadata.name).
	// +optional
	UnifaiName string `json:"unifaiName,omitempty"`
}

// ConfigSpec carries an UnifAI cfg_dict. `$ref:<kind>/<name>` strings reference other UnifAI objects
// (kind = llm|provider|tool|retriever|sandbox|condition|agent) and `$rid:<kind>/<name>` yields the bare id.
type ConfigSpec struct {
	// +kubebuilder:pruning:PreserveUnknownFields
	// +kubebuilder:validation:Type=object
	// +optional
	Config *runtime.RawExtension `json:"config,omitempty"`
	// +optional
	SecretRefs []SecretRef `json:"secretRefs,omitempty"`
}

// ObjectStatus is the status of every UnifAI object kind.
type ObjectStatus struct {
	// Ready, Error, Pending, Running, Completed, Failed, Submitted, Suspended.
	// +optional
	Phase string `json:"phase,omitempty"`
	// +optional
	Message string `json:"message,omitempty"`
	// +optional
	ObservedGeneration int64 `json:"observedGeneration,omitempty"`
	// +optional
	LastReconciled *metav1.Time `json:"lastReconciled,omitempty"`
	// Truncated SHA-256 of the resolved spec last pushed to UnifAI.
	// +optional
	Hash string `json:"hash,omitempty"`
	// Id of the UnifAI library resource.
	// +optional
	RID string `json:"rid,omitempty"`
	// +optional
	BlueprintID string `json:"blueprintId,omitempty"`
	// +optional
	ScheduleID string `json:"scheduleId,omitempty"`
	// +optional
	TemplateID string `json:"templateId,omitempty"`
	// +optional
	SessionID string `json:"sessionId,omitempty"`
	// Chat transcript (truncated JSON).
	// +optional
	Result string `json:"result,omitempty"`
	// RAG pipeline dispatch response (truncated JSON).
	// +optional
	Response string `json:"response,omitempty"`
	// +optional
	Conditions []metav1.Condition `json:"conditions,omitempty"`
}

// Object is implemented by every UnifAI object kind (not by UnifaiStack).
// +kubebuilder:object:generate=false
type Object interface {
	client.Object
	GetCommon() *CommonSpec
	GetObjectStatus() *ObjectStatus
}

// ResourceObject is a kind stored in the UnifAI `resources` collection.
// +kubebuilder:object:generate=false
type ResourceObject interface {
	Object
	// Category is the UnifAI resource category (llms, providers, tools, conditions, retrievers, sandboxes, nodes).
	Category() string
	GetType() string
	GetConfigSpec() *ConfigSpec
}
