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

## Extraction node (`type: memory_extractor_node`)

Blueprints run an extraction with the `memory_extractor_node` node (`lib/mas/elements/nodes/memory_extractor`).
It reads the session transcript (`messages`), calls `MemoryExtractor.extract` with `llm`, then `persist`s through
the memory tool referenced by `memory`, so the scope and the `access` block stay on the tool.

| field | meaning |
| --- | --- |
| `llm` | LLM used for the extraction (required). |
| `memory` | Reference to the memory tool (required). |
| `classification` | Optional classification of the transcript. |
| `local_llm` | Optional LLM allowed to see restricted classifications. |
| `restricted_classifications` | Case-insensitive list, default `restricted`, `confidential`, `secret`. |

Classification fallback: a classification outside `restricted_classifications` uses `llm`. A restricted one is only
ever sent to `local_llm`; **when no `local_llm` is configured the extraction is refused** before any model call and
nothing is written. The tool's own `classification` (provenance) is configured separately on the tool.

The node never raises: invalid model output, a model error, an access refusal or a failed write end up in a one-line
summary stored in `nodes_output[<node uid>]`, e.g. `memory extraction ok: 2 facts, 1 memories written, 0 dropped` or
`memory extraction failed: no model is approved for classification 'restricted'`.

## Example blueprint fragment

```yaml
llms:
  - {rid: extract_llm, name: extractor, type: openai, config: {type: openai, model_name: my-model}}
tools:
  - rid: project_memory
    name: project memory
    type: memory
    config:
      type: memory
      scope_id: "{project_id}"      # see "Placeholders" below: must be a literal id when the blueprint is stored
      access:
        mode: team                  # the acting user must be a member of the team "{project_id}"
nodes:
  - rid: remember
    name: Remember
    type: memory_extractor_node
    config:
      type: memory_extractor_node
      llm: extract_llm
      memory: project_memory
      classification: internal
plan:
  - {uid: remember, after: answer, node: remember}   # after the node that produces the answer
```

Agent nodes can also list `project_memory` in their `tools` to read and write it during the run.

## Placeholders

Nothing in the platform resolves `{project_id}`. The blueprint loader, the resolver, the element builders and the
factories pass `scope_id` through verbatim; the only `{...}` substitution that exists is for forwarded identity
headers (`{session_id}`, `{node_uid}`), and it does not apply to element configs. A literal `"{project_id}"` would be
used as the scope id (and, with `access.mode: team`, the membership check would run against that string and refuse).
Whatever creates or instantiates the blueprint must therefore replace it by the real id before the blueprint is stored
or built. A minimal in-platform mechanism, not implemented here, would be a `scope_from: team` option on the tool
config that takes the scope from the session identity (`ExecutionContext.identity.id`) at call time, which also fits
`access.mode: team`.

## Config

`scope_id` (required), `mongo_db`, `mongo_collection` (memories), `facts_collection`,
`qdrant_collection`, `qdrant_url`, `embedding_service_url`, `embedding_model`, `embedding_dim`,
`top_k`, `min_score`, `author`, `classification`, `access.mode`.

## Environment

Defaults mirror the RAG service:

- `MONGODB_IP`, `MONGODB_PORT` (shared config).
- `QDRANT_IP`, `QDRANT_PORT`. `QDRANT_IP` may be a bare host or carry a scheme and/or port
  (`qdrant`, `http://qdrant`, `https://qdrant:6334`). `QDRANT_PORT` may be an integer or the
  `tcp://host:port` value Kubernetes injects for a Service named `qdrant` (the port is taken; the host is
  only used when `QDRANT_IP` is empty). The `qdrant_url` config field overrides both.
- `EMBEDDING_SERVICE_URL`, `EMBEDDING_SERVICE_MODEL`, `EMBEDDING_SERVICE_TIMEOUT`.

## Extending

Storage sits behind the `MemoryTextStore`, `FactStore`, `VectorIndex` and `Embedder`
protocols in `ports.py`; the Mongo/Qdrant adapters are in `adapters.py`. Optional dependencies:
`pip install 'mas[memory]'`.
