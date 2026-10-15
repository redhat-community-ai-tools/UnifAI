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
- `unifai-stack` NetworkPolicy: ingress only from the namespace, the OpenShift router, monitoring and
  `openshift-operators` (the internal APIs trust an `X-Authenticated-User` header).

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
`unifai-multiagent-be.<ns>.svc:8003` and `unifai-rag-server.<ns>.svc:13456`.

## Build and release

Requirements: Go 1.26, operator-sdk 1.41, opm, podman, write access to `quay.io/zuno/unifai-operator{,-bundle,-catalog}`.

```bash
make test                       # unit tests (chart rendering) + envtest (controllers against a fake UnifAI API, CEL rules)
make charts                     # refresh internal/stack/assets from ../../helm
make docker-build-local docker-push   # VERSION=0.1.0 UNIFAI_VERSION=devel (Dockerfile.local; `make docker-build` compiles in the image)
make bundle bundle-build bundle-push
make catalog-add                # record VERSION in catalog-template.yaml (CHANNELS=alpha,stable; replaces the channel head)
make catalog-build catalog-push # quay.io/zuno/unifai-operator-catalog:latest
```

A new release: bump `VERSION`, run the steps above (`catalog-add` with `CHANNELS=alpha` for a devel build, then again
with `CHANNELS=stable` to promote it). The catalog image tag is `latest` and the CatalogSource polls it.

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
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata: {name: unifai-operator, namespace: openshift-operators}
spec:
  channel: alpha
  name: unifai-operator
  source: unifai-operator-catalog
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
```

Files: [`deploy/olm/`](deploy/olm/). Then, in any namespace:

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
bundle (generated) · `catalog-template.yaml` → `catalog/` FBC · `examples/` · `legacy-kopf/` first Python version
(to remove once the Go operator is validated on a cluster).
