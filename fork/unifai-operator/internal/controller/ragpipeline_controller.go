package controller

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// RAGPipelineReconciler uploads the declared documents to rag-server and dispatches the document pipeline
// (collect, chunk, embed, store in Qdrant), once per content change.
type RAGPipelineReconciler struct{ Base }

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairagpipelines,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairagpipelines/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairagpipelines/finalizers,verbs=update

const maxDocumentBytes = 50 << 20 // rag-server limit (DocConfigManager.max_file_size_mb)

func (r *RAGPipelineReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	obj := &unifaiv1.UnifaiRAGPipeline{}
	if err := r.Get(ctx, req.NamespacedName, obj); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	return r.run(ctx, obj, Handlers{Apply: func(ctx context.Context) (time.Duration, error) { return 0, r.apply(ctx, obj) }})
}

func (r *RAGPipelineReconciler) content(ctx context.Context, ns string, d unifaiv1.RAGDocument) ([]byte, error) {
	src := d.Source
	switch {
	case src.Inline != "":
		return []byte(src.Inline), nil
	case src.ConfigMapKeyRef != nil:
		var cm corev1.ConfigMap
		if err := r.Get(ctx, types.NamespacedName{Namespace: ns, Name: src.ConfigMapKeyRef.Name}, &cm); err != nil {
			return nil, fmt.Errorf("configmap %s: %w", src.ConfigMapKeyRef.Name, err)
		}
		if v, ok := cm.Data[src.ConfigMapKeyRef.Key]; ok {
			return []byte(v), nil
		}
		if v, ok := cm.BinaryData[src.ConfigMapKeyRef.Key]; ok {
			return v, nil
		}
		return nil, fmt.Errorf("configmap %s has no key %s", src.ConfigMapKeyRef.Name, src.ConfigMapKeyRef.Key)
	case src.URL != "":
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, src.URL, nil)
		if err != nil {
			return nil, permanent("document %s: %v", d.Name, err)
		}
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			return nil, err
		}
		defer resp.Body.Close() //nolint:errcheck
		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("document %s: GET %s: HTTP %d", d.Name, src.URL, resp.StatusCode)
		}
		return io.ReadAll(io.LimitReader(resp.Body, maxDocumentBytes+1))
	}
	return nil, permanent("document %s: set source.inline, source.url or source.configMapKeyRef", d.Name)
}

func (r *RAGPipelineReconciler) apply(ctx context.Context, obj *unifaiv1.UnifaiRAGPipeline) error {
	files := make([]map[string]any, 0, len(obj.Spec.Documents))
	data := make([]map[string]any, 0, len(obj.Spec.Documents))
	digest := map[string]any{}
	for _, d := range obj.Spec.Documents {
		c, err := r.content(ctx, obj.Namespace, d)
		if err != nil {
			return err
		}
		if len(c) > maxDocumentBytes {
			return permanent("document %s is larger than 50 MiB", d.Name)
		}
		s := sha256.Sum256(c)
		meta, err := rawMap(d.Metadata)
		if err != nil {
			return err
		}
		tags := d.Tags
		if tags == nil {
			tags = []string{}
		}
		digest[d.Name] = []any{hex.EncodeToString(s[:]), tags, meta}
		files = append(files, map[string]any{"name": d.Name, "content": base64.StdEncoding.EncodeToString(c)})
		data = append(data, map[string]any{"source_name": d.Name, "tags": tags, "metadata": meta})
	}
	h := hash(digest)
	if obj.Status.Hash == h {
		return nil
	}
	api := r.rag(obj)
	if err := api.Call(ctx, http.MethodPost, "/api/docs/upload", nil, map[string]any{"files": files}, nil); err != nil {
		return permanentOn(err, http.StatusBadRequest, http.StatusUnprocessableEntity)
	}
	var out map[string]any
	if err := api.Call(ctx, http.MethodPut, "/api/pipelines/embed", nil, map[string]any{
		"source_type": "document", "skip_validation": obj.Spec.SkipValidation, "data": data,
	}, &out); err != nil {
		return permanentOn(err, http.StatusBadRequest, http.StatusUnprocessableEntity)
	}
	b, _ := json.Marshal(out)
	obj.Status.Hash, obj.Status.Response = h, unifai.Truncate(string(b), 1500)
	setReady(&obj.Status, "Submitted", "pipeline dispatched to the rag workers")
	return nil
}

// SetupWithManager registers the controller.
func (r *RAGPipelineReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiRAGPipeline{}).Named("unifairagpipeline").Complete(r)
}
