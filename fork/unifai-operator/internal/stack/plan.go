package stack

import (
	"encoding/json"

	corev1 "k8s.io/api/core/v1"
	"fmt"
	"strings"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// DefaultVersion is the UnifAI image tag deployed when spec.version is empty (set at build time).
var DefaultVersion = "devel"

// Plan is everything derived from an UnifaiStack before rendering.
type Plan struct {
	Namespace    string
	Spec         *unifaiv1.UnifaiStackSpec
	Version      string
	Domain       string
	UIHost       string
	IdentityHost string
	KeycloakHost string
	// Secrets holds generated values overlaid with spec.secretsRef and integration secrets (see secrets.go).
	Secrets map[string]string
	// OIDC settings of the identity service.
	OIDCURL, OIDCRealm, OIDCClientID, OIDCClientSecret string
	// OperatorNamespace is allowed through the stack NetworkPolicy.
	OperatorNamespace string
	// ConfigHash changes with the ConfigMaps/Secrets read by the pods; it is set on pod templates so they restart.
	ConfigHash string
	// LiveVolumes holds the specs of the PVCs ("pvc/<name>") and StatefulSet claim templates ("<sts>/<claim>")
	// that already exist: volumes are never resized or moved to another class (immutable or unsafe), so stacks
	// installed by an older version or by helmfile keep their volumes.
	LiveVolumes map[string]corev1.PersistentVolumeClaimSpec
	// LiveClaimTemplates are the existing StatefulSet claim templates ("<sts>/<claim>"), reused verbatim: the
	// whole template (metadata included) is immutable.
	LiveClaimTemplates map[string]corev1.PersistentVolumeClaim
}

// NewPlan derives hosts and the image version; secrets and OIDC are filled by the controller.
func NewPlan(st *unifaiv1.UnifaiStack, clusterDomain, operatorNS string) (*Plan, error) {
	s := &st.Spec
	p := &Plan{Namespace: st.Namespace, Spec: s, Version: s.Version, Domain: s.Exposure.Domain, OperatorNamespace: operatorNS}
	if p.Version == "" {
		p.Version = DefaultVersion
	}
	if p.Domain == "" {
		p.Domain = clusterDomain
	}
	host := func(explicit, name string) string {
		if explicit != "" {
			return explicit
		}
		return fmt.Sprintf("%s-%s.%s", name, st.Namespace, p.Domain)
	}
	if p.Domain == "" && (s.Exposure.UIHost == "" || s.Exposure.IdentityHost == "") {
		return nil, fmt.Errorf("cannot build hosts: set spec.exposure.domain (no OpenShift ingress domain found)")
	}
	p.UIHost = host(s.Exposure.UIHost, "unifai-ui")
	p.IdentityHost = host(s.Exposure.IdentityHost, "unifai-identity")
	if s.Identity.Keycloak != nil {
		p.KeycloakHost = host(s.Identity.Keycloak.Host, "unifai-keycloak")
	}
	return p, nil
}

// Dev reports whether the small-footprint profile is used.
func (p *Plan) Dev() bool { return p.Spec.Profile != "prod" }

// AdminUsers returns the UnifAI administrators (default admin).
func (p *Plan) AdminUsers() []string {
	if len(p.Spec.Identity.AdminUsers) == 0 {
		return []string{"admin"}
	}
	return p.Spec.Identity.AdminUsers
}

// AdminUsersJSON is the JSON list expected by identity/shared-config.
func (p *Plan) AdminUsersJSON() string {
	b, _ := json.Marshal(p.AdminUsers())
	return string(b)
}

// registry returns the registry/org of the UnifAI images.
func (p *Plan) registry() string {
	if p.Spec.ImageRegistry == "" {
		return "quay.io/zuno"
	}
	return strings.TrimRight(p.Spec.ImageRegistry, "/")
}

// appImage returns repository and tag of an UnifAI image (component = rag, multiagent, backend, identity, ui).
func (p *Plan) appImage(component string) (repo, tag string) {
	if img := p.Spec.Images[component]; img != "" {
		return splitTag(img)
	}
	return fmt.Sprintf("%s/unifai-%s", p.registry(), component), p.Version
}

// thirdPartyDefaults are the public images the fork overlay uses instead of the upstream internal registry.
var thirdPartyDefaults = map[string]string{
	"mongodb":      "docker.io/library/mongo",
	"qdrant":       "docker.io/qdrant/qdrant:v1.16.0",
	"rabbitmq":     "docker.io/bitnamilegacy/rabbitmq:4.0.5-debian-12-r0",
	"redis":        "quay.io/fedora/redis-7:20250108",
	"redisInsight": "docker.io/redis/redisinsight:3.4.2",
	"temporal":     "docker.io/temporalio/temporal",
	"docling":      "quay.io/docling-project/docling-serve-cpu:v1.37.0",
	"embedding":    "ghcr.io/huggingface/text-embeddings-inference:cpu-1.9",
}

// imageValues returns {registry, repository[, tag]} for a third-party component.
func (p *Plan) imageValues(component string) map[string]any {
	img := p.Spec.Images[component]
	if img == "" {
		img = thirdPartyDefaults[component]
	}
	if img == "" { // keep the chart's image
		return map[string]any{}
	}
	name, tag := splitTag(img)
	registry, repo := "docker.io", name
	if i := strings.Index(name, "/"); i > 0 && strings.ContainsAny(name[:i], ".:") || strings.HasPrefix(name, "localhost/") {
		registry, repo = name[:i], name[i+1:]
	} else if !strings.Contains(name, "/") {
		repo = "library/" + name
	}
	out := map[string]any{"registry": registry, "repository": repo}
	if tag != "" {
		out["tag"] = tag
	}
	if p.Spec.ImagePullPolicy != "" {
		out["pullPolicy"] = string(p.Spec.ImagePullPolicy)
	}
	return out
}

// splitTag splits "name:tag" (a registry port is not a tag).
func splitTag(img string) (string, string) {
	i := strings.LastIndex(img, ":")
	if i < 0 || strings.Contains(img[i:], "/") {
		return img, ""
	}
	return img[:i], img[i+1:]
}

// size returns the requested size of a volume, or def.
func (p *Plan) size(key, def string) string {
	if v := p.Spec.Storage.Sizes[key]; v != "" {
		return v
	}
	if p.Dev() {
		if v, ok := devSizes[key]; ok {
			return v
		}
	}
	return def
}

// devSizes are the volume sizes of the dev profile (upstream sizes target production).
var devSizes = map[string]string{
	"mongodb": "10Gi", "qdrant": "10Gi", "redis": "2Gi", "redisInsight": "1Gi", "temporal": "2Gi", "rabbitmq": "2Gi",
	"ragShared": "10Gi", "multiagentShared": "5Gi", "logging": "5Gi", "docling": "5Gi", "keycloakDb": "2Gi",
}

func boolStr(b bool) string {
	if b {
		return "True"
	}
	return "False"
}

// DeployDocling reports whether docling-serve runs in the stack namespace.
func (p *Plan) DeployDocling() bool { return p.Spec.RAG.Docling.Mode != "remote" }

// DeployEmbedding reports whether the embedding service runs in the stack namespace.
func (p *Plan) DeployEmbedding() bool { return p.Spec.RAG.Embedding.Mode != "remote" }

// EmbeddingModel is the embedding model (default the upstream one).
func (p *Plan) EmbeddingModel() string {
	if m := p.Spec.RAG.Embedding.Model; m != "" {
		return m
	}
	return "sentence-transformers/all-MiniLM-L6-v2"
}

// fullImage returns the image reference of a component (override or default).
func (p *Plan) fullImage(component string) string {
	if img := p.Spec.Images[component]; img != "" {
		return img
	}
	return thirdPartyDefaults[component]
}
