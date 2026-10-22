# Memory tool (`type: memory`)

Durable memory shared by every run of one scope (for example a project). Nothing here
is specific to a deployment: the scope is an opaque string.

## Operations

| operation | arguments | effect |
| --- | --- | --- |
| `write` | `text`, `kind` | Stores a free-text memory: text in MongoDB, embedding in Qdrant. Deduplicated per scope on the whitespace/case-normalised text. |
| `read` | `query`, `top_k` | Vector search restricted to the scope; without `query`, the most recent memories. |
| `set_fact` | `key`, `value` | Upserts a structured fact (any JSON value, at most 64 KiB, key at most 200 chars). Last write wins. |
| `get_fact` | `key` | Returns the fact, or an error result if absent. |
| `list_facts` | `top_k` | Most recently updated facts of the scope. |

Every stored memory and fact carries optional provenance: `author`, `agent`, `session_id`,
`classification`, plus `created_at` (and `updated_at` for facts). `agent` and `session_id` are filled
from `bind_tool_context` when the node binds it; `author` and `classification` come from the config.
Missing values are `null`.

## Scope guard

`scope_id` is a **config** field. It is never read from the model's arguments, and every Mongo
and Qdrant query is filtered by it. **If the blueprint uses a placeholder such as `{project_id}`,
it must be resolved before the factory's `create` is called**; an empty scope is rejected.

## Access control

By default (`access.mode: none`) the tool trusts the blueprint, as before. Set an `access` block to
make every operation check the acting user first:

```yaml
config:
  type: memory
  scope_id: "<team id>"
  access:
    mode: team   # none | team | owner
```

- `team`: `scope_id` is a team id; the acting user must be a member (`IdentityProvider.is_member`).
- `owner`: `scope_id` must equal the acting user id.

The acting user is the credential user of the session's execution context, never a tool argument
(extra arguments such as `user` are ignored). The check fails closed: no execution context, no
identifiable user (e.g. a team session without a credential user), an identity provider error or a
non-member all return an error result (`memory access refused: ...`) and nothing is read, written or
embedded. A mode other than `none` without an identity provider or execution context makes the factory
fail at build time rather than run unprotected. The checker is the `ScopeAccessChecker` port in
`ports.py`; the provider comes from `ElementBuildContext.identity_provider`.

## Extraction

`extraction.MemoryExtractor` turns a conversation into candidate memories with a model:

```python
extractor = MemoryExtractor(llm, llm_for_classification=resolver)
result = extractor.extract(messages, classification="restricted")  # ExtractionResult
report = persist(result, memory_tool)                               # PersistReport
```

The model must answer one JSON object `{"facts": [{"key", "value"}], "memories": [{"text", "kind"}]}`.
Output is validated, never trusted: invalid JSON, a non-object, or an answer over `max_output_chars`
gives `ok=False` with an `error` (no exception); unknown fields, malformed entries, oversized
keys/values/texts, bad `kind` values (`^[a-z][a-z0-9_-]{0,31}$`) and entries over the caps are dropped
and counted in `dropped`. Only user and assistant turns are sent, as a JSON array in a delimited
`<transcript>` block that the prompt declares to be data; the most recent turns are kept when over
budget.

Classification: pass `classification` and a `llm_for_classification(classification) -> BaseLLM | None`
callable so the caller picks the model allowed to see such data (e.g. a local model for restricted
data). A `None` return, an exception, or a classification without a resolver refuses the extraction
before any model is called. Without a classification the default `llm` is used.

`persist` writes through `MemoryTool.run`, so scope access, limits, deduplication and provenance all
apply; the first access refusal stops the run, and a failed extraction is never written.

## Config

`scope_id` (required), `mongo_db`, `mongo_collection` (memories), `facts_collection`,
`qdrant_collection`, `embedding_service_url`, `embedding_model`, `embedding_dim`,
`top_k`, `min_score`, `author`, `classification`, `access.mode`.

## Environment

Defaults mirror the RAG service:

- `MONGODB_IP`, `MONGODB_PORT` (shared config).
- `QDRANT_IP`, `QDRANT_PORT`.
- `EMBEDDING_SERVICE_URL`, `EMBEDDING_SERVICE_MODEL`, `EMBEDDING_SERVICE_TIMEOUT`.

## Extending

Storage sits behind the `MemoryTextStore`, `FactStore`, `VectorIndex` and `Embedder`
protocols in `ports.py`; the Mongo/Qdrant adapters are in `adapters.py`. Optional dependencies:
`pip install 'mas[memory]'`.
