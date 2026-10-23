package controller

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"strings"
	"time"

	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// ChatReconciler runs an UnifaiChat once: it creates a session on the workflow, submits the prompt
// and polls the session until it ends, then stores the transcript in status.result.
type ChatReconciler struct{ Base }

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaichats,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaichats/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaichats/finalizers,verbs=update

var chatTerminal = map[string]string{"COMPLETED": PhaseCompleted, statusFailed: PhaseFailed, "CANCELLED": PhaseFailed, "ERROR": PhaseFailed}

func (r *ChatReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	obj := &unifaiv1.UnifaiChat{}
	if err := r.get(ctx, req.NamespacedName, obj); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	api := r.mas(ctx, obj)
	return r.run(ctx, obj, Handlers{
		Apply: func(ctx context.Context) (time.Duration, error) { return r.apply(ctx, api, obj) },
		Delete: func(ctx context.Context) error {
			if obj.Status.SessionID == "" {
				return nil
			}
			err := api.Call(ctx, http.MethodDelete, "/api/sessions/session.delete", url.Values{"sessionId": {obj.Status.SessionID}}, nil, nil)
			if err != nil && !unifai.IsStatus(err, http.StatusNotFound) {
				return err
			}
			return nil
		},
	})
}

func (r *ChatReconciler) apply(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiChat) (time.Duration, error) {
	st := &obj.Status
	switch st.Phase {
	case PhaseCompleted, PhaseFailed:
		return 0, nil
	}
	if st.SessionID == "" {
		bid, err := workflowID(ctx, api, obj.Spec.Workflow)
		if err != nil {
			return 0, err
		}
		title := obj.Spec.Title
		if title == "" {
			title = obj.Name
		}
		var sid string
		if err := api.Call(ctx, http.MethodPost, "/api/sessions/user.session.create", nil, map[string]any{
			"blueprintId": bid, "hitlEnabled": obj.Spec.HITL,
			"metadata": map[string]any{"title": title, "source": "operator"},
		}, &sid); err != nil {
			return 0, permanentOn(err, http.StatusBadRequest, http.StatusNotFound, http.StatusUnprocessableEntity)
		}
		// Recorded before submitting: a failed submit is retried on the same session.
		st.SessionID, st.BlueprintID = sid, bid
	}
	if st.Phase != "Running" {
		if err := api.Call(ctx, http.MethodPost, "/api/sessions/user.session.submit", nil,
			map[string]any{"sessionId": st.SessionID, "inputs": map[string]any{"user_prompt": obj.Spec.Prompt}}, nil); err != nil {
			return 0, permanentOn(err, http.StatusBadRequest, http.StatusConflict)
		}
		setReady(st, "Running", "submitted")
		return retry, nil
	}
	var chat map[string]any
	if err := api.Call(ctx, http.MethodGet, "/api/sessions/session.chat.get", url.Values{"sessionId": {st.SessionID}}, nil, &chat); err != nil {
		return 0, err
	}
	status, _ := chat["status"].(string)
	status = strings.ToUpper(status)
	phase, done := chatTerminal[status]
	if !done {
		setReady(st, "Running", "session "+status)
		return retry, nil
	}
	b, _ := json.Marshal(chat)
	st.Result = unifai.Truncate(string(b), 4000)
	setReady(st, phase, "session "+status)
	return 0, nil
}

// SetupWithManager registers the controller.
func (r *ChatReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiChat{}).Named("unifaichat").Complete(r)
}
