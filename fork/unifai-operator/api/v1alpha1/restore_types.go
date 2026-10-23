package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// Restore stores.
const (
	RestoreMongoDB = "mongodb"
	RestoreQdrant  = "qdrant"
)

// UnifaiRestoreSpec restores the MongoDB and/or Qdrant data of the namespace's stack from the backups written by
// spec.backup. The UnifAI applications are stopped while the data is replaced, then restarted.
// +kubebuilder:validation:XValidation:rule="self == oldSelf",message="an UnifaiRestore is immutable: create a new one"
// +kubebuilder:validation:XValidation:rule="!has(self.source) || !has(self.source.endpoint) || self.source.endpoint.startsWith('https://')",message="spec.source.endpoint must be https"
type UnifaiRestoreSpec struct {
	// Backup to restore: "latest", or a UTC time in the backup format (e.g. 20261023T020000Z); each store then
	// uses its newest backup taken at or before that time.
	// +kubebuilder:validation:Pattern=`^(latest|[0-9]{8}T[0-9]{6}Z)$`
	// +kubebuilder:default=latest
	// +optional
	Backup string `json:"backup,omitempty"`
	// Stores to restore (default both). A MongoDB restore replaces the dumped databases (mongorestore --drop).
	// +optional
	// +listType=set
	Stores []RestoreStore `json:"stores,omitempty"`
	// Qdrant collections to restore (default: every collection of the backup).
	// +optional
	// +listType=set
	// +kubebuilder:validation:MaxItems=100
	// +kubebuilder:validation:items:Pattern=`^[A-Za-z0-9_.-]+$`
	Collections []string `json:"collections,omitempty"`
	// Backups to read; default: the stack's spec.backup.s3. Set it to restore another stack's backups (same
	// bucket layout): https only, and its credentials Secret must be the stack's backup one or a Secret of this
	// namespace labelled unifai.startx.fr/backup-credentials=true.
	// +optional
	Source *BackupS3Spec `json:"source,omitempty"`
	// Restore a MongoDB backup whose encryption-key fingerprint differs from this stack's
	// CREDENTIAL_ENCRYPTION_KEY: the credentials it holds then cannot be decrypted (they must be entered again).
	// +optional
	AllowKeyMismatch bool `json:"allowKeyMismatch,omitempty"`
}

// RestoreStore is a store of the stack data.
// +kubebuilder:validation:Enum=mongodb;qdrant
type RestoreStore string

// UnifaiRestoreStatus reports the progress of a restore.
type UnifaiRestoreStatus struct {
	// Pending, Stopping, Restoring, Starting, Completed, Failed.
	// +optional
	Phase string `json:"phase,omitempty"`
	// +optional
	Message string `json:"message,omitempty"`
	// Backups restored, as <store>/<timestamp>.
	// +optional
	Restored []string `json:"restored,omitempty"`
	// +optional
	StartedAt *metav1.Time `json:"startedAt,omitempty"`
	// +optional
	CompletedAt *metav1.Time `json:"completedAt,omitempty"`
	// +optional
	Conditions []metav1.Condition `json:"conditions,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=urestore,categories=unifai
// +kubebuilder:printcolumn:name="Backup",type=string,JSONPath=`.spec.backup`
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// UnifaiRestore is a one-shot restore of the stack data from its S3 backups.
type UnifaiRestore struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiRestoreSpec   `json:"spec,omitempty"`
	Status UnifaiRestoreStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiRestoreList contains a list of UnifaiRestore.
type UnifaiRestoreList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiRestore `json:"items"`
}

func init() {
	SchemeBuilder.Register(&UnifaiRestore{}, &UnifaiRestoreList{})
}
