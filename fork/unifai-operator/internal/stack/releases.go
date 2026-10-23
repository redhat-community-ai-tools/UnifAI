package stack

import (
	"encoding/json"
	"fmt"
	"strings"
)

// Release is one Helm release of the stack (the helmfile releases, without the four "dummy" ConfigMap charts whose
// content the operator now creates directly).
type Release struct {
	// Helm release name (same as the upstream helmfile, so resource names do not change).
	Name  string
	Chart string
	// Key of spec.resources / spec.images for this release's pods.
	Component string
	// Phase 0 = shared resources, 1 = applications, 2 = UI (needs the service ConfigMaps of phase 1).
	Phase int
	// Internal releases only keep their upstream Route with spec.exposure.exposeInternal.
	Internal bool
	// Traced releases get the OTEL_* environment of spec.openTelemetry.
	Traced bool
	// InternalAuth releases get INTERNAL_AUTH_SECRET (secretKeyRef to InternalAuthSecret).
	InternalAuth bool
	// IdentityEnv is the variable through which the release calls the identity API service to service; it is set
	// to the identity Service (the public Route strips X-Internal-Auth). Releases that also need the public URL
	// (OAuth callbacks) keep it in IDENTITY_HOST and get the internal one in DIRECTORY_SSO_URL.
	IdentityEnv string
	Enabled     func(p *Plan) bool
	Values      func(p *Plan) (map[string]any, error)
}

// IsEnabled reports whether the release is part of the plan.
func (r Release) IsEnabled(p *Plan) bool { return r.Enabled == nil || r.Enabled(p) }

// Releases is the ordered list of releases of a stack.
var Releases = []Release{
	{Name: "unifai-mongodb", Chart: "mongodb", Component: "mongodb", Phase: 0, Internal: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("shared-resource-values.yaml", "mongodb")
		return storage(p, v, err, "mongodb", "storage.className", "storage.requestedSize", "100G", false)
	}},
	{Name: "unifai-qdrant", Chart: "qdrant", Component: "qdrant", Phase: 0, Internal: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("shared-resource-values.yaml", "qdrant")
		return storage(p, v, err, "qdrant", "storage.className", "storage.requestedSize", "100Gi", false)
	}},
	{Name: "unifai-rabbitmq", Chart: "rabbitmq", Component: "rabbitmq", Phase: 0, Internal: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("shared-resource-values.yaml", "rabbitmq")
		if err != nil {
			return nil, err
		}
		set(v, "global.storageClass", p.Spec.Storage.ClassName)
		return storage(p, v, nil, "rabbitmq", "persistence.storageClass", "persistence.size", "8Gi", false)
	}},
	{Name: "unifai-redis", Chart: "redis", Component: "redis", Phase: 0, Internal: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("shared-resource-values.yaml", "redis")
		return storage(p, v, err, "redis", "storage.storageClassName", "storage.size", "10Gi", false)
	}},
	{Name: "unifai-redis-insight", Chart: "redis-insight", Component: "redisInsight", Phase: 0, Internal: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("shared-resource-values.yaml", "redis-insight")
		return storage(p, v, err, "redisInsight", "storage.storageClassName", "storage.size", "2Gi", false)
	}},
	{Name: "unifai-temporal", Chart: "temporal", Component: "temporal", Phase: 0, Internal: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("shared-resource-values.yaml", "temporal")
		return storage(p, v, err, "temporal", "storage.storageClassName", "storage.size", "10Gi", false)
	}},
	{Name: "unifai-logging", Chart: "logging", Component: "logging", Phase: 0, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("shared-resource-values.yaml", "logging")
		return storage(p, v, err, "logging", "storage.className", "storage.requestedSize", "100Gi", true)
	}},

	{Name: "unifai-rag-shared-storage", Chart: "unifai-rag-shared-storage", Component: "ragShared", Phase: 1, Values: func(p *Plan) (map[string]any, error) {
		s, err := valuesFile("rag-resource-values.yaml", "storage")
		v, err := storage(p, map[string]any{"storage": s}, err, "ragShared", "storage.className", "storage.requestedSize", "100Gi", true)
		return withGlobal(p, v, err, false)
	}},
	{Name: "unifai-rag-server", IdentityEnv: "IDENTITY_HOST", Chart: "unifai-rag-server", Component: "rag", Phase: 1, Traced: true, InternalAuth: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("rag-resource-values.yaml", "unifai_rag_server")
		v = ragValues(p, v)
		if v != nil && p.Spec.RAG.TokenReview {
			set(v, "env.RAG_TOKENREVIEW_ENABLED", "true")
			set(v, "serviceAccount.create", true)
			set(v, "serviceAccount.name", RAGServiceAccount)
		}
		return withGlobal(p, v, err, false)
	}},
	{Name: "unifai-rag-celery", IdentityEnv: "IDENTITY_HOST", Chart: "unifai-rag-celery", Component: "ragCelery", Phase: 1, Traced: true, InternalAuth: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("rag-resource-values.yaml", "unifai_rag_celery")
		return withGlobal(p, ragValues(p, v), err, false)
	}},
	{Name: "unifai-multiagent-shared-storage", Chart: "unifai-multiagent-shared-storage", Component: "multiagentShared", Phase: 1, Values: func(p *Plan) (map[string]any, error) {
		s, err := valuesFile("multiagent-resource-values.yaml", "storage")
		v, err := storage(p, map[string]any{"storage": s}, err, "multiagentShared", "storage.className", "storage.requestedSize", "50Gi", true)
		return withGlobal(p, v, err, true)
	}},
	{Name: "unifai-multiagent-be", IdentityEnv: "DIRECTORY_SSO_URL", Chart: "be", Component: "multiagent", Phase: 1, Internal: true, Traced: true, InternalAuth: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("multiagent-resource-values.yaml", "multiagent_server")
		return withGlobal(p, multiagentValues(p, v), err, true)
	}},
	{Name: "unifai-multiagent-temporal-worker", IdentityEnv: "DIRECTORY_SSO_URL", Chart: "temporal-worker", Component: "multiagentWorker", Phase: 1, Traced: true, InternalAuth: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("multiagent-resource-values.yaml", "multiagent_temporal_worker")
		return withGlobal(p, multiagentValues(p, v), err, true)
	}},
	{Name: "unifai-backend", IdentityEnv: "IDENTITY_HOST", Chart: "unifai-backend", Component: "backend", Phase: 1, Internal: true, Traced: true, InternalAuth: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("backend-resource-values.yaml", "unifai_backend")
		if err != nil {
			return nil, err
		}
		appImage(p, v, "image", "backend")
		// Upstream points the backend at port 13457; rag-server listens on 13456.
		set(v, "env.RAG_URL", fmt.Sprintf("http://unifai-rag-server:%d", 13456))
		slack := p.Spec.Integrations.Slack
		set(v, "slackSocket.enabled", slack != nil && slack.AppToken != nil)
		return withGlobal(p, v, nil, false)
	}},
	{Name: "unifai-identity", Chart: "identity", Component: "identity", Phase: 1, InternalAuth: true, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("identity-values.yaml", "")
		if err != nil {
			return nil, err
		}
		appImage(p, v, "backend.image", "identity")
		return withGlobal(p, v, nil, false)
	}},
	{Name: "unifai-docling", Chart: "docling", Component: "docling", Phase: 1,
		Enabled: func(p *Plan) bool { return p.DeployDocling() },
		Values: func(p *Plan) (map[string]any, error) {
			v, err := valuesFile("docling-values-cpu.yaml", "")
			if err != nil {
				return nil, err
			}
			// The upstream "cpu" values still carry GPU settings.
			delete(v, "tolerations")
			var env []any
			for _, e := range asSlice(v["env"]) {
				if m, ok := e.(map[string]any); ok && strings.Contains(fmt.Sprint(m["name"]), "VISIBLE_DEVICES") ||
					ok && m["name"] == "NVIDIA_DRIVER_CAPABILITIES" {
					continue
				}
				env = append(env, e)
			}
			v["env"] = env
			set(v, "config.processing.enableGPU", false)
			set(v, "route.enabled", false)
			return storage(p, v, nil, "docling", "storage.className", "storage.requestedSize", "10Gi", false)
		}},

	{Name: "unifai-ui", Chart: "ui", Component: "ui", Phase: 2, Values: func(p *Plan) (map[string]any, error) {
		v, err := valuesFile("ui-values.yaml", "ui")
		if err != nil {
			return nil, err
		}
		appImage(p, v, "image", "ui")
		return withGlobal(p, v, nil, false)
	}},
}

// In-namespace URLs of the deployed docling and embedding services.
const (
	DoclingURL   = "http://docling-serve:5001" // fullnameOverride of the upstream chart
	EmbeddingURL = "http://unifai-embedding:8080"
)

func mapAt(m map[string]any, key string) map[string]any {
	if v, ok := m[key].(map[string]any); ok {
		return v
	}
	return map[string]any{}
}

// storage applies the image, storage class and size of a release whose chart reads them at the given keys.
func storage(p *Plan, v map[string]any, err error, component, classKey, sizeKey, defSize string, shared bool) (map[string]any, error) {
	if err != nil {
		return nil, err
	}
	if img := p.imageValues(component); len(img) > 0 {
		v["image"] = merge(mapAt(v, "image"), img)
	}
	class := p.Spec.Storage.ClassName
	if shared {
		class = p.Spec.Storage.SharedClassName
	}
	set(v, classKey, class)
	set(v, sizeKey, p.size(component, defSize))
	// Red Hat PaaS-only metadata of the upstream values.
	if s, ok := v["storage"].(map[string]any); ok {
		delete(s, "labels")
		delete(s, "storageClassName")
		if classKey == "storage.storageClassName" {
			s["storageClassName"] = class
		}
	}
	return v, nil
}

// appImage sets repository/tag (and pull policy) of an UnifAI image at dotted key prefix.
func appImage(p *Plan, v map[string]any, key, component string) {
	repo, tag := p.appImage(component)
	set(v, key+".repository", repo)
	set(v, key+".tag", tag)
	if p.Spec.ImagePullPolicy != "" {
		set(v, key+".pullPolicy", string(p.Spec.ImagePullPolicy))
	}
}

// withGlobal merges the upstream global-config.yaml (env shared by the apps) with the stack URLs.
// The helmfile passes it before (globalFirst) or after the release values; the merge order is preserved.
func withGlobal(p *Plan, v map[string]any, err error, globalFirst bool) (map[string]any, error) {
	if err != nil {
		return nil, err
	}
	g, err := valuesFile("global-config.yaml", "")
	if err != nil {
		return nil, err
	}
	set(g, "env.FRONTEND_URL", "https://"+p.UIHost)
	set(g, "env.IDENTITY_HOST", "https://"+p.IdentityHost)
	if globalFirst {
		return merge(g, v), nil
	}
	return merge(v, g), nil
}

// Quiescable reports whether the release is an UnifAI application stopped during a restore (the data stores,
// docling and the embedding service keep running).
func (r Release) Quiescable() bool { return r.InternalAuth || r.Name == uiRelease }

func ragValues(p *Plan, v map[string]any) map[string]any {
	if v == nil {
		return nil
	}
	appImage(p, v, "image", "rag")
	r := p.Spec.RAG
	docling, embedding := r.Docling.URL, r.Embedding.URL
	if p.DeployDocling() {
		docling = DoclingURL
	}
	if p.DeployEmbedding() {
		embedding = EmbeddingURL
	}
	// The upstream rag image has neither docling nor sentence-transformers: both are always remote services.
	set(v, "env.USE_REMOTE_DOCLING", boolStr(true))
	set(v, "env.DOCLING_SERVICE_URL", docling)
	set(v, "env.USE_REMOTE_EMBEDDING", boolStr(true))
	set(v, "env.EMBEDDING_SERVICE_URL", embedding)
	set(v, "env.EMBEDDING_SERVICE_MODEL", p.EmbeddingModel())
	if r.Embedding.Dimension > 0 {
		set(v, "env.EMBEDDING_DIM", fmt.Sprint(r.Embedding.Dimension))
	}
	// Every addition below is conditional: with the new fields unset the release hash is unchanged and
	// existing stacks do not roll.
	if r.Hybrid {
		set(v, "env.QDRANT_HYBRID_ENABLED", "true")
	}
	if len(r.SharedPublishers) > 0 {
		publishers, _ := json.Marshal(r.SharedPublishers)
		set(v, "env.RAG_SHARED_PUBLISHERS", string(publishers))
		if p.OIDCURL != "" && p.OIDCRealm != "" {
			// Lets the RAG service verify user tokens forwarded by multiagent (shared-source ACLs).
			set(v, "env.OIDC_ISSUER_URL", strings.TrimRight(p.OIDCURL, "/")+"/realms/"+p.OIDCRealm)
		}
	}
	if c := r.Confluence; c != nil {
		// Celery workers consume one queue per source type (confluence and web sources share this switch:
		// the default queues stay unchanged so existing stacks do not roll).
		set(v, "env.CELERY_QUEUES", "slack_queue,document_queue,slack_events_queue,confluence_queue,web_queue")
		if c.VerifyTLS != nil && !*c.VerifyTLS {
			set(v, "env.CONFLUENCE_VERIFY_TLS", "false")
		}
	}
	return v
}

func multiagentValues(p *Plan, v map[string]any) map[string]any {
	if v == nil {
		return nil
	}
	appImage(p, v, "image", "multiagent")
	if p.Spec.Identity.ForwardUserToken {
		// CLIENT_SECRET comes from multiagent-be-secret (objects.go), loaded by both multiagent pods.
		set(v, "env.IDENTITY_FORWARDING_ENABLED", "true")
		set(v, "env.KEYCLOAK_BASE_URL", p.OIDCURL)
		set(v, "env.KEYCLOAK_REALM", p.OIDCRealm)
		set(v, "env.CLIENT_ID", p.OIDCClientID)
	}
	lf := p.Spec.Integrations.Langfuse
	set(v, "env.LANGFUSE_ENABLED", fmt.Sprint(lf != nil))
	if lf != nil && lf.BaseURL != "" {
		set(v, "env.LANGFUSE_BASE_URL", lf.BaseURL)
	}
	return v
}
