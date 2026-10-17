package v1alpha1

import (
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

// AgentBundleLabel marks the objects an UnifaiAgentBundle emits (value: the bundle name).
const AgentBundleLabel = "unifai.startx.fr/agent-bundle"

// OCIBundleSource pins a signed OKF bundle in an OCI registry.
type OCIBundleSource struct {
	// Reference pinned by digest, e.g. quay.io/zuno/okf-tekos@sha256:<64 hex>. Tags are refused.
	// +kubebuilder:validation:XValidation:rule="self.matches('^[^@]+@sha256:[a-f0-9]{64}$')",message="reference must be pinned by a sha256 digest"
	Reference string `json:"reference"`
	// kubernetes.io/dockerconfigjson Secret for a private repository (anonymous pull when unset).
	// +optional
	PullSecretRef *corev1.LocalObjectReference `json:"pullSecretRef,omitempty"`
}

// BundleSource says where the bundle comes from.
type BundleSource struct {
	OCI OCIBundleSource `json:"oci"`
}

// BundleVerify says how the bundle signature is checked. The key is the PEM public half of the signing key
// (for zuno, the Vault Transit key exported as agents/zuno-platform-signer.pub): no access to Vault is needed.
type BundleVerify struct {
	PublicKeyRef SecretKeySelector `json:"publicKeyRef"`
}

// BundleCeilings bound what a bundle may declare (ADR-0564 clause 3): a bundle can narrow, never widen.
// They are reviewed in Git with the CR, independently of the bundle content.
type BundleCeilings struct {
	// Tool names the bundle's tasks may declare in allowed_tools.
	// +optional
	ToolCapabilities []string `json:"toolCapabilities,omitempty"`
	// Knowledge domains the bundle's tasks may declare in allowed_knowledge.
	// +optional
	KnowledgeDomains []string `json:"knowledgeDomains,omitempty"`
	// The least restrictive classification the bundle may run at (C1 < C2 < C3): a bundle declaring a lower
	// level than this would allow model classes the CR's reviewers did not accept.
	// +kubebuilder:validation:Enum=C1;C2;C3
	MinClassification string `json:"minClassification"`
}

// BundleLLM is the template of the LLM emitted for every task: the bundle adds the Zuno headers
// (agent, task, effective classification, run id) to `config.default_headers`.
type BundleLLM struct {
	// +kubebuilder:validation:Enum=openai_compatible
	// +kubebuilder:default=openai_compatible
	// +optional
	Type       string `json:"type,omitempty"`
	ConfigSpec `json:",inline"`
}

// UnifaiAgentBundleSpec maps one signed OKF agent bundle onto UnifAI objects.
type UnifaiAgentBundleSpec struct {
	// Owner and team of the emitted objects.
	CommonSpec `json:",inline"`
	Source     BundleSource `json:"source"`
	Verify     BundleVerify `json:"verify"`
	Ceilings   BundleCeilings `json:"ceilings"`
	// How zuno.access.groups is honoured. Enforced (default) refuses a bundle declaring groups while UnifAI
	// cannot gate agent visibility by group; GatewayOnly emits it and relies on the gateways checking the
	// caller's JWT groups (ADR-0562 interim; a cutover gate for production).
	// +kubebuilder:validation:Enum=Enforced;GatewayOnly
	// +kubebuilder:default=Enforced
	// +optional
	Entitlement string       `json:"entitlement,omitempty"`
	LLM        BundleLLM    `json:"llm"`
	// UnifaiProvider names (MCP servers) attached to the tasks that declare allowed_tools.
	// +optional
	Providers []string `json:"providers,omitempty"`
	// UnifaiRetriever name attached to the tasks that declare allowed_knowledge.
	// +optional
	Retriever string `json:"retriever,omitempty"`
	// Extra custom_agent_node settings merged under every emitted agent (e.g. max_rounds, hitl_mode).
	// +kubebuilder:pruning:PreserveUnknownFields
	// +kubebuilder:validation:Type=object
	// +optional
	AgentConfig *runtime.RawExtension `json:"agentConfig,omitempty"`
	// Per-task classification override: C1, C2 or C3. It may only raise the bundle's level (ADR-0565).
	// +optional
	ClassificationOverrides map[string]string `json:"classificationOverrides,omitempty"`
}

// BundleTaskStatus is what was emitted for one task.
type BundleTaskStatus struct {
	Name           string `json:"name"`
	Classification string `json:"classification"`
	Workflow       string `json:"workflow"`
}

// UnifaiAgentBundleStatus reports verification and the emitted objects.
type UnifaiAgentBundleStatus struct {
	// Ready, Error, Pending.
	// +optional
	Phase string `json:"phase,omitempty"`
	// +optional
	Message string `json:"message,omitempty"`
	// +optional
	ObservedGeneration int64 `json:"observedGeneration,omitempty"`
	// +optional
	LastReconciled *metav1.Time `json:"lastReconciled,omitempty"`
	// Manifest digest that was pulled.
	// +optional
	ResolvedDigest string `json:"resolvedDigest,omitempty"`
	// okf_version of the bundle.
	// +optional
	OKFVersion string `json:"okfVersion,omitempty"`
	// OKF content digest that the signature covers.
	// +optional
	BundleDigest string `json:"bundleDigest,omitempty"`
	// +optional
	Verified bool `json:"verified,omitempty"`
	// zuno.name of the bundle.
	// +optional
	Agent string `json:"agent,omitempty"`
	// +optional
	Tasks []BundleTaskStatus `json:"tasks,omitempty"`
	// Emitted objects, as <Kind>/<name>.
	// +optional
	Children []string `json:"children,omitempty"`
	// OKF content with no UnifAI equivalent.
	// +optional
	Unmapped []string `json:"unmapped,omitempty"`
	// +optional
	Conditions []metav1.Condition `json:"conditions,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=uab,categories=unifai
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Agent",type=string,JSONPath=`.status.agent`
// +kubebuilder:printcolumn:name="Verified",type=boolean,JSONPath=`.status.verified`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// UnifaiAgentBundle turns a signed Zuno OKF agent bundle into UnifAI LLMs, agents, a condition and workflows.
type UnifaiAgentBundle struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiAgentBundleSpec   `json:"spec"`
	Status UnifaiAgentBundleStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiAgentBundleList contains a list of UnifaiAgentBundle.
type UnifaiAgentBundleList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiAgentBundle `json:"items"`
}

func init() {
	SchemeBuilder.Register(&UnifaiAgentBundle{}, &UnifaiAgentBundleList{})
}
