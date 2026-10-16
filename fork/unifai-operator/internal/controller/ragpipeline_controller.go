package controller

import (
	"context"
	"crypto/md5" //nolint:gosec
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/unifai"
)

// RAGPipelineReconciler uploads the declared documents to rag-server and dispatches the document pipeline
// (collect, chunk, embed, store in Qdrant) for new or changed documents, and follows the ingestion.
type RAGPipelineReconciler struct{ Base }

// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairagpipelines,verbs=get;list;watch;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairagpipelines/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=unifai.startx.fr,resources=unifairagpipelines/finalizers,verbs=update

const maxDocumentBytes = 50 << 20 // rag-server limit (DocConfigManager.max_file_size_mb)

func (r *RAGPipelineReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	obj := &unifaiv1.UnifaiRAGPipeline{}
	if err := r.get(ctx, req.NamespacedName, obj); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}
	api := r.rag(obj)
	return r.run(ctx, obj, Handlers{
		Apply:  func(ctx context.Context) (time.Duration, error) { return r.apply(ctx, api, obj) },
		Delete: func(ctx context.Context) error { return r.remove(ctx, api, obj) },
	})
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

// ragSource is an entry of rag-server data.sources.get.
type ragSource struct {
	ID       string `json:"source_id"`
	Name     string `json:"source_name"`
	Status   string `json:"status"`
	TypeData struct {
		MD5 string `json:"md5"`
	} `json:"type_data"`
}

func listSources(ctx context.Context, api *unifai.Client) (map[string]ragSource, error) {
	var out struct {
		Sources []ragSource `json:"sources"`
	}
	if err := api.Call(ctx, http.MethodGet, "/api/data_sources/data.sources.get", url.Values{"source_type": {"DOCUMENT"}}, nil, &out); err != nil {
		return nil, err
	}
	m := map[string]ragSource{}
	for _, s := range out.Sources {
		m[s.Name] = s
	}
	return m, nil
}

func deleteSources(ctx context.Context, api *unifai.Client, ids []string) error {
	if len(ids) == 0 {
		return nil
	}
	return api.Call(ctx, http.MethodDelete, "/api/data_sources/data.source.delete", nil, map[string]any{"pipeline_ids": ids}, nil)
}

// apply reconciles document by document: an unchanged document already ingested is kept; a changed document (or one
// whose ingestion never completed) is deleted from the RAG and submitted again (rag-server refuses duplicate names).
// A failed ingestion is not resubmitted until the spec changes.
func (r *RAGPipelineReconciler) apply(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiRAGPipeline) (time.Duration, error) {
	type doc struct {
		files, data map[string]any
		md5         string
	}
	docs := make([]doc, 0, len(obj.Spec.Documents))
	digest := map[string]any{}
	for _, d := range obj.Spec.Documents {
		c, err := r.content(ctx, obj.Namespace, d)
		if err != nil {
			return 0, err
		}
		if len(c) > maxDocumentBytes {
			return 0, permanent("document %s is larger than 50 MiB", d.Name)
		}
		meta, err := rawMap(d.Metadata)
		if err != nil {
			return 0, err
		}
		tags := d.Tags
		if tags == nil {
			tags = []string{}
		}
		sum := md5.Sum(c) //nolint:gosec // matches rag-server's duplicate detection, not a security use
		m := hex.EncodeToString(sum[:])
		digest[d.Name] = []any{m, tags, meta}
		docs = append(docs, doc{
			files: map[string]any{"name": d.Name, "content": base64.StdEncoding.EncodeToString(c)},
			data:  map[string]any{"source_name": d.Name, "tags": tags, "metadata": meta},
			md5:   m,
		})
	}
	h := hash(digest)
	sources, err := listSources(ctx, api)
	if err != nil {
		return 0, err
	}
	var stale []string
	var files, data []map[string]any
	done, failed, running := 0, []string{}, 0
	for _, d := range docs {
		name := d.data["source_name"].(string)
		src, exists := sources[name]
		switch {
		case exists && src.TypeData.MD5 == d.md5 && src.Status == "DONE":
			done++
			continue
		case exists && src.TypeData.MD5 == d.md5 && obj.Status.Hash == h:
			// Already submitted for this spec: report, do not resubmit.
			if src.Status == "FAILED" {
				failed = append(failed, name)
			} else {
				running++
			}
			continue
		case exists:
			stale = append(stale, src.ID)
		}
		files = append(files, d.files)
		data = append(data, d.data)
	}
	if err := deleteSources(ctx, api, stale); err != nil {
		return 0, err
	}
	if len(data) > 0 {
		if err := api.Call(ctx, http.MethodPost, "/api/docs/upload", nil, map[string]any{"files": files}, nil); err != nil {
			return 0, permanentOn(err, http.StatusBadRequest, http.StatusUnprocessableEntity)
		}
		var out struct {
			Registration struct {
				Issues []map[string]any `json:"issues"`
			} `json:"registration"`
		}
		var raw json.RawMessage
		if err := api.Call(ctx, http.MethodPut, "/api/pipelines/embed", nil, map[string]any{
			"source_type": "document", "skip_validation": obj.Spec.SkipValidation, "data": data,
		}, &raw); err != nil {
			return 0, permanentOn(err, http.StatusBadRequest, http.StatusUnprocessableEntity)
		}
		_ = json.Unmarshal(raw, &out)
		obj.Status.Response = unifai.Truncate(string(raw), 1500)
		if len(out.Registration.Issues) > 0 {
			b, _ := json.Marshal(out.Registration.Issues)
			return 0, fmt.Errorf("rag-server refused documents: %s", unifai.Truncate(string(b), 400))
		}
		obj.Status.Hash = h
		setReady(&obj.Status, "Ingesting", fmt.Sprintf("%d document(s) submitted, %d already ingested", len(data), done))
		return 30 * time.Second, nil
	}
	obj.Status.Hash = h
	switch {
	case len(failed) > 0:
		setReady(&obj.Status, "Failed", fmt.Sprintf("ingestion failed for %v (change the spec to retry)", failed))
		return 0, nil
	case running > 0:
		setReady(&obj.Status, "Ingesting", fmt.Sprintf("%d/%d documents ingested", done, len(docs)))
		return 30 * time.Second, nil
	}
	setReady(&obj.Status, "Ready", fmt.Sprintf("%d document(s) ingested", done))
	return 0, nil
}

// remove deletes the documents of the resource from the RAG.
func (r *RAGPipelineReconciler) remove(ctx context.Context, api *unifai.Client, obj *unifaiv1.UnifaiRAGPipeline) error {
	sources, err := listSources(ctx, api)
	if err != nil {
		return err
	}
	var ids []string
	for _, d := range obj.Spec.Documents {
		if s, ok := sources[d.Name]; ok {
			ids = append(ids, s.ID)
		}
	}
	return deleteSources(ctx, api, ids)
}

// SetupWithManager registers the controller.
func (r *RAGPipelineReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).For(&unifaiv1.UnifaiRAGPipeline{}).Named("unifairagpipeline").Complete(r)
}
