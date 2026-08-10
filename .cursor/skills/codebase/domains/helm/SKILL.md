---
name: helm-knowledge
description: >-
  Domain knowledge for UnifAI Helm charts and helmfile releases. Chart layout,
  values conventions, and cross-helmfile deploy contracts. Use when working on
  files under helm/.
paths: helm/**
---

# Helm Knowledge System

Deployment packaging for UnifAI: one helmfile per deployable module, charts under
`helm/`, environment values under `helm/values/`. Deploy orchestration lives in
`ci/pipeline-deploy.groovy` (not this domain) — this skill documents the chart
contracts that pipeline depends on.

Hexagonal / Python layer rules do **not** apply here. Review for correctness,
consistency with established Helm conventions, and blast radius across releases.

## Component Routing

Map path → module (kebab-case → `references/<name>.md` when present).

| Path prefix (under `helm/`) | Component |
|-----------------------------|-----------|
| `*.yaml.gotmpl` | Helmfiles |
| `values/` | Env values |
| `shared-resources/` | Shared infra |
| `backend/` | Backend |
| `rag/` | RAG |
| `multiagent/` | Multi-agent |
| `ui/` | UI |
| `scripts/` | Helm hooks |
| `unifai-tests/` | Tests |

Cross-cutting references live under `references/` and `recipes/` (load when the
change touches that concern — e.g. `references/shared-storage.md` for PVC contracts).

## Landmarks

| Landmark | Location |
|----------|----------|
| Shared infra helmfile | `helm/shared-resources.yaml.gotmpl` |
| Shared infra values | `helm/values/shared-resource-values.yaml` |
| Module helmfiles | `helm/backend.yaml.gotmpl`, `rag.yaml.gotmpl`, `multiagent.yaml.gotmpl`, `identity.yaml.gotmpl`, `ui.yaml.gotmpl` |
| Module chart trees | `helm/backend/`, `helm/rag/`, `helm/multiagent/`, `helm/ui/`, `helm/shared-resources/` |
| Deploy pipeline | `ci/pipeline-deploy.groovy` |

## Helmfile Map

| Helmfile | Owns |
|----------|------|
| `shared-resources.yaml.gotmpl` | Platform infra releases |
| `backend.yaml.gotmpl` | Backend releases |
| `rag.yaml.gotmpl` | RAG releases |
| `multiagent.yaml.gotmpl` | Multi-agent releases |
| `identity.yaml.gotmpl` | Identity release (chart packaged under `shared-resources/identity`) |
| `ui.yaml.gotmpl` | UI releases |

## Domain Rules

---

### 1. One Helmfile Per Deploy Module

Each deployable module has its own `*.yaml.gotmpl`. Do not merge unrelated modules
into a single helmfile. Cross-module ordering is enforced by the deploy pipeline,
not by helmfile `needs:` across files.

---

### 2. Platform Infra vs Module-Local Resources

- **Platform-wide resources** (consumed by multiple modules) belong in
  `shared-resources` and are referenced from each consumer chart’s values.
- **Module-local resources** live in the same helmfile as their consumers so one
  `helmfile apply` owns create + consume.

For volume/PVC naming and mount contracts, see `references/shared-storage.md`.

---

### 3. Values Live With the Release

Consumer charts read their own `values.yaml` and module `values/*-resource-values.yaml`.
They do **not** load `shared-resource-values.yaml`. Producer-side knobs are not
automatically visible inside other modules’ charts.

---

### Established Patterns — Helm

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| One helmfile per deploy module; no cross-file `needs:` between modules | `*.yaml.gotmpl` | Helmfile `needs:` cannot span files; deploy pipeline orders modules (e.g. `shared-resources` first on fresh install) |
| Platform resources created under `shared-resources`; app modules reference them from their own values | `shared-resources.yaml.gotmpl` + consumer chart values | Upgrades assume shared infra already exists; values are not cross-templated across helmfiles |
| Module-local supporting charts co-located with their consumers in the same helmfile | Module helmfiles (e.g. rag, multiagent) | Same apply owns create + consume |
| Hardcoded cross-chart resource names matching producer defaults (services, PVCs, configmaps, etc.) | Consumer `values.yaml` | Stable name is the contract when producer and consumer live in different value trees |
| Shared-volume mount wiring without lifecycle/retention in the same change | Consumer mounts on shared PVCs (including dynamic `subPathExpr` paths) | Storage create+mount may land before ops lifecycle (retention, rotation, shipping). Reviewers: Risks & Follow-ups / INFO — do not MAJOR solely for missing cleanup when that work is deferred |
