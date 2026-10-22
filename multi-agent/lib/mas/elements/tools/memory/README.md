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

## Config

`scope_id` (required), `mongo_db`, `mongo_collection` (memories), `facts_collection`,
`qdrant_collection`, `embedding_service_url`, `embedding_model`, `embedding_dim`,
`top_k`, `min_score`, `author`, `classification`.

## Environment

Defaults mirror the RAG service:

- `MONGODB_IP`, `MONGODB_PORT` (shared config).
- `QDRANT_IP`, `QDRANT_PORT`.
- `EMBEDDING_SERVICE_URL`, `EMBEDDING_SERVICE_MODEL`, `EMBEDDING_SERVICE_TIMEOUT`.

## Extending

Storage sits behind the `MemoryTextStore`, `FactStore`, `VectorIndex` and `Embedder`
protocols in `ports.py`; the Mongo/Qdrant adapters are in `adapters.py`. Optional dependencies:
`pip install 'mas[memory]'`.
