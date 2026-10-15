package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

// UnifaiWorkflowSpec defines an agentic workflow (UnifAI blueprint).
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
type ScheduleDefinition struct {
	// ISO-8601 duration, minimum PT1M.
	// +optional
	Interval string `json:"interval,omitempty"`
	// 5-field cron expression.
	// +optional
	CronExpression string `json:"cron_expression,omitempty"`
	// +optional
	Timezone string `json:"timezone,omitempty"`
	// +kubebuilder:validation:Enum=skip;buffer_one;cancel_other
	// +optional
	OverlapPolicy string `json:"overlap_policy,omitempty"`
	// +optional
	StartAt string `json:"start_at,omitempty"`
	// +optional
	EndAt string `json:"end_at,omitempty"`
	// +optional
	RemainingActions *int `json:"remaining_actions,omitempty"`
}

// UnifaiScheduleSpec defines a scheduled run of a workflow.
type UnifaiScheduleSpec struct {
	CommonSpec `json:",inline"`
	// UnifAI workflow (blueprint) name.
	Workflow string `json:"workflow"`
	// Workflow inputs; `user_prompt` is required by UnifAI.
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
type UnifaiChatSpec struct {
	CommonSpec `json:",inline"`
	// UnifAI workflow (blueprint) name.
	Workflow string `json:"workflow"`
	Prompt   string `json:"prompt"`
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
	// +optional
	URL string `json:"url,omitempty"`
	// +optional
	ConfigMapKeyRef *ConfigMapKeySelector `json:"configMapKeyRef,omitempty"`
}

// RAGDocument is one document to ingest.
type RAGDocument struct {
	// File name with a supported extension (pdf, docx, md, pptx).
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
type UnifaiRAGPipelineSpec struct {
	CommonSpec `json:",inline"`
	// +optional
	SkipValidation bool `json:"skipValidation,omitempty"`
	// +kubebuilder:validation:MinItems=1
	// +kubebuilder:validation:MaxItems=100
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
