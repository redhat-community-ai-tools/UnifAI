package stack

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
)

// GeneratedSecretName holds the values generated once per stack; it is never regenerated
// (CREDENTIAL_ENCRYPTION_KEY encrypts the credentials stored in MongoDB).
const GeneratedSecretName = "unifai-generated"

// Generated secret keys.
const (
	KeySecretKey         = "SECRET_KEY"
	KeyCredentialKey     = "CREDENTIAL_ENCRYPTION_KEY"
	KeyOAuthState        = "OAUTH_STATE_SECRET"
	KeyRedisPassword     = "REDIS_PASSWORD"
	KeyClientSecret      = "keycloak-client-secret"
	KeyKeycloakAdminPass = "keycloak-admin-password"
	KeyKeycloakDBPass    = "keycloak-db-password"
)

// generators produce each generated key.
var generators = map[string]func() string{
	KeySecretKey:         func() string { return randomHex(32) },
	KeyCredentialKey:     fernetKey,
	KeyOAuthState:        func() string { return randomHex(32) },
	KeyRedisPassword:     func() string { return randomAlnum(24) },
	KeyClientSecret:      func() string { return randomAlnum(32) },
	KeyKeycloakAdminPass: func() string { return randomAlnum(20) },
	KeyKeycloakDBPass:    func() string { return randomAlnum(24) },
}

// FillGenerated adds the missing generated keys to data and reports whether it changed.
func FillGenerated(data map[string][]byte) bool {
	changed := false
	for k, gen := range generators {
		if len(data[k]) == 0 {
			data[k] = []byte(gen())
			changed = true
		}
	}
	return changed
}

func randomHex(n int) string {
	b := make([]byte, n)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// fernetKey is a urlsafe base64 32-byte key, the format of cryptography.fernet.Fernet.generate_key().
func fernetKey() string {
	b := make([]byte, 32)
	_, _ = rand.Read(b)
	return base64.URLEncoding.EncodeToString(b)
}

const alnum = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

func randomAlnum(n int) string {
	out := make([]byte, n)
	for i := range out {
		x, _ := rand.Int(rand.Reader, big.NewInt(int64(len(alnum))))
		out[i] = alnum[x.Int64()]
	}
	return string(out)
}

func hashOf(v ...any) string {
	b, _ := json.Marshal(v)
	s := sha256.Sum256(b)
	return hex.EncodeToString(s[:])[:16]
}

func objMeta(p *Plan, name, component string) metav1.ObjectMeta {
	return metav1.ObjectMeta{Name: name, Namespace: p.Namespace, Labels: map[string]string{
		LabelPartOf: "unifai", LabelManagedBy: "unifai-operator", LabelComponent: component,
	}}
}

func configMap(p *Plan, name, component string, data map[string]string) *corev1.ConfigMap {
	return &corev1.ConfigMap{ObjectMeta: objMeta(p, name, component), Data: data}
}

func secret(p *Plan, name, component string, data map[string]string) *corev1.Secret {
	return &corev1.Secret{ObjectMeta: objMeta(p, name, component), Type: corev1.SecretTypeOpaque, StringData: data}
}

// BaseObjects are the ConfigMaps and Secrets the upstream presync/postsync hooks created before the releases
// (redis-presync, shared-resources-postsync, rag-presync, multiagent-presync, identity-presync).
func BaseObjects(p *Plan) []ctrlObject {
	s := p.Secrets
	objs := []ctrlObject{
		configMap(p, "redis-config", "redis", map[string]string{"REDIS_PORT": "6379", "RI_APP_PORT": "5540", "RI_REDIS_PORT": "6379"}),
		secret(p, "redis-secret", "redis", map[string]string{
			"REDIS_USERNAME": "default", "REDIS_PASSWORD": s[KeyRedisPassword],
			"RI_REDIS_USERNAME": "default", "RI_REDIS_PASSWORD": s[KeyRedisPassword],
		}),
		configMap(p, "shared-config", "shared", map[string]string{
			"MONGODB_IP": "mongodb", "MONGODB_PORT": "27017", "RABBITMQ_IP": "rabbitmq", "RABBITMQ_PORT": "5672",
			"REDIS_IP": "redis", "REDIS_PORT": "6379", "TEMPORAL_IP": "temporal", "TEMPORAL_PORT": "7233",
			"UMAMI_URL": s["UMAMI_URL"], "UMAMI_WEBSITE_NAME": s["UMAMI_WEBSITE_NAME"], "admin_allowed_users": p.AdminUsersJSON(),
		}),
		secret(p, "shared-secret", "shared", map[string]string{
			"UMAMI_USERNAME": s["UMAMI_USERNAME"], "UMAMI_PASSWORD": s["UMAMI_PASSWORD"], "REDIS_PASSWORD": s[KeyRedisPassword],
			"SECRET_KEY": s[KeySecretKey], "VAULT_ROLE_ID": s["VAULT_ROLE_ID"], "VAULT_SECRET_ID": s["VAULT_SECRET_ID"],
			"LANGFUSE_BASE_URL": s["LANGFUSE_BASE_URL"], "LANGFUSE_PUBLIC_KEY": s["LANGFUSE_PUBLIC_KEY"],
			"LANGFUSE_SECRET_KEY": s["LANGFUSE_SECRET_KEY"], "slack_signing_secret": s["SLACK_SIGNING_SECRET"],
			"SLACK_APP_TOKEN": s["SLACK_APP_TOKEN"], "SLACK_BOT_TOKEN": s["SLACK_BOT_TOKEN"],
		}),
		secret(p, "unifai-rag-secrets", "rag", map[string]string{
			"default_slack_bot_token": s["SLACK_BOT_TOKEN"], "default_slack_user_token": s["SLACK_USER_TOKEN"],
		}),
		secret(p, "multiagent-be-secret", "multiagent", multiagentSecret(p)),
		configMap(p, "identity-config", "identity", map[string]string{
			"admin_allowed_users": p.AdminUsersJSON(), "keycloak_base_url": p.OIDCURL, "client_id": p.OIDCClientID,
			"keycloak_realm": p.OIDCRealm, "directory_provider": "", "directory_url": "", "directory_verify_ssl": "false",
			"directory_ldap_bind_dn": "",
		}),
		secret(p, "identity-secret", "identity", map[string]string{"client_secret": p.OIDCClientSecret, "directory_ldap_bind_password": ""}),
	}
	if key := s["GCP_SA_KEY_JSON"]; key != "" {
		objs = append(objs, secret(p, "gcp-vertex-credentials", "multiagent", map[string]string{"gcp-sa-key.json": key}))
	}
	if p.Spec.Exposure.NetworkPolicy == nil || *p.Spec.Exposure.NetworkPolicy {
		objs = append(objs, networkPolicy(p))
	}
	return objs
}

// ServiceConfigs are the ConfigMaps the postsync hooks derived from each application Service; the UI reads them.
// Key: ConfigMap name -> service name and variable prefix.
var ServiceConfigs = []struct{ ConfigMap, Service, Prefix, Component string }{
	{"unifai-rag-config", "unifai-rag-server", "RAG", "rag"},
	{"multiagent-config", "unifai-multiagent-be", "MULTIAGENT", "multiagent"},
	{"backend-config", "unifai-backend", "BACKEND", "backend"},
	{"identity-svc-config", "identity", "IDENTITY_SVC", "identity"},
}

// ServiceConfig builds one service ConfigMap from its Service.
func ServiceConfig(p *Plan, cmName, prefix, component string, svc *corev1.Service) *corev1.ConfigMap {
	port := ""
	if len(svc.Spec.Ports) > 0 {
		port = fmt.Sprint(svc.Spec.Ports[0].Port)
	}
	return configMap(p, cmName, component, map[string]string{
		prefix + "_ADDR": svc.Spec.ClusterIP, prefix + "_PORT": port, prefix + "_IP": svc.Name,
	})
}

// NetworkPolicyName is the stack's ingress policy.
const NetworkPolicyName = "unifai-stack"

// networkPolicy admits traffic from the namespace itself, the OpenShift router, the monitoring stack and the
// operators (this one and the Crunchy/RHBK ones running in openshift-operators). The UnifAI internal APIs trust an
// X-Authenticated-User header, so they must not be reachable from other namespaces.
func networkPolicy(p *Plan) *networkingv1.NetworkPolicy {
	nsSel := func(labels map[string]string) networkingv1.NetworkPolicyPeer {
		return networkingv1.NetworkPolicyPeer{NamespaceSelector: &metav1.LabelSelector{MatchLabels: labels}}
	}
	peers := []networkingv1.NetworkPolicyPeer{
		{PodSelector: &metav1.LabelSelector{}},
		nsSel(map[string]string{"policy-group.network.openshift.io/ingress": ""}),
		nsSel(map[string]string{"network.openshift.io/policy-group": "monitoring"}),
		nsSel(map[string]string{"kubernetes.io/metadata.name": "openshift-operators"}),
	}
	if p.OperatorNamespace != "" && p.OperatorNamespace != "openshift-operators" && p.OperatorNamespace != p.Namespace {
		peers = append(peers, nsSel(map[string]string{"kubernetes.io/metadata.name": p.OperatorNamespace}))
	}
	return &networkingv1.NetworkPolicy{
		ObjectMeta: objMeta(p, NetworkPolicyName, "shared"),
		Spec: networkingv1.NetworkPolicySpec{
			PodSelector: metav1.LabelSelector{},
			PolicyTypes: []networkingv1.PolicyType{networkingv1.PolicyTypeIngress},
			Ingress:     []networkingv1.NetworkPolicyIngressRule{{From: peers}},
		},
	}
}

// EmbeddingName is the Deployment/Service of the embedding service deployed by the stack.
const EmbeddingName = "unifai-embedding"

// EmbeddingObjects deploys Text Embeddings Inference (CPU), the OpenAI-compatible service the rag pods call.
func EmbeddingObjects(p *Plan) []ctrlObject {
	if !p.DeployEmbedding() {
		return nil
	}
	labels := map[string]string{"app": EmbeddingName, LabelPartOf: "unifai", LabelManagedBy: "unifai-operator", LabelComponent: "embedding"}
	req := corev1.ResourceList{corev1.ResourceCPU: resource.MustParse("1"), corev1.ResourceMemory: resource.MustParse("2Gi")}
	if p.Dev() {
		req = corev1.ResourceList{corev1.ResourceCPU: resource.MustParse("100m"), corev1.ResourceMemory: resource.MustParse("512Mi")}
	}
	res := corev1.ResourceRequirements{Requests: req, Limits: corev1.ResourceList{corev1.ResourceMemory: resource.MustParse("4Gi")}}
	if o, ok := p.Spec.Resources["embedding"]; ok {
		res = o
	}
	one := int32(1)
	probe := func(delay int32) *corev1.Probe {
		return &corev1.Probe{ProbeHandler: corev1.ProbeHandler{HTTPGet: &corev1.HTTPGetAction{Path: "/health", Port: intstr.FromInt32(8080)}},
			InitialDelaySeconds: delay, PeriodSeconds: 10, FailureThreshold: 30}
	}
	dep := &appsv1.Deployment{
		ObjectMeta: objMeta(p, EmbeddingName, "embedding"),
		Spec: appsv1.DeploymentSpec{
			Replicas: &one,
			Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"app": EmbeddingName}},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{Labels: labels},
				Spec: corev1.PodSpec{
					NodeSelector: p.Spec.NodeSelector, Tolerations: p.Spec.Tolerations, ImagePullSecrets: p.Spec.ImagePullSecrets,
					Containers: []corev1.Container{{
						Name: "tei", Image: p.fullImage("embedding"), ImagePullPolicy: p.Spec.ImagePullPolicy,
						Args:           []string{"--model-id", p.EmbeddingModel(), "--port", "8080", "--hostname", "0.0.0.0"},
						Env:            []corev1.EnvVar{{Name: "HF_HOME", Value: "/data"}, {Name: "HUGGINGFACE_HUB_CACHE", Value: "/data"}},
						Ports:          []corev1.ContainerPort{{Name: "http", ContainerPort: 8080}},
						Resources:      res,
						ReadinessProbe: probe(10),
						StartupProbe:   probe(5),
						VolumeMounts:   []corev1.VolumeMount{{Name: "data", MountPath: "/data"}},
					}},
					Volumes: []corev1.Volume{{Name: "data", VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{}}}},
				},
			},
		},
	}
	dep.Labels["app"] = EmbeddingName
	svc := &corev1.Service{
		ObjectMeta: objMeta(p, EmbeddingName, "embedding"),
		Spec: corev1.ServiceSpec{Selector: map[string]string{"app": EmbeddingName},
			Ports: []corev1.ServicePort{{Name: "http", Port: 8080, TargetPort: intstr.FromInt32(8080)}}},
	}
	return []ctrlObject{dep, svc}
}

// multiagentSecret is read (envFrom) by multiagent-be and the temporal worker.
func multiagentSecret(p *Plan) map[string]string {
	s := p.Secrets
	data := map[string]string{
		"CREDENTIAL_ENCRYPTION_KEY": s[KeyCredentialKey], "OAUTH_STATE_SECRET": s[KeyOAuthState],
		"LANGFUSE_SECRET_KEY": s["LANGFUSE_SECRET_KEY"], "LANGFUSE_PUBLIC_KEY": s["LANGFUSE_PUBLIC_KEY"],
	}
	if p.Spec.Identity.ForwardUserToken {
		data["CLIENT_SECRET"] = p.OIDCClientSecret
	}
	return data
}
