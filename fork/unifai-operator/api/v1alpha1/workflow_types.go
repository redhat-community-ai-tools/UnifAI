package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

// UnifaiWorkflowSpec defines an agentic workflow (UnifAI blueprint).
// +kubebuilder:validation:XValidation:rule="!has(self.teamId) || !has(self.teamRef) || size(self.teamId) == 0 || size(self.teamRef) == 0",message="teamId and teamRef are exclusive"
// +kubebuilder:validation:XValidation:rule="!has(self.display) || !has(self.display.icon) || size(self.display.icon) == 0 || self.display.icon.matches('^[a-z0-9-]+$')",message="display.icon is made of lower-case letters, digits and hyphens"
// +kubebuilder:validation:XValidation:rule="!has(self.display) || !has(self.display.color) || size(self.display.color) == 0 || self.display.color.matches('^(#[0-9a-fA-F]{6}|[a-z]+)$')",message="display.color is a CSS colour keyword or #rrggbb"
type UnifaiWorkflowSpec struct {
	CommonSpec `json:",inline"`
	// +optional
	Description string `json:"description,omitempty"`
	// BlueprintDraft: nodes, conditions, plan... Library objects are referenced with `$ref:<kind>/<name>`
	// (node entries without config are expanded from the library) and `$rid:<kind>/<name>` in the plan.
	// +kubebuilder:pruning:PreserveUnknownFields
	// +kubebuilder:validation:Type=object
	Blueprint runtime.RawExtension `json:"blueprint"`
	// +optional
	SecretRefs []SecretRef `json:"secretRefs,omitempty"`
	// Display is the descriptive sheet stored in the blueprint's metadata, for a UI that shows one entry per
	// workflow. Public fields only; the UnifAI API refuses anything else.
	// +optional
	Display *AgentDisplay `json:"display,omitempty"`
}

// AgentDisplay is the public, descriptive sheet of an agent or workflow. It never carries a prompt, a tool or
// knowledge list, an access group, a digest or a signature.
type AgentDisplay struct {
	// Agent is the agent's stable name, the key of its entry (/agents/<agent>).
	// +optional
	Agent string `json:"agent,omitempty"`
	// +optional
	Title string `json:"title,omitempty"`
	// +optional
	DisplayName string `json:"displayName,omitempty"`
	// +optional
	Description string `json:"description,omitempty"`
	// +optional
	TileDescription string `json:"tileDescription,omitempty"`
	// +optional
	Maintainer string `json:"maintainer,omitempty"`
	// Lifecycle state, such as active or placeholder.
	// +optional
	State string `json:"state,omitempty"`
	// Classification ceiling.
	// +optional
	Classification string `json:"classification,omitempty"`
	// Short keyword for an icon, lower case letters, digits and hyphens.
	// +optional
	Icon string `json:"icon,omitempty"`
	// A CSS color keyword or #rrggbb.
	// +optional
	Color string `json:"color,omitempty"`
	// +optional
	Tasks []DisplayTask `json:"tasks,omitempty"`
}

// DisplayTask is the public name of one task.
type DisplayTask struct {
	Name string `json:"name"`
	// +optional
	Title string `json:"title,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=uwf,categories=unifai
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="BlueprintId",type=string,JSONPath=`.status.blueprintId`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// UnifaiWorkflow is an UnifAI agentic workflow (blueprint).
type UnifaiWorkflow struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiWorkflowSpec `json:"spec"`
	Status ObjectStatus       `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiWorkflowList contains a list of UnifaiWorkflow.
type UnifaiWorkflowList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiWorkflow `json:"items"`
}

func (o *UnifaiWorkflow) GetCommon() *CommonSpec         { return &o.Spec.CommonSpec }
func (o *UnifaiWorkflow) GetObjectStatus() *ObjectStatus { return &o.Status }

// ScheduleDefinition mirrors UnifAI's ScheduleDefinition: exactly one of interval or cron_expression.
// +kubebuilder:validation:XValidation:rule="has(self.interval) != has(self.cron_expression)",message="set exactly one of interval or cron_expression"
// +kubebuilder:validation:XValidation:rule="!has(self.start_at) || !has(self.end_at) || !self.start_at.matches('^\\\\d{4}-\\\\d{2}-\\\\d{2}T\\\\d{2}:\\\\d{2}:\\\\d{2}(\\\\.\\\\d+)?(Z|[+-]\\\\d{2}:\\\\d{2})$') || !self.end_at.matches('^\\\\d{4}-\\\\d{2}-\\\\d{2}T\\\\d{2}:\\\\d{2}:\\\\d{2}(\\\\.\\\\d+)?(Z|[+-]\\\\d{2}:\\\\d{2})$') || timestamp(self.start_at) < timestamp(self.end_at)",message="end_at is after start_at"
type ScheduleDefinition struct {
	// ISO-8601 duration, minimum PT1M.
	// +kubebuilder:validation:XValidation:rule="self.matches('^P(T(\\\\d+H)?(\\\\d+M)?(\\\\d+S)?|\\\\d+D(T(\\\\d+H)?(\\\\d+M)?(\\\\d+S)?)?)$') && !self.matches('^P(0+D)?(T(0+H)?(0+M)?(0*[0-5]?[0-9]S)?)?$')",message="interval is an ISO-8601 duration of at least PT1M"
	// +kubebuilder:validation:MaxLength=64
	// +optional
	Interval string `json:"interval,omitempty"`
	// 5-field cron expression.
	// +kubebuilder:validation:XValidation:rule="self.matches('^\\\\s*\\\\S+(\\\\s+\\\\S+){4}\\\\s*$')",message="cron_expression has 5 fields"
	// +kubebuilder:validation:MaxLength=64
	// +optional
	CronExpression string `json:"cron_expression,omitempty"`
	// +optional
	Timezone string `json:"timezone,omitempty"`
	// +kubebuilder:validation:Enum=skip;buffer_one;cancel_other
	// +optional
	OverlapPolicy string `json:"overlap_policy,omitempty"`
	// +kubebuilder:validation:MaxLength=64
	// +optional
	StartAt string `json:"start_at,omitempty"`
	// +kubebuilder:validation:MaxLength=64
	// +optional
	EndAt string `json:"end_at,omitempty"`
	// +kubebuilder:validation:XValidation:rule="self >= 1",message="remaining_actions is at least 1"
	// +optional
	RemainingActions *int `json:"remaining_actions,omitempty"`
}

// UnifaiScheduleSpec defines a scheduled run of a workflow.
// +kubebuilder:validation:XValidation:rule="!has(self.teamId) || !has(self.teamRef) || size(self.teamId) == 0 || size(self.teamRef) == 0",message="teamId and teamRef are exclusive"
type UnifaiScheduleSpec struct {
	CommonSpec `json:",inline"`
	// UnifAI workflow (blueprint) name.
	Workflow string `json:"workflow"`
	// Workflow inputs; `user_prompt` is required by UnifAI.
	// +kubebuilder:validation:XValidation:rule="'user_prompt' in self",message="inputs needs user_prompt"
	Inputs map[string]string `json:"inputs"`
	// Pause the schedule.
	// +optional
	Suspend  bool               `json:"suspend,omitempty"`
	Schedule ScheduleDefinition `json:"schedule"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=usch,categories=unifai
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Workflow",type=string,JSONPath=`.spec.workflow`
// +kubebuilder:printcolumn:name="ScheduleId",type=string,JSONPath=`.status.scheduleId`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// UnifaiSchedule is a scheduled workflow (Temporal schedule).
type UnifaiSchedule struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiScheduleSpec `json:"spec"`
	Status ObjectStatus       `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiScheduleList contains a list of UnifaiSchedule.
type UnifaiScheduleList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiSchedule `json:"items"`
}

func (o *UnifaiSchedule) GetCommon() *CommonSpec         { return &o.Spec.CommonSpec }
func (o *UnifaiSchedule) GetObjectStatus() *ObjectStatus { return &o.Status }

// UnifaiTemplateSpec defines a catalog template (owner must be an UnifAI admin).
// +kubebuilder:validation:XValidation:rule="!has(self.teamId) || !has(self.teamRef) || size(self.teamId) == 0 || size(self.teamRef) == 0",message="teamId and teamRef are exclusive"
type UnifaiTemplateSpec struct {
	CommonSpec `json:",inline"`
	// BlueprintDraft with inline resources; secrets are PLACEHOLDER_* values listed in placeholders.
	// +kubebuilder:pruning:PreserveUnknownFields
	// +kubebuilder:validation:Type=object
	Draft runtime.RawExtension `json:"draft"`
	// +kubebuilder:pruning:PreserveUnknownFields
	// +kubebuilder:validation:Type=object
	// +optional
	Placeholders *runtime.RawExtension `json:"placeholders,omitempty"`
	// +kubebuilder:pruning:PreserveUnknownFields
	// +kubebuilder:validation:Type=object
	// +optional
	Metadata *runtime.RawExtension `json:"metadata,omitempty"`
	// +optional
	SecretRefs []SecretRef `json:"secretRefs,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=utpl,categories=unifai
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="TemplateId",type=string,JSONPath=`.status.templateId`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// UnifaiTemplate is an UnifAI catalog template (no update API: changes delete and recreate it).
type UnifaiTemplate struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiTemplateSpec `json:"spec"`
	Status ObjectStatus       `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiTemplateList contains a list of UnifaiTemplate.
type UnifaiTemplateList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiTemplate `json:"items"`
}

func (o *UnifaiTemplate) GetCommon() *CommonSpec         { return &o.Spec.CommonSpec }
func (o *UnifaiTemplate) GetObjectStatus() *ObjectStatus { return &o.Status }

// UnifaiChatSpec defines a one-shot chat: a session on the workflow with one prompt.
// +kubebuilder:validation:XValidation:rule="self == oldSelf",message="UnifaiChat is a one-shot run: spec is immutable, create a new one"
// +kubebuilder:validation:XValidation:rule="!has(self.teamId) || !has(self.teamRef) || size(self.teamId) == 0 || size(self.teamRef) == 0",message="teamId and teamRef are exclusive"
type UnifaiChatSpec struct {
	CommonSpec `json:",inline"`
	// UnifAI workflow (blueprint) name.
	Workflow string `json:"workflow"`
	// +kubebuilder:validation:XValidation:rule="size(self.trim()) > 0",message="prompt is not empty"
	Prompt string `json:"prompt"`
	// Session title (defaults to metadata.name).
	// +optional
	Title string `json:"title,omitempty"`
	// +optional
	HITL bool `json:"hitl,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=uchat,categories=unifai
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Workflow",type=string,JSONPath=`.spec.workflow`
// +kubebuilder:printcolumn:name="Session",type=string,JSONPath=`.status.sessionId`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// UnifaiChat runs one prompt on a workflow; the transcript lands in status.result.
type UnifaiChat struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiChatSpec `json:"spec"`
	Status ObjectStatus   `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiChatList contains a list of UnifaiChat.
type UnifaiChatList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiChat `json:"items"`
}

func (o *UnifaiChat) GetCommon() *CommonSpec         { return &o.Spec.CommonSpec }
func (o *UnifaiChat) GetObjectStatus() *ObjectStatus { return &o.Status }

// ConfigMapKeySelector selects a key of a ConfigMap in the CR's namespace.
type ConfigMapKeySelector struct {
	Name string `json:"name"`
	Key  string `json:"key"`
}

// DocumentSource is where a document's content comes from (exactly one).
// +kubebuilder:validation:XValidation:rule="(has(self.inline) ? 1 : 0) + (has(self.url) ? 1 : 0) + (has(self.configMapKeyRef) ? 1 : 0) == 1",message="set exactly one of inline, url or configMapKeyRef"
type DocumentSource struct {
	// +optional
	Inline string `json:"inline,omitempty"`
	// +kubebuilder:validation:MaxLength=2048
	// +kubebuilder:validation:XValidation:rule="isURL(self) && (self.startsWith('http://') || self.startsWith('https://')) && size(url(self).getHostname()) > 0",message="document urls are http(s) URLs"
	// +optional
	URL string `json:"url,omitempty"`
	// +optional
	ConfigMapKeyRef *ConfigMapKeySelector `json:"configMapKeyRef,omitempty"`
}

// RAGDocument is one document to ingest.
type RAGDocument struct {
	// File name with a supported extension (pdf, docx, md, pptx).
	// +kubebuilder:validation:MaxLength=255
	// +kubebuilder:validation:XValidation:rule="self.matches('(?i)\\\\.(pdf|docx|md|pptx)$')",message="document names end in .pdf, .docx, .md or .pptx"
	Name string `json:"name"`
	// +optional
	Tags []string `json:"tags,omitempty"`
	// +kubebuilder:pruning:PreserveUnknownFields
	// +kubebuilder:validation:Type=object
	// +optional
	Metadata *runtime.RawExtension `json:"metadata,omitempty"`
	Source   DocumentSource        `json:"source"`
}

// UnifaiRAGPipelineSpec declares documents to ingest through the RAG data pipeline.
// +kubebuilder:validation:XValidation:rule="!has(self.teamId) || !has(self.teamRef) || size(self.teamId) == 0 || size(self.teamRef) == 0",message="teamId and teamRef are exclusive"
type UnifaiRAGPipelineSpec struct {
	CommonSpec `json:",inline"`
	// +optional
	SkipValidation bool `json:"skipValidation,omitempty"`
	// +kubebuilder:validation:MinItems=1
	// +kubebuilder:validation:MaxItems=100
	// +listType=map
	// +listMapKey=name
	Documents []RAGDocument `json:"documents"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=urag,categories=unifai
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// UnifaiRAGPipeline uploads documents and dispatches the document pipeline (chunk, embed, store in Qdrant).
type UnifaiRAGPipeline struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiRAGPipelineSpec `json:"spec"`
	Status ObjectStatus          `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiRAGPipelineList contains a list of UnifaiRAGPipeline.
type UnifaiRAGPipelineList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiRAGPipeline `json:"items"`
}

func (o *UnifaiRAGPipeline) GetCommon() *CommonSpec         { return &o.Spec.CommonSpec }
func (o *UnifaiRAGPipeline) GetObjectStatus() *ObjectStatus { return &o.Status }

func init() {
	SchemeBuilder.Register(&UnifaiWorkflow{}, &UnifaiWorkflowList{}, &UnifaiSchedule{}, &UnifaiScheduleList{},
		&UnifaiTemplate{}, &UnifaiTemplateList{}, &UnifaiChat{}, &UnifaiChatList{},
		&UnifaiRAGPipeline{}, &UnifaiRAGPipelineList{})
}
