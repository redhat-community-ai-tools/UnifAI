# unifai-operator — declarative UnifAI (`unifai.startx.fr/v1alpha1`)

Declare UnifAI objects as Kubernetes custom resources; a small kopf controller reconciles them into UnifAI through its REST API
(`unifai-multiagent-be:8003`, `unifai-rag-server:13456`). Fork-only (`fork/`), never contributed upstream.

## Kinds

| CRD (short) | UnifAI object | API used |
|---|---|---|
| `UnifaiLLM` (ullm), `UnifaiProvider` (uprov), `UnifaiTool` (utool), `UnifaiCondition` (ucond), `UnifaiRetriever` (uretr), `UnifaiSandbox` (usbx), `UnifaiAgent` (uagent) | rows of Mongo `UnifAI.resources` (category llms/providers/tools/conditions/retrievers/sandboxes/nodes) | `/api/resources/resource.{save,update,delete}`, `config.validate` |
| `UnifaiWorkflow` (uwf) | blueprint (agentic workflow) | `/api/blueprints/blueprint.{save,update}`, `remove.blueprint` |
| `UnifaiSchedule` (usch) | scheduled workflow (Temporal) | `/api/schedules/schedule.{create,update,delete}` |
| `UnifaiTemplate` (utpl) | catalog template (admin only, no update API: delete + create) | `/api/templates/template.{create,delete}` |
| `UnifaiChat` (uchat) | one-shot chat session (create + submit prompt, result in `.status.result`) | `/api/sessions/user.session.{create,submit}`, `session.{status,chat}.get` |
| `UnifaiRAGPipeline` (urag) | document ingestion (upload, then chunk/embed into Qdrant) | rag-server `/api/docs/upload`, `PUT /api/pipelines/embed` |

`kubectl get unifai` lists them all. `status`: `phase` (Ready/Error/...), `message`, `rid`/`blueprintId`/`scheduleId`/..., `hash`.

## Spec conventions
- `spec.owner` (default `admin`) is the UnifAI user owning the object; `spec.teamId` targets a team workspace; `spec.unifaiName` overrides the name (default `metadata.name`).
- `spec.type` + `spec.config` = UnifAI `type` + `cfg_dict`. The accepted types are those the deployed instance serves: `GET /api/catalog/elements.list.get`
  (on demo333: llms openai/openai_compatible/google_genai; conditions router_direct; tools oc_exec/ssh_exec/web_fetch; providers mcp_server; retrievers docs_rag; sandboxes openshell_sandbox; nodes custom_agent/orchestrator/a2a_agent/deep_agent/claude_agent).
  Each change is first checked with `config.validate`; an invalid spec gives `phase: Error` (permanent) with UnifAI's message.
- `spec.secretRefs: [{path: api_key, secretKeyRef: {name, key}}]` injects a Secret value at a dotted path of the config. UnifAI encrypts it at rest.
- References: `$ref:<kind>/<name>` becomes `$ref:<rid>` (kind = llm|provider|tool|retriever|sandbox|condition|agent); `$rid:<kind>/<name>` becomes the bare rid (blueprint `plan`).
  A missing target is retried every 10 s (`ordering` is thus free in a single `kubectl apply`).
- Workflows: node entries `{rid: "$ref:agent/x"}` without `config` are expanded with the library agent's config (what the UI stores).
- Idempotent upsert on `(owner, category, name)`. An object already present in UnifAI but not owned by a CR is **not** touched unless the CR carries the annotation `unifai.startx.fr/adopt: "true"`.
- Deleting a CR deletes the UnifAI object; one still referenced (`ResourceInUse`) is retried every 30 s: delete the dependants first.

## Deploy
```
kubectl apply -k fork/unifai-operator          # CRDs + RBAC + operator (code in a ConfigMap, pip install at start)
kubectl -n unifai-devel apply -k fork/unifai-operator/examples/demo-backends   # test LLM + MCP (optional)
kubectl -n unifai-devel apply -f fork/unifai-operator/examples/00-secrets/secrets.example.yaml   # placeholders: edit first
kubectl -n unifai-devel apply -f examples/llm -f examples/provider -f examples/tool -f examples/condition \
  -f examples/agent/agents.yaml -f examples/retriever -f examples/workflow -f examples/schedule -f examples/chat -f examples/template
```
CRDs are generated: edit `gen_crds.py`, run `python3 gen_crds.py`. An image can replace the ConfigMap approach: `operator/Dockerfile` (not built: pushing to `quay.io/zuno` needs credentials).

## Examples (`examples/`)
`llm` (fake/vLLM/OpenAI/Gemini), `provider` (MCP without auth and with bearer), `tool` (web_fetch, oc_exec, ssh_exec), `condition` (router_direct),
`agent` (ReAct custom agent, orchestrator, a2a; `not-applied/` claude agent), `retriever` (docs_rag), `sandbox` (openshell, not applied: no gateway),
`workflow` (linear, branches, orchestrated, rag), `schedule` (interval + cron/timezone), `chat` (smoke test), `template` (2 catalog templates), `rag` (ingestion), `demo-backends` (offline fake LLM + MCP).
The `demo-fake` LLM answers a constant text, so `UnifaiChat/demo-chat-smoke` validates the whole chain with no model or key.

## RAG data pipeline (what is and is not declarative)
- Per-document ingestion: `UnifaiRAGPipeline`. Global behaviour is environment configuration of rag-server/rag-celery (Helm overlay `fork/values/rag-resource-values.yaml`):
  `USE_REMOTE_DOCLING`, `DOCLING_SERVICE_URL`, `USE_REMOTE_EMBEDDING`, `EMBEDDING_SERVICE_URL`, `EMBEDDING_SERVICE_MODEL`, `EMBEDDING_DIM`.
- Chunking is hard-coded (500 tokens, 50 overlap: `rag/bootstrap/app_container.py`); Qdrant collections `document_data` / `slack_data` are created automatically.
- On demo333 `rag-celery` is Pending (GPU request), so submitted pipelines stay queued in RabbitMQ until it runs.

## Security notes
- The operator authenticates with the `X-Authenticated-User` header that multiagent-be/rag-server accept without a session. Anything that can reach those services can impersonate any user:
  restrict ingress with a NetworkPolicy (not applied yet: it must also allow the UI nginx, identity and the Routes) and keep the public Routes under review.
- Secret values are only read from Secrets of the CR's namespace; `status.hash` is a truncated SHA-256 of the resolved spec.
- `$ref:` of deleted/renamed objects is not rewritten in existing blueprints: UnifAI refuses deleting referenced resources, which protects this case.
