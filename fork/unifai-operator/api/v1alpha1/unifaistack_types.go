package v1alpha1

import (
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// StackName is the only name an UnifaiStack may have: it makes the stack a per-namespace singleton.
const StackName = "unifai"

// StorageSpec configures persistent volumes.
type StorageSpec struct {
	// StorageClass for ReadWriteOnce volumes (MongoDB, Qdrant, Redis, Temporal, RabbitMQ). Empty = cluster default.
	// +optional
	ClassName string `json:"className,omitempty"`
	// StorageClass for the ReadWriteMany volumes shared by several pods (rag, multiagent, logging). Empty = cluster default.
	// +optional
	SharedClassName string `json:"sharedClassName,omitempty"`
	// Size overrides by volume: mongodb, qdrant, redis, redisInsight, temporal, rabbitmq, ragShared, multiagentShared, logging, docling, keycloakDb.
	// +optional
	Sizes map[string]string `json:"sizes,omitempty"`
}

// ExposureSpec configures how the stack is reached from outside the namespace.
type ExposureSpec struct {
	// Apps domain used to build hosts. Empty = OpenShift cluster ingress domain.
	// +optional
	Domain string `json:"domain,omitempty"`
	// UI host. Default: unifai-ui-<namespace>.<domain>.
	// +optional
	UIHost string `json:"uiHost,omitempty"`
	// Identity host. Default: unifai-identity-<namespace>.<domain>.
	// +optional
	IdentityHost string `json:"identityHost,omitempty"`
	// Also create the upstream Routes of internal services (mongodb, qdrant, redis-insight, temporal, backend, multiagent-be).
	// They have no authentication: keep false outside of debugging.
	// +optional
	ExposeInternal bool `json:"exposeInternal,omitempty"`
	// Restrict ingress to the namespace, the OpenShift router and the operator (the internal APIs trust an identity header).
	// +kubebuilder:default=true
	// +optional
	NetworkPolicy *bool `json:"networkPolicy,omitempty"`
}

// ExternalOIDCSpec points the identity service to an existing Keycloak realm.
type ExternalOIDCSpec struct {
	// Keycloak base URL, e.g. https://keycloak.example.com
	URL string `json:"url"`
	// +kubebuilder:default=unifai
	// +optional
	Realm string `json:"realm,omitempty"`
	// +kubebuilder:default=unifai
	// +optional
	ClientID     string            `json:"clientId,omitempty"`
	ClientSecret SecretKeySelector `json:"clientSecret"`
}

// KeycloakDatabaseSpec selects the database of a managed Keycloak.
type KeycloakDatabaseSpec struct {
	// auto = Crunchy PostgresCluster when the Crunchy operator serves this namespace, else a PostgreSQL StatefulSet.
	// +kubebuilder:validation:Enum=auto;crunchy;statefulset
	// +kubebuilder:default=auto
	// +optional
	Type string `json:"type,omitempty"`
	// PostgreSQL image of the StatefulSet mode.
	// +optional
	Image string `json:"image,omitempty"`
}

// ManagedKeycloakSpec deploys Keycloak (Red Hat build of Keycloak operator) and the UnifAI realm in the stack namespace.
type ManagedKeycloakSpec struct {
	// Install the RHBK operator in the namespace (OperatorGroup + Subscription) when it does not serve it yet.
	// +kubebuilder:default=true
	// +optional
	InstallOperator *bool `json:"installOperator,omitempty"`
	// RHBK Subscription channel.
	// +kubebuilder:default=stable-v26.6
	// +optional
	Channel string `json:"channel,omitempty"`
	// Keycloak host. Default: unifai-keycloak-<namespace>.<domain>.
	// +optional
	Host string `json:"host,omitempty"`
	// +optional
	Database KeycloakDatabaseSpec `json:"database,omitempty"`
	// Password of the realm users listed in identity.adminUsers. Default: generated (key keycloak-admin-password of the generated secret).
	// +optional
	AdminPassword *SecretKeySelector `json:"adminPassword,omitempty"`
}

// IdentitySpec configures authentication (exactly one of external or keycloak).
// +kubebuilder:validation:XValidation:rule="has(self.external) != has(self.keycloak)",message="set exactly one of identity.external or identity.keycloak"
type IdentitySpec struct {
	// UnifAI administrators (Keycloak usernames).
	// +kubebuilder:default={admin}
	// +optional
	AdminUsers []string `json:"adminUsers,omitempty"`
	// Let workflow elements that opt in (forward_user_token) send the acting user's OIDC token to model and tool
	// gateways: the multiagent pods get the Keycloak client of the identity service to refresh it.
	// +optional
	ForwardUserToken bool `json:"forwardUserToken,omitempty"`
	// +optional
	External *ExternalOIDCSpec `json:"external,omitempty"`
	// +optional
	Keycloak *ManagedKeycloakSpec `json:"keycloak,omitempty"`
}

// DoclingSpec configures document conversion. The upstream rag image has no in-process converter: documents are
// always converted by a docling-serve service.
// +kubebuilder:validation:XValidation:rule="self.mode != 'remote' || has(self.url)",message="docling.url is required with mode remote"
type DoclingSpec struct {
	// deploy (or local) = docling-serve (CPU) deployed in the stack namespace; remote = existing service at url.
	// +kubebuilder:validation:Enum=deploy;local;remote
	// +kubebuilder:default=deploy
	// +optional
	Mode string `json:"mode,omitempty"`
	// +optional
	URL string `json:"url,omitempty"`
}

// EmbeddingSpec configures the embedding service (OpenAI-compatible /v1/embeddings, e.g. Text Embeddings Inference).
// +kubebuilder:validation:XValidation:rule="self.mode != 'remote' || has(self.url)",message="embedding.url is required with mode remote"
type EmbeddingSpec struct {
	// deploy (or local) = Text Embeddings Inference (CPU) deployed in the stack namespace; remote = service at url.
	// +kubebuilder:validation:Enum=deploy;local;remote
	// +kubebuilder:default=deploy
	// +optional
	Mode string `json:"mode,omitempty"`
	// +optional
	URL string `json:"url,omitempty"`
	// Hugging Face model id (deploy) or model name sent to the remote service.
	// +kubebuilder:default="sentence-transformers/all-MiniLM-L6-v2"
	// +optional
	Model string `json:"model,omitempty"`
	// Vector size of the model (Qdrant collections are created with it).
	// +kubebuilder:default=384
	// +optional
	Dimension int `json:"dimension,omitempty"`
}

// RAGSpec configures the RAG data pipeline.
type RAGSpec struct {
	// Request one nvidia.com/gpu for rag-celery (upstream default). Without it, ingestion runs on CPU.
	// +optional
	GPU bool `json:"gpu,omitempty"`
	// +optional
	Docling DoclingSpec `json:"docling,omitempty"`
	// +optional
	Embedding EmbeddingSpec `json:"embedding,omitempty"`
	// Dense + sparse (BM25) search with rank fusion. Uses new `<collection>_hybrid` collections: existing
	// sources must be re-ingested.
	// +optional
	Hybrid bool `json:"hybrid,omitempty"`
	// Users allowed to publish shared sources (visible to members of the source's ACL groups). Empty =
	// every source stays private to its uploader. UnifaiRAGSource objects are published as their owner.
	// +optional
	SharedPublishers []string `json:"sharedPublishers,omitempty"`
	// Credentials of the Confluence source type.
	// +optional
	Confluence *ConfluenceSpec `json:"confluence,omitempty"`
}

// ConfluenceSpec holds the credentials the RAG service uses for Confluence sources: basic auth with an API
// token, or a bearer token when only the token is set.
type ConfluenceSpec struct {
	// +optional
	Username *SecretKeySelector `json:"username,omitempty"`
	Token    SecretKeySelector  `json:"token"`
	// +kubebuilder:default=true
	// +optional
	VerifyTLS *bool `json:"verifyTLS,omitempty"`
}

// SlackSpec configures the Slack integration (RAG Slack source and backend socket-mode bot).
type SlackSpec struct {
	// +optional
	BotToken *SecretKeySelector `json:"botToken,omitempty"`
	// +optional
	UserToken *SecretKeySelector `json:"userToken,omitempty"`
	// App-level token: enables the backend slack-socket sidecar.
	// +optional
	AppToken *SecretKeySelector `json:"appToken,omitempty"`
	// +optional
	SigningSecret *SecretKeySelector `json:"signingSecret,omitempty"`
}

// UmamiSpec configures UI analytics.
type UmamiSpec struct {
	URL string `json:"url"`
	// +optional
	WebsiteName string `json:"websiteName,omitempty"`
	// +optional
	Username *SecretKeySelector `json:"username,omitempty"`
	// +optional
	Password *SecretKeySelector `json:"password,omitempty"`
}

// LangfuseSpec configures LLM tracing.
type LangfuseSpec struct {
	// +kubebuilder:default="https://us.cloud.langfuse.com"
	// +optional
	BaseURL   string            `json:"baseUrl,omitempty"`
	PublicKey SecretKeySelector `json:"publicKey"`
	SecretKey SecretKeySelector `json:"secretKey"`
}

// IntegrationsSpec groups optional third-party integrations.
type IntegrationsSpec struct {
	// +optional
	Slack *SlackSpec `json:"slack,omitempty"`
	// +optional
	Umami *UmamiSpec `json:"umami,omitempty"`
	// +optional
	Langfuse *LangfuseSpec `json:"langfuse,omitempty"`
	// GCP service account key (JSON) for Vertex AI agents (claude_agent_node).
	// +optional
	GCPServiceAccountKey *SecretKeySelector `json:"gcpServiceAccountKey,omitempty"`
}

// UnifaiStackSpec defines a complete UnifAI deployment in the namespace of the resource.
type UnifaiStackSpec struct {
	// dev = small resource requests and no autoscaling; prod = upstream requests (~25 CPU / 60 GiB).
	// +kubebuilder:validation:Enum=dev;prod
	// +kubebuilder:default=dev
	// +optional
	Profile string `json:"profile,omitempty"`
	// Tag of the UnifAI images (<registry>/unifai-{rag,multiagent,backend,identity,ui}). Default: the operator's.
	// +optional
	Version string `json:"version,omitempty"`
	// Registry and organization of the UnifAI images.
	// +kubebuilder:default="quay.io/zuno"
	// +optional
	ImageRegistry string `json:"imageRegistry,omitempty"`
	// +kubebuilder:validation:Enum=Always;IfNotPresent;Never
	// +optional
	ImagePullPolicy corev1.PullPolicy `json:"imagePullPolicy,omitempty"`
	// +optional
	ImagePullSecrets []corev1.LocalObjectReference `json:"imagePullSecrets,omitempty"`
	// Full image overrides by component: mongodb, qdrant, rabbitmq, redis, redisInsight, temporal, rag, multiagent, backend, identity, ui, docling, embedding.
	// +optional
	Images map[string]string `json:"images,omitempty"`
	// +optional
	Storage StorageSpec `json:"storage,omitempty"`
	// Resource overrides by component (same keys as images, plus ragCelery, multiagentWorker).
	// +optional
	Resources map[string]corev1.ResourceRequirements `json:"resources,omitempty"`
	// Extra environment variables by component (multiagent, multiagentWorker, rag, ragCelery, backend, identity, ui),
	// added to every container of its Deployments; a variable of the chart with the same name is replaced. Values can
	// come from Secrets or ConfigMaps of the namespace (valueFrom).
	// +kubebuilder:validation:XValidation:rule="self.all(k, k in ['multiagent', 'multiagentWorker', 'rag', 'ragCelery', 'backend', 'identity', 'ui'])",message="extraEnv keys: multiagent, multiagentWorker, rag, ragCelery, backend, identity, ui"
	// +optional
	ExtraEnv map[string][]corev1.EnvVar `json:"extraEnv,omitempty"`
	// Added to every UnifAI pod.
	// +optional
	NodeSelector map[string]string `json:"nodeSelector,omitempty"`
	// +optional
	Tolerations []corev1.Toleration `json:"tolerations,omitempty"`
	// +optional
	Exposure ExposureSpec `json:"exposure,omitempty"`
	Identity IdentitySpec `json:"identity"`
	// +optional
	RAG RAGSpec `json:"rag,omitempty"`
	// +optional
	Integrations IntegrationsSpec `json:"integrations,omitempty"`
	// Secret whose keys override the generated ones (SECRET_KEY, CREDENTIAL_ENCRYPTION_KEY, OAUTH_STATE_SECRET, REDIS_PASSWORD, ...).
	// +optional
	SecretsRef *corev1.LocalObjectReference `json:"secretsRef,omitempty"`
	// Retain keeps PVCs, the generated secret and the Keycloak database when the stack is deleted; Delete removes them.
	// +kubebuilder:validation:Enum=Retain;Delete
	// +kubebuilder:default=Retain
	// +optional
	DeletionPolicy string `json:"deletionPolicy,omitempty"`
	// Stop reconciling (nothing is changed or deleted).
	// +optional
	Paused bool `json:"paused,omitempty"`
	// Scheduled backups of MongoDB (mongodump archive) and Qdrant (one snapshot per collection) to S3.
	// +optional
	Backup *BackupSpec `json:"backup,omitempty"`
	// OpenTelemetry export (OTLP) of the multiagent, RAG and backend services (global_utils telemetry bootstrap).
	// +optional
	OpenTelemetry *OpenTelemetrySpec `json:"openTelemetry,omitempty"`
}

// OpenTelemetrySpec sets the OTEL_* environment of the multiagent (server and Temporal worker), RAG (server and
// Celery) and backend pods. Each one reports as its Helm release name (OTEL_SERVICE_NAME), with the attribute
// k8s.namespace.name.
type OpenTelemetrySpec struct {
	// OTLP endpoint of the collector, e.g. http://otel-collector.monitoring.svc:4318.
	// +kubebuilder:validation:MinLength=1
	Endpoint string `json:"endpoint"`
	// OTLP protocol; empty = the SDK default (grpc). Port 4318 is http/protobuf.
	// +kubebuilder:validation:Enum=grpc;http/protobuf
	// +optional
	Protocol string `json:"protocol,omitempty"`
	// Trace sampler (OTEL_TRACES_SAMPLER); empty = the SDK default (parentbased_always_on).
	// +kubebuilder:validation:Enum=always_on;always_off;traceidratio;parentbased_always_on;parentbased_always_off;parentbased_traceidratio
	// +optional
	Sampler string `json:"sampler,omitempty"`
	// Sampler argument (OTEL_TRACES_SAMPLER_ARG), e.g. "0.1" for a ratio sampler.
	// +kubebuilder:validation:Pattern=`^(0(\.[0-9]+)?|1(\.0+)?)$`
	// +optional
	SamplerArg string `json:"samplerArg,omitempty"`
	// Export traces only (OTEL_METRICS_EXPORTER=none).
	// +optional
	DisableMetrics bool `json:"disableMetrics,omitempty"`
	// Added to OTEL_RESOURCE_ATTRIBUTES, e.g. deployment.environment: demo.
	// +optional
	ResourceAttributes map[string]string `json:"resourceAttributes,omitempty"`
}

// BackupSpec schedules backups to an S3-compatible bucket, under <prefix>/mongodb/ and <prefix>/qdrant/<timestamp>/.
type BackupSpec struct {
	// Cron schedule of both backup CronJobs.
	// +kubebuilder:default="0 2 * * *"
	// +optional
	Schedule string       `json:"schedule,omitempty"`
	S3       BackupS3Spec `json:"s3"`
	// Backups kept per store; older ones are deleted after each successful run.
	// +kubebuilder:validation:Minimum=1
	// +kubebuilder:default=7
	// +optional
	Retention int `json:"retention,omitempty"`
	// Suspend both CronJobs.
	// +optional
	Suspend bool `json:"suspend,omitempty"`
	// Image overrides (defaults: public.ecr.aws/aws-cli/aws-cli and docker.io/library/mongo, pinned).
	// +optional
	Images BackupImages `json:"images,omitempty"`
}

// BackupS3Spec locates the bucket. The credentials Secret holds AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.
type BackupS3Spec struct {
	// Endpoint URL of a non-AWS S3 service (e.g. https://s3.example.com); empty = AWS.
	// +optional
	Endpoint string `json:"endpoint,omitempty"`
	Bucket   string `json:"bucket"`
	// Key prefix (default: unifai/<namespace>).
	// +optional
	Prefix string `json:"prefix,omitempty"`
	// +kubebuilder:default=us-east-1
	// +optional
	Region            string `json:"region,omitempty"`
	CredentialsSecret string `json:"credentialsSecret"`
}

// BackupImages overrides the backup tool images.
type BackupImages struct {
	// +optional
	AWSCLI string `json:"awsCli,omitempty"`
	// +optional
	Mongo string `json:"mongo,omitempty"`
}

// ComponentStatus is the state of one Helm release of the stack.
type ComponentStatus struct {
	Name string `json:"name"`
	// +optional
	Revision int `json:"revision,omitempty"`
	// +optional
	Ready bool `json:"ready"`
	// +optional
	Message string `json:"message,omitempty"`
	// Hash of the chart and values last applied.
	// +optional
	Hash string `json:"hash,omitempty"`
}

// StackEndpoints are the URLs of the stack.
type StackEndpoints struct {
	// +optional
	UI string `json:"ui,omitempty"`
	// +optional
	Identity string `json:"identity,omitempty"`
	// +optional
	Keycloak string `json:"keycloak,omitempty"`
	// +optional
	MultiAgent string `json:"multiAgent,omitempty"`
	// +optional
	RAG string `json:"rag,omitempty"`
}

// UnifaiStackStatus defines the observed state of UnifaiStack.
type UnifaiStackStatus struct {
	// Pending, Deploying, Ready, Error, Paused, Deleting.
	// +optional
	Phase string `json:"phase,omitempty"`
	// +optional
	Message string `json:"message,omitempty"`
	// +optional
	ObservedGeneration int64 `json:"observedGeneration,omitempty"`
	// UnifAI image tag deployed.
	// +optional
	Version string `json:"version,omitempty"`
	// Version of the operator that last reconciled the stack.
	// +optional
	OperatorVersion string `json:"operatorVersion,omitempty"`
	// +optional
	Components []ComponentStatus `json:"components,omitempty"`
	// +optional
	Endpoints StackEndpoints `json:"endpoints,omitempty"`
	// +optional
	Conditions []metav1.Condition `json:"conditions,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:shortName=ustack,categories=unifai
// +kubebuilder:validation:XValidation:rule="self.metadata.name == 'unifai'",message="only one UnifaiStack per namespace: its name must be 'unifai'"
// +kubebuilder:printcolumn:name="Phase",type=string,JSONPath=`.status.phase`
// +kubebuilder:printcolumn:name="Version",type=string,JSONPath=`.status.version`
// +kubebuilder:printcolumn:name="UI",type=string,JSONPath=`.status.endpoints.ui`
// +kubebuilder:printcolumn:name="Message",type=string,JSONPath=`.status.message`,priority=1
// +kubebuilder:printcolumn:name="Age",type=date,JSONPath=`.metadata.creationTimestamp`

// UnifaiStack deploys a complete UnifAI platform in its namespace (at most one per namespace, named `unifai`).
type UnifaiStack struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   UnifaiStackSpec   `json:"spec"`
	Status UnifaiStackStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// UnifaiStackList contains a list of UnifaiStack.
type UnifaiStackList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []UnifaiStack `json:"items"`
}

func init() {
	SchemeBuilder.Register(&UnifaiStack{}, &UnifaiStackList{})
}
