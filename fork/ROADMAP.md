# ROADMAP — fork startxfr/UnifAI

Single backlog of the fork (fork-only, `devel`). Each item has an id `R-xxx`, a status (`todo`, `doing`, `done`,
`blocked`) and an owner (the Claude session or person working on it). Product work packages tracked elsewhere (WP-xxx)
are referenced, not duplicated. No secrets, no unpublished vulnerability details here: this repository is public.

## Working rules
- **Branches**: `main` mirrors upstream; features branch from `main` and merge into `devel` (`fork/README.md`).
  Fork-only paths (`fork/fork-only-paths`) are only committed on `devel`.
- **Ownership**: one owning session per area; announce before editing files of another area.
  | Area | Owner |
  |---|---|
  | Operator core, UnifaiStack, releases (`fork/unifai-operator`, except below) | operator session |
  | UnifaiAgentBundle, UnifaiRAGSource, `zuno-unifai` stack, app images | zuno-demo-68 |
  | v0.11 plan (WP-146..157) | zuno-demo-59 (coordination) |
- **Commits**: explicit pathspec only (the tree is shared); run `make generate manifests test` before committing
  operator changes; Conventional Commits (`feat(fork): ...`).
- **Operator releases**: only through `make release` (canary instance + e2e incl. upgrade) then `make promote`;
  one session cuts releases and folds in the other sessions' committed changes.
- **App images**: immutable tags `devel-<sha>` for pinned stacks; `:devel` moves only on purpose.
- **Push**: `devel` and upstream PRs only on the user's decision.
- **Routine (weekly)**: `make upstream-check`; if behind, `make sync-all`, then `make -C fork/unifai-operator charts`
  and an operator release when `helm/` changed.

## 1. Industrialisation
| Id | Item | Status | Owner |
|---|---|---|---|
| R-101 | This backlog and the working rules | done | operator |
| R-102 | GitHub Actions `unifai-operator.yml`: charts drift, unit+envtest, generated files committed, build, e2e compile, lint (new issues), bundle/catalog validation | done (runs once `devel` is pushed) | operator |
| R-103 | `make upstream-check` + `make -C fork/unifai-operator charts-check` | done | operator |
| R-104 | Lint debt: 30 existing golangci-lint findings (goconst, prealloc, gocyclo, errcheck in `internal/okf`, ...) then lint on the whole tree in CI | todo | operator (+ zuno-demo-68 for okf/agentbundle) |
| R-105 | Release from CI (image, bundle, catalog) with a quay robot secret; e2e stays on the cluster | todo (needs decision) | — |

## 2. Operator quality
| Id | Item | Status | Owner |
|---|---|---|---|
| R-201 | envtest for Provider, Retriever, Sandbox, Template; unit tests for `internal/unifai` (client, refs) | done (0.1.19) | operator |
| R-202 | Kubernetes Events on phase changes and errors (`EventRecorder` in `controller.Base`) | done (0.1.19) | operator |
| R-203 | Custom metrics (phase transitions, stack ready, Helm apply duration, Keycloak repairs) done (0.1.19); operator ServiceMonitor (OLM, OpenShift monitoring) todo | doing | operator |
| R-204 | e2e: Schedule, Template (done, 0.1.19), RAGPipeline with `E2E_FULL=1`; periodic `E2E_FULL=1 E2E_KEYCLOAK=1` run | doing | operator |
| R-205 | Tests of the UnifaiStack reconciler (post-render, plan) | todo | operator |
| R-206 | Canary used to run the previous release image (fixed in 0.1.18; e2e now checks the operator version) | done | operator |

## 3. Security and operations
| Id | Item | Status | Owner |
|---|---|---|---|
| R-301 | Narrow the operator ClusterRole (rbac, OLM rights only for managed Keycloak); study a namespaced mode | todo | operator |
| R-302 | NetworkPolicy: MAS/RAG reachable only from UI, identity and the operator, not the whole namespace; status warning when disabled | todo | operator |
| R-303 | Restore from backups (annotation or CR running mongorestore + Qdrant snapshot restore) | todo | operator |
| R-304 | CEL validation on the resource kinds; `v1beta1` once specs are stable | todo | operator |
| R-305 | demo333: GPU nodes NotReady after the 2026-10-22 restart (models, embeddings, RAG ingestion of zuno) | blocked (user) | user |

## 4. Upstream contribution
Order: smallest and least controversial first, each with `make contrib-check` / `contrib-pr`. Contact the maintainers
(CODEOWNERS) before the first PR.
| Id | Item | Status | Owner |
|---|---|---|---|
| R-401 | Chart defects: `helm/multiagent/be` template without extension, rabbitmq missing `common` dependency | todo | — |
| R-402 | `fix/multiagent-optional-corp-ca` | todo | — |
| R-403 | Internal auth header trusted from outside: private report to the maintainers first (security advisory), PR after | todo (needs decision) | user |
| R-404 | forwardUserToken + validator without model probe (`feat/forward-user-token`, `fix/openai-compatible-validator-forwarded-token`) | todo | zuno-demo-68 |
| R-405 | Qdrant hybrid search, shared ACL, Confluence source, OTel instrumentation | todo | — |

## 5. UnifAI features
| Id | Item | Status | Owner |
|---|---|---|---|
| R-501 | v0.11 work packages WP-146..157 (memory/routing/quota parity, gateway guardrails, ...) | doing | zuno-demo-59 |
| R-502 | WP-152 UnifaiAgentBundle `spec.mcp` per-task provider (committed dbfc4752e, ships in operator 0.1.19) | doing | zuno-demo-68 |
| R-503 | UnifaiRAGSource on `zuno-unifai` (waits for the GPU embedding service) | blocked | zuno-demo-68 |

## Older TODO carried over from MEMORY.md
- Slack tokens for the backend sidecar; scale `unifai-worker-a` down when idle.
- `admin` password is weak (user's choice): change it before wider exposure.
