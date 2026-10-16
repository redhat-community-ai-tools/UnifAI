# MEMORY — fork startxfr/UnifAI (branch `devel` only)

Project memory for resuming work on this fork. Fork-only: never versioned outside `devel` (see `fork/fork-only-paths`).
No secrets here.

## Goal
Deploy UnifAI autonomously on our OpenShift cluster, evolve it, and contribute selected changes upstream
(`redhat-community-ai-tools/UnifAI`, trunk `main`).

## Branch model
- `main` = strict mirror of `upstream/main` (`git merge --ff-only`), no own commits. Never merge `devel` into `main`.
- `devel` = `main` + fork delta (Makefile, `fork/`, `MEMORY.md`, fork-only patches). Receives `main` by merge. Build/deploy/release branch.
- Features/fixes: branch from `main` (`make feature-start`), merge into `devel` to test (`make feature-to-devel`), PR upstream if wanted.
- Releases are tagged on `devel` (what is deployed = what is tagged).

## Guard rails
- Pushes to `origin` and `upstream` are disabled (`remote.*.pushurl=DISABLED`); nothing is pushed unless explicitly decided
  (`git config --unset remote.origin.pushurl`). User rule: commit locally as much as needed, no push.
- Fork-only paths (`fork/fork-only-paths`): `Makefile`, `fork.mk`, `fork.mk.example`, `MEMORY.md`, `fork/`, `.fork/`.
  A `.gitignore` cannot keep tracked files out of a merge, so `fork/hooks/guard-fork-only` (installed by `make init` as
  pre-commit and pre-merge-commit) refuses them on any branch but `devel`; `make contrib-check` also rejects them.

## What exists
- `fork/render_values.py` + `fork/values/*.yaml` + `fork/images.yaml`: `make overlay` copies `helm/` to `.fork/helm/` and deep-merges
  overlays over `helm/values/*` (image repos/tags -> quay.io, URLs, storage classes, public shared images). Chosen over
  `--state-values-file` because `global-config.yaml` is a release-level values file. Cluster-specific placeholders come from `fork.mk`.
- Branch `fix/multiagent-optional-corp-ca` (merged in `devel`): `--build-arg CERT_URL=` skips the Red Hat CA download. Candidate for a first upstream PR.
- Image names: `$(REGISTRY)/unifai-{rag,multiagent,backend,identity,ui}`; identity's helm values key is `backend`. UI image needs
  `ui/UnifAI-secrets/certificates/unifai.{crt,key}` (`make ui-certs`).

## Known gaps / not validated
- helmfile 1.8.1 + helm-diff installed in `~/.local/bin`; `helmfile template` passes on the 6 rendered modules (no AWS/Red Hat leftovers), `deploy-diff`/`deploy` not yet run on a cluster. Images built and pushed to `quay.io/zuno/unifai-*:devel` (+`devel-<sha>`). Public images for mongo/qdrant/rabbitmq (`bitnamilegacy/rabbitmq`) to confirm at runtime.
- Upstream values quirks handled in overlays: mongodb/qdrant read `storage.className` (not `storageClassName`); rabbitmq uses `global.storageClass`; rag/multiagent shared-storage need a nested `storage.storage.className`.
- Remaining Red Hat dependencies: docling and embedding service URLs (set `DOCLING_URL`/`EMBEDDING_URL`, or `USE_REMOTE_*=False`), `paas.redhat.com/appcode` annotations.
- Upstream chart defects found by `make helm-lint`: `helm/multiagent/be` (template without extension), `helm/shared-resources/rabbitmq` (missing `common` dependency).
- Upstream has no CONTRIBUTING; PRs come from in-repo branches; review gate = CodeRabbit + Cursor pipeline (arch APPROVE, score >= 8/10) needing secrets forks do not get.

## Open TODO (manual)
1. Create quay.io repos `unifai-*`; `cp fork.mk.example fork.mk` and fill it; install helmfile (+helm-diff), gh, ruff, gitleaks.
2. Contact upstream maintainers (CODEOWNERS) before the first PR.
3. Validate `make deploy-diff` then deploy on a test namespace; decide TLS (nginx certs vs OpenShift Route).

## Key commands
`make help`, `make init`, `make status`, `make sync-all`, `make overlay`, `make helm-lint`, `make images-devel`, `make contrib-check`.

## Clusters (all deployments are in namespace `unifai-devel`)
- **demo333** (api.demo333.startx.fr, apps.demo333.startx.fr) — current, working (validated by the user 2026-10-15). Shared with the zuno demo, nodes at ~98% CPU requests.
  - Added MachineSet `unifai-worker-a` (2x m5a.4xlarge, label `workload=unifai`; ~0.8 $/h each, scale to 0 when unused). Existing worker MachineSets are t3a.large (too small).
  - RWX: `nfs-provisioner-operator` (community-operators) in ns `nfs-provisioner`, StorageClass `nfs`, 300G gp3 backing. ODF was rejected (needs 3 big storage nodes).
  - Keycloak (RHBK in ns `zuno-auth`, https://keycloak.apps.demo333.startx.fr) is managed by ArgoCD for zuno: do not touch realm `zuno`. Realm `unifai` was created with a `KeycloakRealmImport` (client `unifai`, user `admin`; `admin_allowed_users=["admin"]`). A KeycloakRealmImport is not re-applied once the realm exists: later changes go through the admin REST API (token from the `keycloak-admin` secret in `zuno-auth`; renaming a user needs `editUsernameAllowed=true` temporarily). Client secret and passwords: `.fork/secrets.env` only.
  - `fork.mk` (local): hosts `unifai-{ui,identity}-unifai-devel.apps.demo333.startx.fr`, STORAGE_CLASS=gp3-csi, SHARED_STORAGE_CLASS=nfs, docling/embedding URLs still dummy.
  - Up: shared resources, rag-server, backend (`slack-socket` sidecar fails: no Slack tokens), multiagent be + temporal-worker, identity, ui. `rag-celery` Pending: chart requests `nvidia.com/gpu: 1`, GPU nodes had no allocatable GPU (user chose to keep the GPU request).
- **amine420** (api.amine420.startx.fr): first test cluster (no GPU, no Keycloak). Shared + rag-server + backend + multiagent were deployed there; identity/ui were not. NFS provisioner installed there too. Still holds a partial deployment.

## Operations notes / gotchas
- Always `set -a; source <(sed 's/ *= */=/' fork.mk); set +a; source .fork/secrets.env` before `make deploy*` or `helmfile`: the presync/postsync hooks read lowercase env vars with `set -u` (redis_*, umami_*, vault_*, langfuse_*, slack_*, keycloak_*/client_*, CREDENTIAL_ENCRYPTION_KEY, OAUTH_STATE_SECRET...). `admin_allowed_users` must be a JSON list.
- `make deploy` stops at the first failing module (rag-celery `wait: true`): apply modules individually from `.fork/helm` (`helmfile -n unifai-devel -f <module>.yaml.gotmpl apply`). `make overlay` deletes and recreates `.fork/helm`: never keep a shell cwd inside it while re-rendering.
- `rag-config` `needs` rag-celery, so while celery is Pending its postsync never runs: run `bash scripts/rag-postsync.sh` by hand (creates `unifai-rag-config`, required by the UI nginx: "no host in upstream" otherwise). Hooks of unchanged releases are skipped: run `shared-resources-postsync.sh` / `identity-presync.sh` by hand after changing env values, then restart the pods.
- umask 0077 on the build host makes `COPY` produce unreadable files for the non-root image user: `make build-ui` and `make build-multi-agent` run `chmod -R a+rX` first. Image tags `:devel` are mutable and nodes cache them: deploy a `devel-<sha>` tag (`DEPLOY_TAG=devel-<sha> make overlay`) or restart after clearing the cache.
- Pull of `registry.access.redhat.com/rhel9/redis-7` needs a Red Hat login: the overlay uses `quay.io/fedora/redis-7`. A Pending StatefulSet pod stuck on a bad image must be deleted by hand after fixing the image.
- Rolling updates can deadlock when nodes are full (identity needs 4 CPU): delete the old pod. Upstream requests are large (total ~25.6 CPU / 60 GiB); a dev-sized requests overlay is a possible follow-up.
- quay.io: images are public under `quay.io/zuno/unifai-*` (`:devel`, `:devel-<sha>`); push needs a login with write access to `zuno` (a robot of another org gets "authentication required").
- Security: charts create public Routes for mongodb, qdrant, redis-insight, temporal, backend, multiagent-be (no auth on qdrant/redis-insight/temporal): review or remove. The `admin` password is weak (user's choice): change it before wider exposure.

## Open TODO
1. GPU for rag-celery (or drop the request), docling + embedding services for RAG ingestion, Slack tokens for the backend sidecar.
2. Dev-sized resource requests overlay; remove public routes; scale `unifai-worker-a` down when idle.
3. Contact upstream maintainers before the first PR (candidate: `fix/multiagent-optional-corp-ca`).

## UnifAI operator (`fork/unifai-operator/`, Go, since 2026-10-16)
- operator-sdk/controller-runtime operator, group `unifai.startx.fr/v1alpha1`: `UnifaiStack` (one per namespace, name `unifai`, CEL) + 12 object kinds. Replaced the first kopf prototype (removed). Details: `fork/unifai-operator/README.md`.
- Images `quay.io/zuno/unifai-operator{,-bundle,-catalog}` (public; push needs `podman login quay.io -u zuno+zuno_demo`, the `~/.docker/config.json` fallback is the `startx+alcor` robot without zuno rights). Release: bump `VERSION` in its Makefile, `make docker-build-local docker-push bundle bundle-build bundle-push catalog-add catalog-build catalog-push` (use `set -o pipefail`; run `make test` first). Channels: `alpha` and `stable` = 0.1.12 (releases now go to both with `CHANNELS=alpha,stable`).
- demo333: CatalogSource `unifai-operator-catalog` (openshift-marketplace) + Subscription `unifai-operator` (openshift-operators, alpha, Automatic). Upgrades 0.1.0 -> 0.1.12 went through OLM.
- Test stack `unifai-olm` (dev profile, managed Keycloak: RHBK installed in the namespace, Crunchy PostgresCluster `unifai-keycloak-db`, https://unifai-ui-unifai-olm.apps.demo333.startx.fr, admin password in secret `unifai-generated` key `keycloak-admin-password`). Validated: all components Ready, examples Ready, chat smoke, RAG ingestion (docling-serve CPU + TEI) and retrieval, Retain delete/recreate (same encryption key, no duplicates).
- `unifai-devel` is now managed by `UnifaiStack/unifai` (profile dev, external Keycloak zuno-auth realm `unifai`, client secret in Secret `unifai-oidc`; `fork/unifai-operator/examples/stack/stack-unifai-devel.yaml`), adopted from helmfile on 2026-10-16: same encryption key, volumes and data kept, CPU requests 27.6 -> 1.4, only ui/identity Routes left, rag-celery runs (no GPU) with docling-serve + TEI. Do NOT run `make deploy`/helmfile on it any more. The kopf prototype resources were deleted.
- Gotchas: upstream rag image has no docling/sentence-transformers (both always remote); docling chart Service is `docling-serve`; a multiagent-be pod started before the `admin` rename kept `admin_allowed_users=["unifai-admin"]` (random 403): restart pods after changing shared-config; nodes `workload=unifai` were full because the helmfile HPA scaled multiagent-be to 6 (fixed by the dev profile).
- `/home` was full: build images with `docker-build-local`, Go cache in `/var/tmp/cl-gocache`.
