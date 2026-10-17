package controller

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// RAGSourceReconciler registers an UnifaiRAGSource with the RAG service and triggers its (incremental) sync when
// the spec changes and every syncInterval. The RAG service decides what actually changed: an unchanged space
// embeds nothing.
type RAGSourceReconciler struct {
	Base
	// Now is the clock (overridable in tests).
	Now func() time.Time
}

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairagsources,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairagsources/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairagsources/finalizers,verbs=update

const minSyncInterval = 10 * time.Minute

func (r *RAGSourceReconciler) now() time.Time {
	if r.Now != nil {
		return r.Now()
	}
	return time.Now()
}

func (r *RAGSourceReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	obj := &unifaiv1.UnifaiRAGSource{}
	if err := r.get(ctx, req.NamespacedName, obj); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	api := r.rag(obj)
	return r.run(ctx, obj, Handlers{
		Apply: func(ctx context.Context) (time.Duration, error) { return r.apply(ctx, api, obj) },
		Delete: func(ctx context.Context) error {
			if obj.Status.SourceID == "" {
				return nil
			}
			err := api.Call(ctx, http.MethodDelete, "/api/data_sources/data.source.delete", nil,
				map[string]any{"pipeline_ids": []string{obj.Status.SourceID}}, nil)
			if unifai.IsStatus(err, http.StatusNotFound) {
				return nil
			}
			return err
		},
	})
}

// instance is what the RAG service registers; its hash decides whether the spec changed.
func ragSourceInstance(obj *unifaiv1.UnifaiRAGSource) (string, map[string]any, error) {
	switch obj.Spec.Type {
	case "confluence":
		c := obj.Spec.Confluence
		if c == nil {
			return "", nil, permanent("spec.confluence is required for type confluence")
		}
		visibility := obj.Spec.Visibility
		if visibility == "" {
			visibility = "private"
		}
		return "confluence", map[string]any{
			"name": unifaiName(obj), "baseUrl": c.BaseURL, "spaceKey": c.SpaceKey, "rootTitle": c.RootTitle,
			"excludeLabels": append([]string{}, c.ExcludeLabels...), "visibility": visibility,
			"aclGroups": append([]string{}, obj.Spec.ACLGroups...),
		}, nil
	}
	return "", nil, permanent("unsupported source type %q", obj.Spec.Type)
}

func (r *RAGSourceReconciler) apply(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiRAGSource) (time.Duration, error) {
	st := &obj.Status
	sourceType, instance, err := ragSourceInstance(obj)
	if err != nil {
		return 0, err
	}
	interval := time.Duration(0)
	if obj.Spec.SyncInterval != nil {
		interval = obj.Spec.SyncInterval.Duration
		if interval < minSyncInterval {
			return 0, permanent("syncInterval %s is below the %s minimum", interval, minSyncInterval)
		}
	}
	h, now := hash(instance), r.now()
	specChanged := st.Hash != h || st.SourceID == ""
	scheduled := !obj.Spec.Suspend && interval > 0 && st.LastSyncTime != nil && !now.Before(st.LastSyncTime.Add(interval))
	if specChanged || scheduled {
		// The hash and sync time are recorded as soon as the RAG service accepted the request, before its
		// body is read: a retry must never re-trigger an accepted sync (each one queues a pipeline run).
		accepted, err := r.trigger(ctx, api, obj, sourceType, instance)
		if accepted {
			st.Hash, st.LastSyncTime = h, &metav1.Time{Time: now}
		}
		if err != nil {
			return 0, err
		}
	}
	st.NextSyncTime = nil
	if !obj.Spec.Suspend && interval > 0 && st.LastSyncTime != nil {
		st.NextSyncTime = &metav1.Time{Time: st.LastSyncTime.Add(interval)}
	}

	syncing, err := r.refresh(ctx, api, obj)
	if err != nil {
		return 0, err
	}
	switch {
	case syncing:
		setReady(&st.ObjectStatus, "Syncing", fmt.Sprintf("pipeline %s", st.PipelineStatus))
		return 30 * time.Second, nil
	case st.PipelineStatus == "FAILED":
		setReady(&st.ObjectStatus, "Failed", "the last sync failed; it is retried at the next interval or spec change")
	default:
		setReady(&st.ObjectStatus, "Ready", fmt.Sprintf("%d pages (%d changed, %d deleted at the last sync)",
			st.Pages, st.PagesChanged, st.PagesDeleted))
	}
	if st.NextSyncTime != nil {
		return max(time.Until(st.NextSyncTime.Time), time.Second), nil
	}
	return 0, nil
}

// trigger registers the source and queues a sync. accepted reports whether the RAG service took the request
// (HTTP 200), in which case a sync may be running even if the body is unexpected.
func (r *RAGSourceReconciler) trigger(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiRAGSource, sourceType string, instance map[string]any) (bool, error) {
	var out struct {
		Registration struct {
			Registered []struct {
				Metadata map[string]any `json:"metadata"`
			} `json:"registered_sources"`
			Issues []map[string]any `json:"issues"`
		} `json:"registration"`
	}
	var raw json.RawMessage
	if err := api.Call(ctx, http.MethodPut, "/api/pipelines/embed", nil, map[string]any{
		"source_type": sourceType, "skip_validation": false, "data": []any{instance},
	}, &raw); err != nil {
		return false, permanentOn(err, http.StatusBadRequest, http.StatusForbidden, http.StatusUnprocessableEntity)
	}
	_ = json.Unmarshal(raw, &out)
	if len(out.Registration.Issues) > 0 {
		b, _ := json.Marshal(out.Registration.Issues)
		return true, permanent("rag-server refused the source: %s", unifai.Truncate(string(b), 400))
	}
	if len(out.Registration.Registered) == 0 {
		return true, permanent("rag-server accepted the request but returned no registered source: %s", unifai.Truncate(string(raw), 300))
	}
	if id, _ := out.Registration.Registered[0].Metadata["source_id"].(string); id != "" {
		obj.Status.SourceID = id
	}
	return true, nil
}

// refresh reads the source's pipeline status and page counts; it reports whether a sync is still running.
func (r *RAGSourceReconciler) refresh(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiRAGSource) (bool, error) {
	st := &obj.Status
	if st.SourceID == "" {
		return true, nil
	}
	var out struct {
		Source struct {
			Status   string         `json:"status"`
			TypeData map[string]any `json:"type_data"`
		} `json:"source"`
	}
	err := api.Call(ctx, http.MethodGet, "/api/data_sources/data.source.details.get", url.Values{"source_id": {st.SourceID}}, nil, &out)
	if unifai.IsStatus(err, http.StatusNotFound) {
		return true, nil // registered, not persisted by the worker yet
	}
	if err != nil {
		return false, err
	}
	st.PipelineStatus = out.Source.Status
	count := func(k string) int {
		if f, ok := out.Source.TypeData[k].(float64); ok {
			return int(f)
		}
		return 0
	}
	st.Pages, st.PagesChanged, st.PagesDeleted = count("page_count"), count("pages_changed"), count("pages_deleted")
	return st.PipelineStatus != "" && st.PipelineStatus != "DONE" && st.PipelineStatus != "FAILED", nil
}

// SetupWithManager registers the controller.
func (r *RAGSourceReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiRAGSource{}).Named("unifairagsource").Complete(r)
}
