# Fork tooling

Fork-only files (never part of an upstream PR): `Makefile`, `fork.mk` (local, git-ignored), `fork.mk.example`, `fork/`.

- `make help` lists every target. `make init` sets up the `upstream` remote and **disables pushes** to `origin`/`upstream`
  (`git config --unset remote.origin.pushurl` when you want to publish).
- Branches: `main` mirrors `upstream/main` (ff-only); `devel` = `main` + fork delta; features start from `main`
  (`make feature-start`), are merged into `devel` to test (`make feature-to-devel`) and can then go upstream (`make contrib-*`).
- Deployment: `make overlay` copies `helm/` to `.fork/helm/` and deep-merges `fork/values/<file>.yaml` over `helm/values/<file>.yaml`
  (placeholders in braces are read from `fork.mk`); image repositories/tags come from `fork/images.yaml`. Upstream files stay untouched.
- Known gaps: `helmfile` is not validated here (not installed when written); `make helm-lint` reports upstream chart issues
  (`multiagent/be` template without extension, `rabbitmq` missing `common` dependency).

## Guard rails for main
`main` mirrors upstream, so fork-only paths (`fork/fork-only-paths`) must never reach it. `make init` installs
`fork/hooks/guard-fork-only` as pre-commit and pre-merge-commit hook: it refuses these paths on every branch except `devel`.

## Signed images (CI)

`.github/workflows/publish-images.yml` builds the five application images with the Makefile's Dockerfiles, pushes them to
`quay.io/zuno/unifai-<component>` and signs each digest keyless with the workflow's GitHub OIDC identity, with a SLSA provenance
(`fork/ci/slsa_provenance.py`) and an SPDX SBOM attached as attestations. zuno-demo verifies them before deploying
(zuno-demo ADR-0586, WP-176).

- A push to `devel` that touches an image's code publishes `devel-<sha>` and `devel` (environment `quay-devel`, no approval,
  restricted to the `devel` branch). A `vX.Y.Z` tag publishes `vX.Y.Z` (environment `quay-release`, with its approval).
- Both environments hold `QUAY_USERNAME` and `QUAY_TOKEN` of a quay robot with write access to `unifai-*`.
- The identity zuno accepts is the workflow path and ref: do not rename the workflow file or change its triggers without changing
  zuno-demo's `platform/supply-chain/image-identities.yaml`.
- `make images-devel` stays for local development and quick test images. Those images are **unsigned**: a cluster that verifies
  its UnifAI images refuses them, so pin only digests taken from a CI run's summary.
