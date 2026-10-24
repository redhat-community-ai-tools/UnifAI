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

// RAGWebSource scopes a web source: public pages fetched without credentials, from seed URLs and
// (optionally) the pages they link to.
type RAGWebSource struct {
	// Seed pages. Each is fetched on every sync (its links are the discovery input); the pages found
	// from it are fetched only when the server says they changed.
	// +kubebuilder:validation:MinItems=1
	// +kubebuilder:validation:MaxItems=500
	// +kubebuilder:validation:items:MaxLength=2048
	// +kubebuilder:validation:XValidation:rule="self.all(u, isURL(u) && (u.startsWith('http://') || u.startsWith('https://')) && size(url(u).getHostname()) > 0)",message="web urls are http(s) URLs"
	URLs []string `json:"urls"`
	// Discovery of linked pages: redhat-docs (same host, /html/ or /html-single/ book paths), generic
	// (same host, under the seed's directory) or none (the seeds only).
	// +kubebuilder:validation:Enum=redhat-docs;generic;none
	// +kubebuilder:default=redhat-docs
	// +optional
	Crawl string `json:"crawl,omitempty"`
	// Shell-style patterns a discovered URL must match (empty = all) and must not match.
	// +optional
	Include []string `json:"include,omitempty"`
	// +optional
	Exclude []string `json:"exclude,omitempty"`
	// Limit on pages discovered per seed.
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:validation:Maximum=1000
	// +kubebuilder:default=50
	// +optional
	MaxPages int `json:"maxPages,omitempty"`
	// Fields stamped on every chunk of the source (e.g. product, version, language).
	// +optional
	Metadata map[string]string `json:"metadata,omitempty"`
}

// UnifaiRAGSourceSpec is a RAG source kept in sync on a schedule. Credentials are stack-wide
// (UnifaiStack.spec.rag.confluence).
// +kubebuilder:validation:XValidation:rule="self.type != 'confluence' || has(self.confluence)",message="confluence settings are required for type confluence"
// +kubebuilder:validation:XValidation:rule="self.type != 'web' || has(self.web)",message="web settings are required for type web"
// +kubebuilder:validation:XValidation:rule="self.visibility != 'shared' || (has(self.aclGroups) && size(self.aclGroups) > 0)",message="a shared source needs at least one ACL group"
// +kubebuilder:validation:XValidation:rule="!has(self.teamId) || !has(self.teamRef) || size(self.teamId) == 0 || size(self.teamRef) == 0",message="teamId and teamRef are exclusive"
type UnifaiRAGSourceSpec struct {
	// Owner is the UnifAI user registering the source; a shared source needs it in
	// UnifaiStack.spec.rag.sharedPublishers.
	CommonSpec `json:",inline"`
	// +kubebuilder:validation:Enum=confluence;web
	Type string `json:"type"`
	// +optional
	Confluence *RAGConfluenceSource `json:"confluence,omitempty"`
	// +optional
	Web *RAGWebSource `json:"web,omitempty"`
	// private (owner only), shared (owner + members of aclGroups) or public (every signed-in user; for
	// public documentation). Shared and public need the owner in UnifaiStack.spec.rag.sharedPublishers.
	// +kubebuilder:validation:Enum=private;shared;public
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
	// +kubebuilder:validation:XValidation:rule="duration(self) >= duration('10m')",message="syncInterval is at least 10m"
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
