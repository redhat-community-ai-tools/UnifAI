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

// BundleVerify says how the bundle signature is checked: with a public key, or keyless (ADR-0578). Exactly one.
// +kubebuilder:validation:XValidation:rule="has(self.publicKeyRef) != has(self.keyless)",message="set exactly one of publicKeyRef or keyless"
type BundleVerify struct {
	// PEM public half of the signing key (for zuno, the Vault Transit key exported as
	// agents/zuno-platform-signer.pub): no access to Vault is needed. Checks the bundle content digest.
	// +optional
	PublicKeyRef *SecretKeySelector `json:"publicKeyRef,omitempty"`
	// Keyless cosign signature of the artifact manifest digest, checked offline against a Sigstore trusted root.
	// +optional
	Keyless *KeylessVerify `json:"keyless,omitempty"`
}

// KeylessVerify accepts an artifact signed by a CI workflow identity (Fulcio certificate + Rekor entry).
type KeylessVerify struct {
	// OIDC issuer of the signing certificate, e.g. https://token.actions.githubusercontent.com.
	// +kubebuilder:validation:MinLength=1
	Issuer string `json:"issuer"`
	// Regular expression the certificate subject (the workflow identity) must match; anchor it.
	// +kubebuilder:validation:MinLength=1
	SubjectRegExp string `json:"subjectRegExp"`
	// Sigstore trusted_root.json (Fulcio, Rekor and CT log keys), in a Secret of the bundle's namespace.
	TrustedRootRef SecretKeySelector `json:"trustedRootRef"`
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

// BundleMCP is the template of the MCP provider emitted for every task that declares allowed_tools: the
// bundle adds the Zuno headers (agent, task, effective classification, run id) to `config.additional_headers`,
// so the gateway behind it can apply that agent task's own tool declaration.
type BundleMCP struct {
	ConfigSpec `json:",inline"`
}

// UnifaiAgentBundleSpec maps one signed OKF agent bundle onto UnifAI objects.
// +kubebuilder:validation:XValidation:rule="!has(self.teamId) || !has(self.teamRef) || size(self.teamId) == 0 || size(self.teamRef) == 0",message="teamId and teamRef are exclusive"
// +kubebuilder:validation:XValidation:rule="!has(self.groupTeam) || !self.groupTeam || ((!has(self.teamId) || size(self.teamId) == 0) && (!has(self.teamRef) || size(self.teamRef) == 0))",message="groupTeam is exclusive with teamId and teamRef"
type UnifaiAgentBundleSpec struct {
	// Owner and team of the emitted objects.
	CommonSpec `json:",inline"`
	Source     BundleSource   `json:"source"`
	Verify     BundleVerify   `json:"verify"`
	Ceilings   BundleCeilings `json:"ceilings"`
	// How zuno.access.groups is honoured. Enforced (default) refuses a bundle declaring groups while UnifAI
	// cannot gate agent visibility by group; GatewayOnly emits it and relies on the gateways checking the
	// caller's JWT groups (ADR-0562 interim; a cutover gate for production).
	// +kubebuilder:validation:Enum=Enforced;GatewayOnly
	// +kubebuilder:default=Enforced
	// +optional
	Entitlement string `json:"entitlement,omitempty"`
	// GroupTeam emits an owned UnifaiTeam named agent-<bundle> whose members are the bundle's
	// zuno.access.groups (type group) and puts every emitted object in its workspace, so UnifAI's own
	// visibility restricts the agent to those groups. It satisfies the Enforced entitlement. Exclusive with
	// teamId and teamRef; the bundle must declare access groups.
	// +optional
	GroupTeam bool `json:"groupTeam,omitempty"`
	// ServePlaceholder serves a bundle whose OKF says zuno.status: placeholder (ADR-0007). By default such a
	// bundle stays Pending, "placeholder agent: not served", and no object is emitted (objects it emitted
	// before are removed).
	// +optional
	ServePlaceholder bool `json:"servePlaceholder,omitempty"`
	// RetrieveFirst makes every retriever-backed task agent search the retriever with the user's message
	// before the model reasons (the OKF graph shape retrieve_reason_respond always retrieves first). It sends
	// retrieve_first in the agent config, which only multiagent images that know that option accept: leave it
	// off for older stacks.
	// +optional
	RetrieveFirst bool      `json:"retrieveFirst,omitempty"`
	LLM           BundleLLM `json:"llm"`
	// MCP provider emitted per task that declares allowed_tools, carrying the Zuno headers. It is attached
	// before `providers`.
	// +optional
	MCP *BundleMCP `json:"mcp,omitempty"`
	// UnifaiProvider names (MCP servers) attached to the tasks that declare allowed_tools, shared by all
	// tasks and sent without the Zuno headers.
	// +kubebuilder:validation:MaxItems=64
	// +kubebuilder:validation:items:MaxLength=253
	// +kubebuilder:validation:XValidation:rule="self.all(p, p.matches('^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'))",message="providers are UnifaiProvider names (lower-case DNS labels)"
	// +optional
	Providers []string `json:"providers,omitempty"`
	// UnifaiRetriever name attached to the tasks that declare allowed_knowledge.
	// +kubebuilder:validation:XValidation:rule="self.matches('^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')",message="retriever is an UnifaiRetriever name (lower-case DNS label)"
	// +optional
	Retriever string `json:"retriever,omitempty"`
	// Extra custom_agent_node settings merged under every emitted agent (e.g. max_rounds, hitl_mode).
	// +kubebuilder:pruning:PreserveUnknownFields
	// +kubebuilder:validation:Type=object
	// +optional
	AgentConfig *runtime.RawExtension `json:"agentConfig,omitempty"`
	// Per-task classification override: C1, C2 or C3. It may only raise the bundle's level (ADR-0565).
	// +kubebuilder:validation:XValidation:rule="self.all(k, self[k] in ['C1', 'C2', 'C3'])",message="classification overrides are C1, C2 or C3"
	// +kubebuilder:validation:MaxProperties=256
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
	// Certificate subject that signed the artifact (keyless verification only).
	// +optional
	Signer string `json:"signer,omitempty"`
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
	// Display is the public sheet built from the admitted bundle (never from a field set by hand).
	// +optional
	Display *AgentDisplay `json:"display,omitempty"`
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
