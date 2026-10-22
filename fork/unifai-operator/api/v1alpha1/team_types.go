package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// TeamMember is a user or an identity group (OIDC group claim) of a team.
type TeamMember struct {
	// +kubebuilder:validation:Enum=user;group
	Type string `json:"type"`
	// User name or group name (a leading '/' of a group path is removed).
	// +kubebuilder:validation:Pattern=`^/?[A-Za-z0-9][A-Za-z0-9._@:-]{0,127}$`
	ID string `json:"id"`
	// +optional
	DisplayName string `json:"displayName,omitempty"`
}

// UnifaiTeamSpec defines an identity team. Its name is global in identity: a team of the same name created by another
// user is never taken over. The owner (creator) is always a member.
// +kubebuilder:validation:XValidation:rule="!has(self.teamId) && !has(self.teamRef)",message="an UnifaiTeam has no teamId/teamRef"
type UnifaiTeamSpec struct {
	CommonSpec `json:",inline"`
	// +optional
	// +listType=map
	// +listMapKey=type
	// +listMapKey=id
	Members []TeamMember `json:"members,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=uteam,categories=unifai
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="TeamId",type=string,JSONPath=`.status.teamId`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// UnifaiTeam is an UnifAI (identity) team; objects use its workspace with spec.teamRef.
type UnifaiTeam struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiTeamSpec `json:"spec,omitempty"`
	Status ObjectStatus   `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiTeamList contains a list of UnifaiTeam.
type UnifaiTeamList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiTeam `json:"items"`
}

func (o *UnifaiTeam) GetCommon() *CommonSpec         { return &o.Spec.CommonSpec }
func (o *UnifaiTeam) GetObjectStatus() *ObjectStatus { return &o.Status }

func init() {
	SchemeBuilder.Register(&UnifaiTeam{}, &UnifaiTeamList{})
}
