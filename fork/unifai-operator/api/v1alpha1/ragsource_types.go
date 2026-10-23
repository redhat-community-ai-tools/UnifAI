package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// RAGConfluenceSource scopes a Confluence source: one space, optionally narrowed to the subtree under a root page.
type RAGConfluenceSource struct {
	// Site URL, e.g. https://example.atlassian.net (Cloud) or https://confluence.example.com (Data Center).
	// +kubebuilder:validation:Pattern=`^https?://`
	BaseURL  string `json:"baseUrl"`
	SpaceKey string `json:"spaceKey"`
	// Title of the root page whose subtree is ingested (the page included); empty = the whole space.
	// +optional
	RootTitle string `json:"rootTitle,omitempty"`
	// Pages carrying one of these labels are skipped.
	// +optional
	ExcludeLabels []string `json:"excludeLabels,omitempty"`
}

// UnifaiRAGSourceSpec is a RAG source kept in sync on a schedule. Credentials are stack-wide
// (UnifaiStack.spec.rag.confluence).
// +kubebuilder:validation:XValidation:rule="self.type != 'confluence' || has(self.confluence)",message="confluence settings are required for type confluence"
// +kubebuilder:validation:XValidation:rule="self.visibility != 'shared' || (has(self.aclGroups) && size(self.aclGroups) > 0)",message="a shared source needs at least one ACL group"
type UnifaiRAGSourceSpec struct {
	// Owner is the UnifAI user registering the source; a shared source needs it in
	// UnifaiStack.spec.rag.sharedPublishers.
	CommonSpec `json:",inline"`
	// +kubebuilder:validation:Enum=confluence
	Type string `json:"type"`
	// +optional
	Confluence *RAGConfluenceSource `json:"confluence,omitempty"`
	// private (owner only) or shared (owner + members of aclGroups).
	// +kubebuilder:validation:Enum=private;shared
	// +kubebuilder:default=private
	// +optional
	Visibility string `json:"visibility,omitempty"`
	// OIDC groups allowed to retrieve a shared source.
	// +optional
	ACLGroups []string `json:"aclGroups,omitempty"`
	// Tags put on the source, so a search can be scoped to a domain (query tags=<tag>) instead of "every
	// source the caller can see". Changing them registers the source again (no page is re-embedded).
	// +optional
	Tags []string `json:"tags,omitempty"`
	// Time between incremental syncs (minimum 10m). Unset = sync only when the spec changes.
	// +optional
	SyncInterval *metav1.Duration `json:"syncInterval,omitempty"`
	// Stop scheduled syncs.
	// +optional
	Suspend bool `json:"suspend,omitempty"`
}

// UnifaiRAGSourceStatus reports the last sync.
type UnifaiRAGSourceStatus struct {
	ObjectStatus `json:",inline"`
	// Id of the source in the RAG service.
	// +optional
	SourceID string `json:"sourceId,omitempty"`
	// +optional
	LastSyncTime *metav1.Time `json:"lastSyncTime,omitempty"`
	// +optional
	NextSyncTime *metav1.Time `json:"nextSyncTime,omitempty"`
	// Pipeline status reported by the RAG service (PENDING ... DONE, FAILED).
	// +optional
	PipelineStatus string `json:"pipelineStatus,omitempty"`
	// +optional
	Pages int `json:"pages,omitempty"`
	// +optional
	PagesChanged int `json:"pagesChanged,omitempty"`
	// +optional
	PagesDeleted int `json:"pagesDeleted,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=uragsrc,categories=unifai
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Type",type=string,JSONPath=`.spec.type`
// +kubebuilder:printcolumn:name="Pages",type=integer,JSONPath=`.status.pages`
// +kubebuilder:printcolumn:name="LastSync",type=date,JSONPath=`.status.lastSyncTime`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1

// UnifaiRAGSource keeps a RAG source (e.g. a Confluence space) ingested and incrementally re-synced.
type UnifaiRAGSource struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiRAGSourceSpec   `json:"spec"`
	Status UnifaiRAGSourceStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiRAGSourceList contains a list of UnifaiRAGSource.
type UnifaiRAGSourceList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiRAGSource `json:"items"`
}

func (o *UnifaiRAGSource) GetCommon() *CommonSpec         { return &o.Spec.CommonSpec }
func (o *UnifaiRAGSource) GetObjectStatus() *ObjectStatus { return &o.Status.ObjectStatus }

func init() {
	SchemeBuilder.Register(&UnifaiRAGSource{}, &UnifaiRAGSourceList{})
}
