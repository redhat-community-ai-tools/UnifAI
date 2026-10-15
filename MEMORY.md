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

## Deployment state (cluster api.amine420.startx.fr, namespace `unifai-devel`) — 2026-10-15
- RWX: `nfs-provisioner-operator` in ns `nfs-provisioner` (StorageClass `nfs`, 300G gp3 backing). ODF rejected (not enough nodes). `fork.mk`: STORAGE_CLASS=gp3-csi, SHARED_STORAGE_CLASS=nfs.
- Deployed: shared resources, rag-server, backend (slack-socket sidecar crash-loops: no Slack tokens), multiagent be + temporal-worker (image `devel-<sha>`; needs `make multiagent-perms`, umask 0077 issue).
- Not working: rag-celery (chart requests nvidia.com/gpu, no GPU; overlay change declined), identity + ui (identity needs an external Keycloak: keycloak_base_url, client_id/secret, realm).
- Helmfile hook variables live in `.fork/secrets.env` (git-excluded, generated): source it with fork.mk before `helmfile`/`make deploy`. `make deploy` stops at the first failing module (rag-celery wait), so apply modules individually.
- Security: charts expose public Routes for mongodb, qdrant, redis-insight, temporal, backend, multiagent-be: review/remove.

## Cluster demo333 (api.demo333.startx.fr, domain apps.demo333.startx.fr) — 2026-10-15
- Shared with the zuno demo (nodes at ~98% CPU requests). Added MachineSet `unifai-worker-a` (2x m5a.4xlarge, label workload=unifai) + NFS provisioner (ns `nfs-provisioner`, StorageClass `nfs`), namespace `unifai-devel`.
- Keycloak (RHBK, ns zuno-auth): realm import `unifai-realm` (realm `unifai`, client `unifai`, user `admin` (renamed from unifai-admin; admin_allowed_users=["admin"])); client_secret/admin password in `.fork/secrets.env` (git-excluded). identity connects ("Keycloak client setup successfully").
- fork.mk (local): hosts `unifai-{ui,identity}-unifai-devel.apps.demo333.startx.fr`, STORAGE_CLASS=gp3-csi, SHARED_STORAGE_CLASS=nfs.
- State: UI, identity, backend, multiagent, rag-server, shared resources up. rag-celery Pending (GPU kept: no allocatable GPU yet); because rag-config `needs` celery, run `scripts/rag-postsync.sh` by hand to create `unifai-rag-config` (UI needs it).
- Run helmfile from `.fork/helm` (recreated by `make overlay`: never keep a shell cwd inside it while re-rendering).
