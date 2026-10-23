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
| R-104 | Lint debt: existing golangci-lint findings fixed, CI lints the whole tree (`make lint`) | done | operator (+ zuno-demo-68 for okf/agentbundle) |
| R-105 | Release from CI: tag operator-vX.Y.Z publishes the bundle and the catalog (quay-release environment, approval, quay robot); the canary-tested image is not rebuilt; e2e stays on the cluster | done | operator |

## 2. Operator quality
| Id | Item | Status | Owner |
|---|---|---|---|
| R-201 | envtest for Provider, Retriever, Sandbox, Template; unit tests for `internal/unifai` (client, refs) | done (0.1.19) | operator |
| R-202 | Kubernetes Events on phase changes and errors (`EventRecorder` in `controller.Base`) | done (0.1.19) | operator |
| R-203 | Custom metrics (0.1.19); operator moved to namespace `unifai-operator` with a ServiceMonitor scraped by user-workload monitoring (0.1.21, demo333 2026-10-22) | done | operator |
| R-204 | e2e: Schedule, Template (done, 0.1.19), RAGPipeline with `E2E_FULL=1`; periodic `E2E_FULL=1 E2E_KEYCLOAK=1` run | doing | operator |
| R-205 | Tests of the UnifaiStack reconciler (post-render, plan; generated secrets, workload readiness, embedding, Keycloak realm import and deletion) | done | operator |
| R-206 | Canary used to run the previous release image (fixed in 0.1.18; e2e now checks the operator version) | done | operator |

## 3. Security and operations
| Id | Item | Status | Owner |
|---|---|---|---|
| R-301 | Narrow the operator ClusterRole (rbac, OLM rights only for managed Keycloak); study a namespaced mode | todo | operator |
| R-302 | NetworkPolicy: MAS/RAG/identity/backend reachable only from the UnifAI pods, the `internal-client` label and the operator, not the whole namespace; `NetworkIsolated` condition | done (0.1.26) | operator |
| R-303 | Restore from backups (annotation or CR running mongorestore + Qdrant snapshot restore) | todo | operator |
| R-304 | CEL validation on the resource kinds; `v1beta1` once specs are stable | todo | operator |
| R-305 | demo333: GPU nodes NotReady after the 2026-10-22 restart (models, embeddings, RAG ingestion of zuno) | done (nodes back the same evening; embeddings and RAG ingestion run) | user |

## 4. Upstream contribution
Order: smallest and least controversial first, each with `make contrib-check` / `contrib-pr`. Contact the maintainers
(CODEOWNERS) before the first PR.
| Id | Item | Status | Owner |
|---|---|---|---|
| R-401 | Chart defects: `helm/multiagent/be` template without extension, rabbitmq missing `common` dependency | todo | — |
| R-402 | `fix/multiagent-optional-corp-ca` | todo | — |
| R-403 | Internal auth header trusted from outside: fixed in the fork (shared INTERNAL_AUTH_SECRET, object-level checks, secret only sent to stack hosts; images devel-8fb04e165, operator 0.1.22+, deployed on demo333 2026-10-22). User decision 2026-10-22: fork patch only, no upstream report | done | operator |
| R-404 | forwardUserToken + validator without model probe (`feat/forward-user-token`, `fix/openai-compatible-validator-forwarded-token`); also candidates: team-session acting user (`fix/team-session-credential-user`), RAG groups for a team workspace (`fix/rag-team-workspace-groups`), final answer when an agent runs out of rounds (`fix/agent-wrap-up-at-round-limit`) | todo (all four live-proven on demo333) | zuno-demo-68 |
| R-405 | Qdrant hybrid search, shared ACL, Confluence source, OTel instrumentation | todo | — |

## 5. UnifAI features
| Id | Item | Status | Owner |
|---|---|---|---|
| R-501 | v0.11 work packages WP-146..157 (memory/routing/quota parity, gateway guardrails, ...) | doing | zuno-demo-59 |
| R-502 | WP-152 UnifaiAgentBundle `spec.mcp` per-task provider (operator 0.1.19), live-proven on demo333 with the zuno mcp-gateway | done | zuno-demo-68 |
| R-503 | UnifaiRAGSource on `zuno-unifai`: two Confluence sources (90 + 411 pages) ingested with group ACLs, no resync storm; Day-3 backup and restore drill in zuno-demo (`make d3 backup|check|restore unifai`) | done | zuno-demo-68 |
| R-504 | WP-147 operator part: `UnifaiStack.spec.openTelemetry` (OTEL_* env on multiagent, RAG, backend) | done (0.1.20) | operator |
| R-505 | Internal auth secret (`INTERNAL_AUTH_SECRET` / `X-Internal-Auth`, generated, injected, sent by the operator) and `spec.extraEnv` per component, for the access-control fixes of zuno-demo-59 | done (0.1.22) | operator |
| R-506 | `UnifaiTeam` (identity teams with user/group members) and `spec.teamRef` on every object, for group-entitled agent bundles (bundle side: zuno-demo-68) | done (0.1.24; delete deadlock team→object fixed in 0.1.25) | operator |

## Older TODO carried over from MEMORY.md
- Slack tokens for the backend sidecar; scale `unifai-worker-a` down when idle.
- `admin` password is weak (user's choice): change it before wider exposure.
