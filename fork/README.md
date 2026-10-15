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
