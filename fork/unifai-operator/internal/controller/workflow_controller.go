package controller

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"

	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// WorkflowReconciler reconciles UnifaiWorkflow into an UnifAI blueprint.
type WorkflowReconciler struct{ Base }

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaiworkflows,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaiworkflows/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaiworkflows/finalizers,verbs=update

func (r *WorkflowReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	obj := &unifaiv1.UnifaiWorkflow{}
	if err := r.Get(ctx, req.NamespacedName, obj); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	api := r.mas(obj)
	return r.run(ctx, obj, Handlers{
		Apply: func(ctx context.Context) (time.Duration, error) { return 0, r.apply(ctx, api, obj) },
		Delete: func(ctx context.Context) error {
			if obj.Status.BlueprintID == "" {
				return nil
			}
			err := api.Call(ctx, http.MethodDelete, "/api/blueprints/remove.blueprint",
				url.Values{"blueprintId": {obj.Status.BlueprintID}}, nil, nil)
			if unifai.IsStatus(err, http.StatusNotFound) {
				return nil
			}
			return err
		},
	})
}

func (r *WorkflowReconciler) apply(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiWorkflow) error {
	name := unifaiName(obj)
	bp, err := rawMap(&obj.Spec.Blueprint)
	if err != nil {
		return err
	}
	bp["name"] = name
	if _, ok := bp["description"]; !ok {
		bp["description"] = obj.Spec.Description
	}
	if err := r.applySecrets(ctx, obj.Namespace, obj.Spec.SecretRefs, bp); err != nil {
		return err
	}
	rs := unifai.NewResolver(api)
	walked, err := rs.Walk(ctx, bp)
	if err != nil {
		return err
	}
	resolved := walked.(map[string]any)
	if err := rs.ExpandLibraryNodes(ctx, resolved); err != nil {
		return err
	}
	h := hash(resolved)
	raw, _ := json.Marshal(resolved)

	existing, err := api.FindBlueprint(ctx, name)
	if err != nil {
		return err
	}
	if existing != "" && existing != obj.Status.BlueprintID && !adopting(obj) {
		return notManaged(fmt.Sprintf("workflow %s", name))
	}
	bid := existing
	switch {
	case bid != "" && obj.Status.Hash == h && obj.Status.BlueprintID == bid:
	case bid != "":
		err = api.Call(ctx, http.MethodPut, "/api/blueprints/blueprint.update", nil,
			map[string]any{"blueprintId": bid, "blueprintRaw": string(raw)}, nil)
	default:
		var out struct {
			ID string `json:"blueprint_id"`
		}
		err = api.Call(ctx, http.MethodPost, "/api/blueprints/blueprint.save", nil, map[string]any{"blueprintRaw": string(raw)}, &out)
		bid = out.ID
	}
	if err != nil {
		return permanentOn(err, http.StatusBadRequest, http.StatusConflict, http.StatusUnprocessableEntity)
	}
	obj.Status.BlueprintID, obj.Status.Hash = bid, h
	setReady(&obj.Status, "Ready", "blueprint "+name)
	return nil
}

// SetupWithManager registers the controller.
func (r *WorkflowReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiWorkflow{}).Named("unifaiworkflow").Complete(r)
}

// workflowID returns the blueprint id of the workflow named name (temporary error while it does not exist).
func workflowID(ctx context.Context, api *unifai.Client, name string) (string, error) {
	bid, err := api.FindBlueprint(ctx, name)
	if err != nil {
		return "", err
	}
	if bid == "" {
		return "", fmt.Errorf("workflow %q not found in UnifAI", name)
	}
	return bid, nil
}
