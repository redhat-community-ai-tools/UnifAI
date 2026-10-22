package controller

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"time"

	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// ScheduleReconciler reconciles UnifaiSchedule into an UnifAI workflow schedule.
type ScheduleReconciler struct{ Base }

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaischedules,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaischedules/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaischedules/finalizers,verbs=update

func (r *ScheduleReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	obj := &unifaiv1.UnifaiSchedule{}
	if err := r.get(ctx, req.NamespacedName, obj); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	api := r.mas(ctx, obj)
	return r.run(ctx, obj, Handlers{
		Apply:  func(ctx context.Context) (time.Duration, error) { return 0, r.apply(ctx, api, obj) },
		Delete: func(ctx context.Context) error { return deleteSchedule(ctx, api, obj.Status.ScheduleID) },
	})
}

func deleteSchedule(ctx context.Context, api *unifai.Client, id string) error {
	if id == "" {
		return nil
	}
	err := api.Call(ctx, http.MethodDelete, "/api/schedules/schedule.delete", nil, map[string]any{"scheduleId": id}, nil)
	if unifai.IsStatus(err, http.StatusNotFound) {
		return nil
	}
	return err
}

func (r *ScheduleReconciler) apply(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiSchedule) error {
	bid, err := workflowID(ctx, api, obj.Spec.Workflow)
	if err != nil {
		return err
	}
	var sched map[string]any
	b, _ := json.Marshal(obj.Spec.Schedule)
	_ = json.Unmarshal(b, &sched)
	sched["enabled"] = !obj.Spec.Suspend
	h := hash([]any{bid, obj.Spec.Inputs, sched})
	st := &obj.Status
	sid := st.ScheduleID
	if sid != "" && st.BlueprintID != bid { // the workflow was replaced: recreate the schedule
		if err := deleteSchedule(ctx, api, sid); err != nil {
			return err
		}
		sid = ""
	}
	if sid != "" && st.Hash == h { // unchanged: only check it still exists
		err = api.Call(ctx, http.MethodGet, "/api/schedules/schedule.get", url.Values{"scheduleId": {sid}}, nil, nil)
		if unifai.IsStatus(err, http.StatusNotFound) {
			sid, err = "", nil
		}
	} else if sid != "" {
		err = api.Call(ctx, http.MethodPost, "/api/schedules/schedule.update", nil,
			map[string]any{"scheduleId": sid, "inputs": obj.Spec.Inputs, "schedule": sched}, nil)
		if unifai.IsStatus(err, http.StatusNotFound) { // deleted from the UI: recreate
			sid, err = "", nil
		}
	}
	if sid == "" && err == nil {
		var out struct {
			ID string `json:"id"`
		}
		err = api.Call(ctx, http.MethodPost, "/api/schedules/schedule.create", nil,
			map[string]any{"blueprintId": bid, "inputs": obj.Spec.Inputs, "source": "manual", "schedule": sched}, &out)
		sid = out.ID
	}
	if err != nil {
		return permanentOn(err, http.StatusBadRequest, http.StatusConflict, http.StatusUnprocessableEntity)
	}
	st.ScheduleID, st.BlueprintID, st.Hash = sid, bid, h
	if obj.Spec.Suspend {
		setReady(st, "Suspended", "schedule "+sid)
	} else {
		setReady(st, "Ready", "schedule "+sid)
	}
	return nil
}

// SetupWithManager registers the controller.
func (r *ScheduleReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiSchedule{}).Named("unifaischedule").Complete(r)
}
