package controller

import (
	"context"
	"net/http"
	"net/url"
	"strings"
	"time"

	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// TeamReconciler reconciles UnifaiTeam into an identity team (identity API, through its Service with the internal
// secret). Team names are global in identity: a team of the same name is only taken over when it was created by the
// owner and the adopt annotation is set.
type TeamReconciler struct{ Base }

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaiteams,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaiteams/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaiteams/finalizers,verbs=update

// identityTeam is a team as identity serializes it.
type identityTeam struct {
	ID        string `json:"team_id"`
	Name      string `json:"name"`
	CreatedBy string `json:"created_by"`
}

func (r *TeamReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	obj := &unifaiv1.UnifaiTeam{}
	if err := r.get(ctx, req.NamespacedName, obj); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	api := r.identity(ctx, obj)
	return r.run(ctx, obj, Handlers{
		Apply:  func(ctx context.Context) (time.Duration, error) { return 0, r.apply(ctx, api, obj) },
		Delete: func(ctx context.Context) error { return r.delete(ctx, api, obj) },
	})
}

// teamMembers returns the members as identity expects them (a leading '/' of a group path removed).
func teamMembers(obj *unifaiv1.UnifaiTeam) []any {
	out := make([]any, 0, len(obj.Spec.Members))
	for _, m := range obj.Spec.Members {
		id := m.ID
		if m.Type == "group" {
			id = strings.TrimPrefix(id, "/")
		}
		e := map[string]any{"type": m.Type, "id": id}
		if m.DisplayName != "" {
			e["display_name"] = m.DisplayName
		}
		out = append(out, e)
	}
	return out
}

func (r *TeamReconciler) apply(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiTeam) error {
	owner, name := obj.Spec.Owner, unifaiName(obj)
	members := teamMembers(obj)
	h := hash(map[string]any{"name": name, "members": members})
	st := &obj.Status
	if st.TeamID != "" {
		var t identityTeam
		err := api.Call(ctx, http.MethodGet, "/api/teams/team.get", url.Values{"teamId": {st.TeamID}}, nil, &t)
		switch {
		case unifai.IsStatus(err, http.StatusNotFound):
			st.TeamID, st.Hash = "", "" // deleted in identity: recreated below
		case err != nil:
			return err
		case t.CreatedBy != "" && t.CreatedBy != owner:
			return permanent("team %s was created by %s, not by the owner %s", st.TeamID, t.CreatedBy, owner)
		case st.Hash == h && t.Name == name:
			setReady(st, PhaseReady, "team "+st.TeamID)
			return nil
		}
	}
	if st.TeamID == "" {
		var t identityTeam
		err := api.Call(ctx, http.MethodPost, "/api/teams/team.create", nil,
			map[string]any{"name": name, "createdBy": owner, "members": members}, &t)
		switch {
		case err == nil:
			st.TeamID, st.Hash = t.ID, h
			setReady(st, PhaseReady, "team "+t.ID)
			return nil
		case unifai.IsStatus(err, http.StatusBadRequest) && strings.Contains(err.Error(), "already exists"):
			id, terr := r.takeOver(ctx, api, obj, name, owner)
			if terr != nil {
				return terr
			}
			st.TeamID = id
		default:
			return permanentOn(err, http.StatusBadRequest, http.StatusForbidden, http.StatusConflict)
		}
	}
	err := api.Call(ctx, http.MethodPut, "/api/teams/team.update", nil,
		map[string]any{"teamId": st.TeamID, "name": name, "members": members}, nil)
	if err != nil {
		return permanentOn(err, http.StatusBadRequest)
	}
	st.Hash = h
	setReady(st, PhaseReady, "team "+st.TeamID)
	return nil
}

// takeOver finds an existing team of this name created by the owner; it is only used with the adopt annotation.
func (r *TeamReconciler) takeOver(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiTeam, name, owner string) (string, error) {
	var out struct {
		Teams []identityTeam `json:"teams"`
	}
	if err := api.Call(ctx, http.MethodGet, "/api/teams/teams.list", url.Values{"userId": {owner}}, nil, &out); err != nil {
		return "", err
	}
	for _, t := range out.Teams {
		if t.Name != name || t.CreatedBy != owner {
			continue
		}
		if !adopting(obj) {
			return "", permanent("team %q already exists in identity (created by %s): set the annotation %s=true to take it over",
				name, owner, unifaiv1.AdoptAnnotation)
		}
		return t.ID, nil
	}
	return "", permanent("team name %q is already used in identity by another user: set spec.unifaiName", name)
}

// delete removes the identity team once no object of the namespace uses it any more (identity has no such guard:
// deleting it would strand the objects of its workspace).
func (r *TeamReconciler) delete(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiTeam) error {
	if obj.Status.TeamID == "" {
		return nil
	}
	users, err := r.teamUsers(ctx, obj)
	if err != nil {
		return err
	}
	if len(users) > 0 {
		return &InUseError{Users: users}
	}
	err = api.Call(ctx, http.MethodDelete, "/api/teams/team.delete",
		url.Values{"teamId": {obj.Status.TeamID}, "requestedBy": {obj.Spec.Owner}}, nil, nil)
	if unifai.IsStatus(err, http.StatusNotFound) {
		return nil
	}
	return err
}

// teamUsers lists the UnifAI objects of the namespace (including those being deleted) that use the team, by
// teamRef or by its teamId.
func (r *TeamReconciler) teamUsers(ctx context.Context, team *unifaiv1.UnifaiTeam) ([]string, error) {
	reader := client.Reader(r.Client)
	if r.APIReader != nil {
		reader = r.APIReader
	}
	var users []string
	for gvk := range r.Scheme.AllKnownTypes() {
		if gvk.GroupVersion() != unifaiv1.GroupVersion || !strings.HasSuffix(gvk.Kind, "List") ||
			gvk.Kind == "UnifaiTeamList" || gvk.Kind == "UnifaiStackList" {
			continue
		}
		list := &unstructured.UnstructuredList{}
		list.SetGroupVersionKind(gvk)
		if err := reader.List(ctx, list, client.InNamespace(team.Namespace)); err != nil {
			return nil, err
		}
		for _, it := range list.Items {
			ref, _, _ := unstructured.NestedString(it.Object, "spec", "teamRef")
			id, _, _ := unstructured.NestedString(it.Object, "spec", "teamId")
			if ref == team.Name || (id != "" && id == team.Status.TeamID) {
				users = append(users, strings.TrimSuffix(gvk.Kind, "List")+"/"+it.GetName())
			}
		}
	}
	return users, nil
}

// SetupWithManager registers the controller.
func (r *TeamReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiTeam{}).Named("unifaiteam").Complete(r)
}
