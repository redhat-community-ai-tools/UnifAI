package controller

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// ResourceReconciler reconciles one of the seven kinds stored in the UnifAI `resources` collection
// (LLM, Provider, Tool, Condition, Retriever, Sandbox, Agent).
type ResourceReconciler struct {
	Base
	Kind   string
	NewObj func() unifaiv1.ResourceObject
}

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaillms;unifaiproviders;unifaitools;unifaiconditions;unifairetrievers;unifaisandboxes;unifaiagents,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaillms/status;unifaiproviders/status;unifaitools/status;unifaiconditions/status;unifairetrievers/status;unifaisandboxes/status;unifaiagents/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifaillms/finalizers;unifaiproviders/finalizers;unifaitools/finalizers;unifaiconditions/finalizers;unifairetrievers/finalizers;unifaisandboxes/finalizers;unifaiagents/finalizers,verbs=update
// +kubebuilder:rbac:groups="",resources=secrets;configmaps,verbs=get;list;watch

func (r *ResourceReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	obj := r.NewObj()
	if err := r.get(ctx, req.NamespacedName, obj); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	api := r.mas(ctx, obj)
	st := obj.GetObjectStatus()
	return r.run(ctx, obj, Handlers{
		Apply: func(ctx context.Context) (time.Duration, error) { return 0, r.apply(ctx, api, obj) },
		Delete: func(ctx context.Context) error {
			if st.RID == "" {
				return nil
			}
			err := api.Call(ctx, http.MethodDelete, "/api/resources/resource.delete", url.Values{"resourceId": {st.RID}}, nil, nil)
			if unifai.IsStatus(err, http.StatusNotFound) {
				return nil
			}
			return err
		},
	})
}

func (r *ResourceReconciler) apply(ctx context.Context, api *unifai.Client, obj unifaiv1.ResourceObject) error {
	st := obj.GetObjectStatus()
	category, rtype, name := obj.Category(), obj.GetType(), unifaiName(obj)
	cfg, err := rawMap(obj.GetConfigSpec().Config)
	if err != nil {
		return err
	}
	if _, ok := cfg["type"]; !ok {
		cfg["type"] = rtype
	}
	if err := r.applySecrets(ctx, obj.GetNamespace(), obj.GetConfigSpec().SecretRefs, cfg); err != nil {
		return err
	}
	resolved, err := unifai.NewResolver(api).Walk(ctx, cfg)
	if err != nil {
		return err
	}
	h := hash([]any{rtype, name, resolved})

	err = api.Call(ctx, http.MethodPost, "/api/resources/config.validate", nil,
		map[string]any{"category": category, "type": rtype, "name": name, "config": resolved}, nil)
	if err != nil {
		if ae, ok := err.(*unifai.APIError); ok && strings.Contains(ae.Body, "No spec registered") {
			return permanent("type %q is not served by this UnifAI instance: %s", rtype, ae.Error())
		}
		return permanentOn(err, http.StatusBadRequest, http.StatusUnprocessableEntity)
	}

	list, err := api.ListResources(ctx, category)
	if err != nil {
		return err
	}
	var existing *unifai.Resource
	for i := range list {
		if list[i].Name == name {
			existing = &list[i]
		}
	}
	if existing != nil && existing.RID != st.RID && !adopting(obj) {
		return notManaged(fmt.Sprintf("%s/%s", category, name))
	}
	if existing != nil && existing.Type != rtype {
		if err := api.Call(ctx, http.MethodDelete, "/api/resources/resource.delete", url.Values{"resourceId": {existing.RID}}, nil, nil); err != nil {
			return err
		}
		existing = nil
	}
	rid := ""
	if existing != nil {
		rid = existing.RID
		if st.Hash != h || st.RID != rid {
			err = api.Call(ctx, http.MethodPut, "/api/resources/resource.update", nil,
				map[string]any{"resourceId": rid, "config": resolved, "name": name}, nil)
		}
	} else {
		var out map[string]any
		err = api.Call(ctx, http.MethodPost, "/api/resources/resource.save", nil,
			map[string]any{"category": category, "type": rtype, "name": name, "config": resolved}, &out)
		rid, _ = out["rid"].(string)
		if rid == "" && err == nil {
			rid, err = unifai.NewResolver(api).RID(ctx, kindOf(category), name)
		}
	}
	if err != nil {
		return permanentOn(err, http.StatusBadRequest, http.StatusConflict, http.StatusUnprocessableEntity)
	}
	st.RID, st.Hash = rid, h
	setReady(st, "Ready", category+"/"+name)
	return nil
}

func kindOf(category string) string {
	for k, c := range unifai.KindCategory {
		if c == category {
			return k
		}
	}
	return category
}

// SetupWithManager registers the controller.
func (r *ResourceReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(r.NewObj()).Named(strings.ToLower(r.Kind)).Complete(r)
}

// ResourceKinds lists the seven resource kinds with their constructors.
var ResourceKinds = map[string]func() unifaiv1.ResourceObject{
	"UnifaiLLM":       func() unifaiv1.ResourceObject { return &unifaiv1.UnifaiLLM{} },
	"UnifaiProvider":  func() unifaiv1.ResourceObject { return &unifaiv1.UnifaiProvider{} },
	"UnifaiTool":      func() unifaiv1.ResourceObject { return &unifaiv1.UnifaiTool{} },
	"UnifaiCondition": func() unifaiv1.ResourceObject { return &unifaiv1.UnifaiCondition{} },
	"UnifaiRetriever": func() unifaiv1.ResourceObject { return &unifaiv1.UnifaiRetriever{} },
	"UnifaiSandbox":   func() unifaiv1.ResourceObject { return &unifaiv1.UnifaiSandbox{} },
	"UnifaiAgent":     func() unifaiv1.ResourceObject { return &unifaiv1.UnifaiAgent{} },
}
