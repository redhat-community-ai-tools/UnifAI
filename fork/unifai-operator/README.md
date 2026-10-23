# unifai-operator

Go operator (operator-sdk / controller-runtime) that deploys UnifAI and manages UnifAI objects declaratively.
Fork-only (`fork/`, branch `devel`). API group `unifai.startx.fr/v1alpha1`. Images on `quay.io/zuno`.

## What it manages

| Kind | Role |
|---|---|
| `UnifaiStack` | Deploys a full UnifAI platform in **its own namespace**. One per namespace: the name must be `unifai` (CEL rule in the CRD). |
| `UnifaiLLM`, `UnifaiProvider`, `UnifaiTool`, `UnifaiCondition`, `UnifaiRetriever`, `UnifaiSandbox`, `UnifaiAgent` | Rows of the UnifAI `resources` collection (`/api/resources/*`). |
| `UnifaiWorkflow` | Blueprint (agentic workflow). |
| `UnifaiSchedule` | Scheduled workflow (Temporal). |
| `UnifaiTemplate` | Catalog template (owner must be an UnifAI admin; no update API, so a change deletes and recreates it). |
| `UnifaiChat` | One-shot chat: one session, one prompt, transcript in `status.result`. The spec is immutable. |
| `UnifaiRAGPipeline` | Uploads documents and dispatches the RAG document pipeline. |

`kubectl get unifai -A` lists everything. Examples: [`examples/`](examples/) (one directory per kind) and
[`config/samples/`](config/samples/) (also the OperatorHub `alm-examples`).

### UnifaiStack

The operator replaces the upstream helmfile: the upstream charts (`helm/`) are embedded in the binary
(`internal/stack/assets`, refreshed by `make charts`, never edited) and installed with the Helm SDK. Everything
fork-specific is applied by the operator at render time:

- values: images (`spec.imageRegistry`/`spec.version`, per-component `spec.images`), storage classes and sizes,
  URLs, Docling/embedding mode, Langfuse/Slack switches, `RAG_URL` port fix;
- a post-renderer: dev profile (requests capped to 100m CPU / 512Mi, no HPA), per-component `spec.resources`,
  `nodeSelector`/`tolerations`/`imagePullSecrets`, GPU request of rag-celery only with `spec.rag.gpu`,
  Routes (UI and identity only, unless `spec.exposure.exposeInternal`), `helm.sh/resource-policy: keep` on volumes
  (Retain policy), removal of Red Hat PaaS labels, a config hash on pod templates (pods restart when their
  ConfigMaps/Secrets change);
- the helmfile hooks ported to Go (`internal/stack/objects.go`): `redis-config`, `redis-secret`, `shared-config`,
  `shared-secret`, `unifai-rag-secrets`, `multiagent-be-secret`, `identity-config`, `identity-secret`,
  `gcp-vertex-credentials`, and the service ConfigMaps read by the UI (`unifai-rag-config`, `multiagent-config`,
  `backend-config`, `identity-svc-config`). The four "dummy" ConfigMap charts are not installed any more;
- `unifai-generated` Secret: `SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY` (Fernet), `OAUTH_STATE_SECRET`,
  `REDIS_PASSWORD`, Keycloak client/admin/DB passwords. Generated once, never regenerated; `spec.secretsRef`
  overrides any key;
- the UI Route is re-encrypted with an OpenShift service-ca certificate mounted in nginx (instead of the passthrough
  of the self-signed certificate baked in the image), and every TLS-terminating Route deletes the
  `X-Authenticated-User` request header: MAS and RAG trust it as the caller identity when no session cookie is sent;
- `unifai-stack` NetworkPolicy: ingress only from the namespace, the OpenShift router, monitoring, the operator's
  namespace and `openshift-operators`; `unifai-internal-apis`: MAS, RAG, identity and backend only from the UnifAI
  pods, the pods labelled `unifai.startx.fr/internal-client=true` and those namespaces, so models, MCP servers or
  tools deployed in the namespace cannot call them (they also require the internal secret with an identity header).
  `spec.exposure.networkPolicy: false` removes both and sets the `NetworkIsolated` condition to False.

RAG: the upstream `unifai-rag` image has neither docling nor sentence-transformers, so conversion and embeddings are
always remote services. By default (`rag.docling.mode` / `rag.embedding.mode` = `deploy`, `local` is a synonym) the
stack runs docling-serve (CPU, `quay.io/docling-project/docling-serve-cpu:v1.37.0`, Service `docling-serve`) and
Hugging Face Text Embeddings Inference (CPU, `unifai-embedding`, model `sentence-transformers/all-MiniLM-L6-v2`,
dimension 384); `remote` uses `url`. rag-celery needs no GPU unless `rag.gpu: true`.

Phases: shared resources (MongoDB, Qdrant, RabbitMQ, Redis, Redis Insight, Temporal, logging volume), then the
applications once the shared resources are ready, then the UI once the application Services exist.
`status.components[]` shows each release, `status.endpoints` the URLs.

Identity, exactly one of:
- `identity.external`: existing Keycloak realm (`url`, `realm`, `clientId`, `clientSecret` Secret selector);
- `identity.keycloak`: Keycloak deployed in the namespace. RHBK only supports OwnNamespace/SingleNamespace installs,
  so the operator creates an OperatorGroup (if the namespace has none) and a `rhbk-operator` Subscription, a database
  (Crunchy `PostgresCluster` when that API is served, else a PostgreSQL StatefulSet), the `Keycloak` CR, an edge
  Route, and a `KeycloakRealmImport` (realm `unifai`, confidential client `unifai`, one user per
  `identity.adminUsers`, secrets passed as placeholders). The realm is imported once: later host changes must be
  applied in Keycloak.

A managed Keycloak whose pod stays running but unready for 10 minutes (typically after a cluster restart: stale
Infinispan member, "cluster health check" DOWN) is restarted by the operator, at most once every 15 minutes
(annotation `unifai.startx.fr/last-repair` on the Keycloak CR).

`identity.forwardUserToken: true` (default false) gives the multiagent pods (be and temporal worker) the identity
service's Keycloak client (`IDENTITY_FORWARDING_ENABLED`, `KEYCLOAK_BASE_URL`, `KEYCLOAK_REALM`, `CLIENT_ID`, and
`CLIENT_SECRET` through `multiagent-be-secret`), so workflow elements that opt in (`forward_user_token`) can send the
acting user's OIDC token to model and tool gateways. It needs a multiagent image with identity forwarding (fork
commit 4467138fe).

Internal authentication: the services honour `X-Authenticated-User` from callers that also send the shared
`INTERNAL_AUTH_SECRET` in `X-Internal-Auth` (fork access-control fixes; older images ignore both). The operator
generates it once in `unifai-generated` (override: key `INTERNAL_AUTH_SECRET` of `spec.secretsRef`), copies the
effective value to the Secret `unifai-internal-auth`, injects it (secretKeyRef) into identity, multiagent (server and
worker), RAG (server and Celery) and backend, sends it from its own UnifAI client, and every Route deletes both
headers from incoming requests. Service-to-service identity calls go to the identity Service (`http://identity:13456`: `IDENTITY_HOST` of RAG
and backend, `DIRECTORY_SSO_URL` of multiagent, whose `IDENTITY_HOST` stays public for its OAuth callback), since the
public Route strips `X-Internal-Auth`.

`extraEnv` adds variables to a component's containers (keys `multiagent`, `multiagentWorker`, `rag`, `ragCelery`,
`backend`, `identity`, `ui`; full `EnvVar`, so `valueFrom` works); a chart variable with the same name is replaced:
```yaml
spec:
  extraEnv:
    identity:
      - {name: DIRECTORY_PROVIDER, value: oidc-claims}
      - {name: DIRECTORY_OIDC_ISSUER, value: https://keycloak.example.com/realms/unifai}
```

`openTelemetry` exports traces and metrics (OTLP) of the multiagent server and Temporal worker, the RAG server and
Celery worker and the backend, through the global_utils telemetry bootstrap (fork commit c918f732b, images built from
it): `UNIFAI_OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`/`_PROTOCOL`, `OTEL_SERVICE_NAME` (the Helm release name,
e.g. `unifai-multiagent-be`), `OTEL_TRACES_SAMPLER`/`_ARG`, `OTEL_METRICS_EXPORTER=none` with `disableMetrics`, and
`OTEL_RESOURCE_ATTRIBUTES` (`k8s.namespace.name` plus `resourceAttributes`). Only those five releases are upgraded
when it changes.
```yaml
spec:
  openTelemetry:
    endpoint: http://zuno-otel-collector-collector.zuno-monitoring.svc:4318
    protocol: http/protobuf
    sampler: parentbased_traceidratio
    samplerArg: "0.2"
```

Deletion: releases are uninstalled in reverse order, Keycloak objects and the RHBK subscription removed.
`deletionPolicy: Retain` (default) keeps PVCs, `unifai-generated` and the Keycloak database, so recreating the stack
finds its data and encryption key; `Delete` removes them. `paused: true` stops reconciling.

### Object kinds

Same conventions as the first (Python) version: `spec.type` + `spec.config` (UnifAI `cfg_dict`), `spec.secretRefs`
(Secret value injected at a dotted path), `spec.owner` (default `admin`), `spec.teamId`, `spec.unifaiName`.
`$ref:<kind>/<name>` resolves to `$ref:<rid>`, `$rid:<kind>/<name>` to `<rid>`; node entries of a workflow without
config are expanded from the library. Specs are dry-run validated (`config.validate`); invalid ones go to phase
`Error` until the spec changes. An object that already exists in UnifAI is only taken over with the annotation
`unifai.startx.fr/adopt: "true"`. While the namespace's `UnifaiStack` is not Ready, objects wait (namespaces
without a stack, e.g. deployed by helmfile, are not gated). The operator calls
`unifai-multiagent-be.<ns>.svc:8003`, `unifai-rag-server.<ns>.svc:13456` and `identity.<ns>.svc:13456`.

`UnifaiTeam` is an identity team (`members`: `{type: user|group, id, displayName}`; a group is an OIDC group of the
users' tokens, a leading `/` is removed). Team names are global in identity: a team of the same name created by
another user is never taken over, one created by the owner only with the adopt annotation; `status.teamId` holds its
id. Any object can live in its workspace with `spec.teamRef: <UnifaiTeam name>` (exclusive with `teamId`): it waits
until the team is Ready and never falls back to the owner's personal workspace. The team is deleted from identity
only when no object of the namespace references it any more (it stays `Deleting` with the list of its users).
```yaml
apiVersion: unifai.startx.fr/v1alpha1
kind: UnifaiTeam
metadata: {name: tekos}
spec:
  members: [{type: group, id: agent_tekos}]
---
apiVersion: unifai.startx.fr/v1alpha1
kind: UnifaiLLM
metadata: {name: tekos-llm}
spec: {teamRef: tekos, type: openai_compatible, config: {model_name: m, base_url: "http://llm:8000/v1"}}
```

### Zuno OKF agent bundles (fork-only)

`UnifaiAgentBundle` (`internal/okf`, [`examples/agent/agentbundle-tekos.yaml`](examples/agent/agentbundle-tekos.yaml))
maps one signed Zuno OKF agent bundle onto the object kinds above (zuno-demo ADR-0564). It is Zuno-specific and never
proposed upstream. The pipeline runs in a fixed order and a failed step emits nothing, leaving what a previous good
version emitted:

1. **Pull** `spec.source.oci.reference`, pinned by digest (tags are refused at admission); optional
   `pullSecretRef` (dockerconfigjson). Layout: artifact type `application/vnd.zuno.okf.bundle.v1`, one
   `application/vnd.zuno.okf.bundle.v1.tar+gzip` layer holding the `agents/<name>/` tree, and the
   `cosign sign-blob` signature of the bundle digest in the manifest annotation `zuno.okf.signature`.
2. **Verified**: the digest is recomputed exactly as zuno-demo's `sign_okf_bundle.py` does and the ECDSA signature
   is checked against the PEM key in `spec.verify.publicKeyRef`, before any file is parsed.
3. **Valid**: every OKF document's frontmatter is validated against the schemas embedded in `internal/okf/schema/`
   (copies of zuno-demo `platform/okf/schema/`, OKF v0.2). The bundle must declare a graph shape that has a
   blueprint template (only `retrieve_reason_respond` today). A bundle declaring `zuno.access.groups` is refused
   (`EntitlementUnsupported`) unless `spec.entitlement: GatewayOnly`, since UnifAI cannot gate visibility by group.
4. **WithinCeilings**: the tools and knowledge domains the tasks declare must be in `spec.ceilings`, and the
   classification must not be below `ceilings.minClassification`.
5. **Emitted** (owned, labelled `unifai.startx.fr/agent-bundle`): `<bundle>-direct` condition; per task
   `<bundle>-<task>` LLM (the `spec.llm` template plus `X-Zuno-Agent`, `X-Zuno-Task`,
   `X-Zuno-Data-Classification` and `X-Zuno-Run-Id: {session_id}` in `default_headers`) and agent (system prompt
   from `prompts/<task>.md`, providers and retriever when the task declares tools or knowledge), and a linear
   workflow, named `<bundle>` for the primary task. `classificationOverrides` may only raise a task's level.
   Objects of a task removed from the bundle are deleted.

Not mapped (listed in `status.unmapped`): per-task tool allow-lists (enforced by mcp-gateway), `rag.top_k`, UI
fields and prompt examples.

### RAG sources and search settings

`UnifaiStack.spec.rag` also carries:

- `hybrid: true`: dense + BM25 search with rank fusion, in new `<collection>_hybrid` collections (sources are
  re-ingested; existing collections are untouched).
- `sharedPublishers`: users allowed to publish shared sources, visible to members of the source's OIDC groups;
  the RAG service then verifies tokens forwarded by multiagent against the stack's OIDC issuer. Empty = every
  source stays private to its uploader.
- `confluence`: the credentials of the Confluence source type (Secret refs, added to `unifai-rag-secrets`).

Every one of these renders only when set: a stack that does not use them keeps byte-identical RAG releases.

`UnifaiRAGSource` ([`examples/rag/ragsource-confluence.yaml`](examples/rag/ragsource-confluence.yaml)) registers a
Confluence space or page subtree with the RAG service as its `owner`, triggers a sync when the spec changes and
every `syncInterval` (minimum 10m; unset = on spec change only), and reports `sourceId`, the pipeline status and
the page counts of the last sync. The RAG service syncs incrementally (unchanged pages are not re-embedded).
Deleting the resource deletes the source and its vectors. A shared source needs `aclGroups` (admission rule) and
an owner listed in `sharedPublishers` (otherwise phase `Error`, `ACCESS_DENIED`).

### Backups (spec.backup)

`spec.backup` renders two CronJobs (default schedule `0 2 * * *`, `concurrencyPolicy: Forbid`) that write to an
S3-compatible bucket, under `<prefix>` (default `unifai/<namespace>`):

- `unifai-backup-mongodb`: `mongodump --archive --gzip` of `mongodb:27017`, uploaded as
  `<prefix>/mongodb/<UTC timestamp>.archive.gz`;
- `unifai-backup-qdrant`: one snapshot per collection, uploaded as `<prefix>/qdrant/<UTC timestamp>/<collection>.snapshot`,
  then deleted from Qdrant.

Each job keeps the `retention` newest backups (default 7) and deletes older ones. The credentials Secret
(`s3.credentialsSecret`) holds `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`; `s3.endpoint` targets a non-AWS
service. Removing `spec.backup` deletes the CronJobs, never the backups.

Each MongoDB backup also writes `<prefix>/mongodb/<UTC timestamp>.meta.json` with the fingerprint of the stack's
`CREDENTIAL_ENCRYPTION_KEY` (`status.credentialKeyFingerprint`): the credentials stored in MongoDB are encrypted with it.

#### Restore (UnifaiRestore)

```yaml
apiVersion: unifai.startx.fr/v1alpha1
kind: UnifaiRestore
metadata: {name: restore-20261023, namespace: <stack namespace>}
spec:
  backup: latest            # or 20261023T020000Z: each store's newest backup at or before that time
  stores: [mongodb, qdrant] # default both
  collections: [docs]       # Qdrant collections (default: all of the backup)
  # source: {bucket, prefix, endpoint, credentialsSecret}  # another stack's backups (default: spec.backup.s3)
```

The restore is immutable and runs once (`Pending`, `Stopping`, `Restoring`, `Starting`, `Completed` or `Failed`):

1. the operator annotates the stack `unifai.startx.fr/quiesced-by=<restore>`: the UnifAI applications (UI, MAS and its
   worker, RAG server and workers, backend, identity) are scaled to 0, without HPA; the data stores keep running;
2. the Job `unifai-restore-<name>` picks the backups, checks the MongoDB key fingerprint (refused when it differs,
   unless `spec.allowKeyMismatch`: the stored credentials would then have to be entered again), restores the Qdrant
   collections from their snapshots, then MongoDB (`mongorestore --drop`, the dumped databases are replaced);
3. the annotation is removed and the applications restart; `status.restored` lists `<store>/<timestamp>`.

A failed restore restarts the applications too (the Job runs once: look at its pod before retrying with a new
UnifaiRestore). One restore at a time per namespace; deleting an active one gives the applications back. UnifAI
objects created after the backup are recreated by their custom resources at the next reconcile.

### Taking over a helmfile deployment

A `UnifaiStack` created in a namespace deployed by the upstream helmfile adopts it in place (done for `unifai-devel`,
see [`examples/stack/stack-unifai-devel.yaml`](examples/stack/stack-unifai-devel.yaml)):

1. Put the OIDC client secret in a Secret (`identity-secret` holds it as `client_secret`) and reference it in
   `identity.external.clientSecret`.
2. Create the stack. The operator then:
   - seeds `unifai-generated` from the existing `multiagent-be-secret` / `shared-secret` (same
     `CREDENTIAL_ENCRYPTION_KEY`, so the credentials stored in MongoDB stay readable);
   - keeps every existing PVC and StatefulSet claim template as is (size, class, metadata: immutable);
   - uninstalls the helmfile "dummy" releases (`unifai-redis-config`, `unifai-shared-config`, `unifai-rag-config`,
     `multiagent-config`) after marking the ConfigMaps it manages `helm.sh/resource-policy: keep`;
   - upgrades the other releases in place (a release left `failed` at its first revision is reinstalled).
3. Expect one restart of every pod (labels, config hash, dev requests) and the removal of the internal Routes and HPAs.

Other behaviours worth knowing: Deployments mounting a ReadWriteOnce volume (qdrant, temporal, redis-insight, docling)
use the `Recreate` strategy; the dev profile disables chart autoscaling (fixed `replicas`); readiness follows
`kubectl rollout status` (no pod of an older revision left). An `UnifaiRAGPipeline` in phase `Failed` is retried when
its spec changes or when the `unifai.startx.fr/retry` annotation gets a new value.

### Events and metrics
Every phase change of an UnifAI object or an UnifaiStack is recorded as an Event (`events.k8s.io`, reporting
controller `unifai-operator`, reason = the new phase; `Warning` for `Error` and `Failed`, plus `DeleteFailed` when the
UnifAI side of an object cannot be removed): `oc get events -n <ns> --field-selector reportingComponent=unifai-operator`.
The manager metrics endpoint (`:8443/metrics`, HTTPS, token reviewed) adds to the controller-runtime metrics:

| Metric | Labels | Meaning |
|---|---|---|
| `unifai_operator_phase_transitions_total` | kind, phase | phase changes |
| `unifai_operator_stack_ready` | namespace | 1 when the stack is Ready |
| `unifai_operator_helm_apply_seconds` | release, result | Helm install/upgrade duration |
| `unifai_operator_keycloak_repairs_total` | namespace | restarts of a managed Keycloak left unready |

The bundle ships a ServiceMonitor for these metrics (see "Install with OLM"). In Prometheus the `namespace` label is the
operator's (target) namespace: the stack namespace of `unifai_operator_stack_ready` and
`unifai_operator_keycloak_repairs_total` is `exported_namespace`.

## Build and release

Requirements: Go 1.26, operator-sdk 1.41, opm, podman, write access to `quay.io/zuno/unifai-operator{,-bundle,-catalog}`.

```bash
make test        # unit tests (chart rendering, OKF) + envtest (controllers against a fake UnifAI API, CEL rules)
make release     # VERSION=x.y.z: test, image, canary e2e, bundle, catalog on `alpha`
make promote     # catalog on `stable` = production (demo333 subscribes to stable)
```

`make release` runs, in order: `test`, `docker-build-local docker-push`, `canary-deploy` (the candidate image as a
second operator instance, namespace `unifai-operator-canary`, after applying its CRDs), `canary-e2e`, `canary-delete`,
`bundle bundle-build bundle-push`, then `catalog-add CHANNELS=alpha catalog-build catalog-push`. Production is not
touched before `make promote`.

Release through GitHub (no quay credentials on the workstation for the bundle and the catalog):

```bash
make test docker-build-local docker-push canary-deploy canary-e2e canary-delete   # VERSION=x.y.z, on the cluster
make release-files                                     # bundle + catalog template on alpha and stable
git commit ... && git tag operator-vx.y.z && git push origin devel operator-vx.y.z
```

The tag runs `.github/workflows/unifai-operator-release.yml` in the `quay-release` environment (approval required,
quay robot `QUAY_USERNAME`/`QUAY_TOKEN`): it checks that the tag matches `VERSION`, the committed bundle and the
catalog template, that the operator image tested by the canary exists (it is not rebuilt), then pushes the bundle and
the catalog (rendered there: rendering reads the bundle from the registry). Clusters subscribed to `stable` upgrade at
the next catalog poll. Afterwards, `make catalog` refreshes the committed `catalog/` (commit it with the next change).

Operator instances: `OPERATOR_INSTANCE` names an instance ("" = the OLM one). An UnifAI resource labelled
`unifai.startx.fr/operator-instance=<name>` is cached and reconciled only by that instance; unlabelled resources only
by the default one. Relabelling hands a stack over (that is how the upgrade test works). An instance must not be
removed while objects labelled for it are being deleted (their finalizers would stay): the e2e waits for its
namespaces to be gone before returning.

e2e (`make test-e2e`, or `canary-e2e` against the canary) on the current cluster, throwaway namespaces
`unifai-e2e-*`: stack Ready + invariants (singleton, routes, NetworkPolicy, secrets, Recreate on RWO volumes,
replicas), the internal auth header refused through the UI route and without the secret, the APIs unreachable
from a pod without the internal-client label, LLM/agent/workflow/chat, no needless Helm upgrade,
Delete-policy cleanup; `E2E_UPGRADE=1` (canary only): a stack deployed by the OLM instance is handed to the candidate
(same encryption key, same UnifAI objects, chat); `E2E_KEYCLOAK=1`: managed Keycloak (RHBK install, realm import,
removal); `E2E_FULL=1`: docling + TEI deployed; `E2E_KEEP=1` keeps the namespaces. Cluster-specific defaults
(`E2E_STORAGE_CLASS=gp3-csi`, `E2E_SHARED_STORAGE_CLASS=nfs`, `E2E_NODE_SELECTOR=workload=unifai`) are in the Makefile.

`make charts` refreshes `internal/stack/assets` from `../../helm`. `make docker-build` compiles inside the image
(needs several GB on the container storage); `docker-build-local` (used by `release`) compiles on the host.

## Install with OLM (OpenShift)

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata: {name: unifai-operator-catalog, namespace: openshift-marketplace}
spec:
  sourceType: grpc
  image: quay.io/zuno/unifai-operator-catalog:latest
  displayName: UnifAI Operator (startx)
  publisher: startx
  updateStrategy: {registryPoll: {interval: 15m}}
---
apiVersion: v1
kind: Namespace
metadata: {name: unifai-operator}
---
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata: {name: unifai-operator, namespace: unifai-operator}
spec: {}  # AllNamespaces
---
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata: {name: unifai-operator, namespace: unifai-operator}
spec:
  channel: stable
  name: unifai-operator
  source: unifai-operator-catalog
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
```

The operator gets its own namespace (suggested `unifai-operator`) rather than `openshift-operators`: OpenShift
monitoring ignores `openshift-*` namespaces, and the bundle ships a ServiceMonitor scraped by the user-workload
monitoring. It authenticates with the token of the `unifai-operator-metrics-scraper` ServiceAccount (created by OLM
from the CSV `clusterPermissions`, allowed to GET `/metrics`), stored in the Secret `unifai-operator-metrics-token`
that the operator creates. Moving an existing install: delete the Subscription and the CSV in the old namespace (CRDs
and UnifAI resources are kept, stacks keep running), then create the three objects above.

Files: [`deploy/olm/`](deploy/olm/). To pick up a new catalog image without waiting for the 15 min poll:
`oc -n openshift-marketplace delete pod -l olm.catalogSource=unifai-operator-catalog`. Then, in any namespace:

```yaml
apiVersion: unifai.startx.fr/v1alpha1
kind: UnifaiStack
metadata: {name: unifai}
spec:
  profile: dev
  identity: {keycloak: {}}
  storage: {className: gp3-csi, sharedClassName: nfs}
```

## Layout

`api/v1alpha1` types · `internal/unifai` REST client · `internal/controller` reconcilers · `internal/stack` charts,
values, post-renderer, Keycloak · `config/` kustomize (CRDs, RBAC, manager, CSV base, samples) · `bundle/` OLM
bundle (generated) · `catalog-template.yaml` → `catalog/` FBC · `examples/`.

## Implementation notes (learned on demo333)

- Objects are read with the uncached API reader and their status is merge-patched: a stale informer copy right after
  a write made the operator refuse its own UnifAI objects or create duplicates.
- The Helm inputs hash is a label of the Helm release (`unifai.startx.fr/hash`), not only in the CR status.
- Keycloak on Crunchy PostgreSQL 16 needs a per-user schema (`autoCreateUserSchema` annotation + `db.schema`).
- The host umask (0077) makes build contexts unreadable for non-root images: the Makefile runs `chmod -R a+rX`
  before the image, bundle and catalog builds.
- Build with `docker-build-local` when `/home` is short on space (the in-image Go build needs several GB).
