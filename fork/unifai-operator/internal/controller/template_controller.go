package controller

import (
	"context"
	"net/http"
	"net/url"
	"time"

	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// TemplateReconciler reconciles UnifaiTemplate into an UnifAI catalog template.
// UnifAI has no template update endpoint: a changed spec deletes and recreates the template.
type TemplateReconciler struct{ Base }

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaitemplates,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaitemplates/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaitemplates/finalizers,verbs=update

func (r *TemplateReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	obj := &unifaiv1.UnifaiTemplate{}
	if err := r.get(ctx, req.NamespacedName, obj); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	api := r.mas(ctx, obj)
	return r.run(ctx, obj, Handlers{
		Apply:  func(ctx context.Context) (time.Duration, error) { return 0, r.apply(ctx, api, obj) },
		Delete: func(ctx context.Context) error { return deleteTemplate(ctx, api, obj.Status.TemplateID) },
	})
}

func deleteTemplate(ctx context.Context, api *unifai.Client, id string) error {
	if id == "" {
		return nil
	}
	err := api.Call(ctx, http.MethodDelete, "/api/templates/template.delete", url.Values{"templateId": {id}}, nil, nil)
	if unifai.IsStatus(err, http.StatusNotFound) {
		return nil
	}
	return err
}

func (r *TemplateReconciler) apply(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiTemplate) error {
	draft, err := rawMap(&obj.Spec.Draft)
	if err != nil {
		return err
	}
	if err := r.applySecrets(ctx, obj.Namespace, obj.Spec.SecretRefs, draft); err != nil {
		return err
	}
	placeholders, err := rawMap(obj.Spec.Placeholders)
	if err != nil {
		return err
	}
	if _, ok := placeholders["categories"]; !ok {
		placeholders["categories"] = []any{}
	}
	metadata, err := rawMap(obj.Spec.Metadata)
	if err != nil {
		return err
	}
	body := map[string]any{"draft": draft, "placeholders": placeholders, "metadata": metadata}
	h := hash(body)
	st := &obj.Status
	if st.TemplateID != "" {
		err := api.Call(ctx, http.MethodGet, "/api/templates/template.get", url.Values{"templateId": {st.TemplateID}}, nil, nil)
		switch {
		case unifai.IsStatus(err, http.StatusNotFound):
			st.TemplateID = ""
		case err != nil:
			return err
		case st.Hash == h:
			setReady(st, "Ready", "template "+st.TemplateID)
			return nil
		default:
			if err := deleteTemplate(ctx, api, st.TemplateID); err != nil {
				return err
			}
			st.TemplateID = ""
		}
	}
	var out struct {
		ID string `json:"template_id"`
	}
	if err := api.Call(ctx, http.MethodPost, "/api/templates/template.create", nil, body, &out); err != nil {
		return permanentOn(err, http.StatusBadRequest, http.StatusConflict, http.StatusUnprocessableEntity)
	}
	st.TemplateID, st.Hash = out.ID, h
	setReady(st, "Ready", "template "+out.ID)
	return nil
}

// SetupWithManager registers the controller.
func (r *TemplateReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiTemplate{}).Named("unifaitemplate").Complete(r)
}
