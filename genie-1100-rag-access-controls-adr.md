# Architecture Design Review (ADR)

**Feature Name:** [GENIE-1100](https://redhat.atlassian.net/browse/GENIE-1100) — User-Level Access Controls for RAG Document Ingestion and Retrieval Scoping

**Author:** Pipeline Designer Agent | **Date:** 2026-06-24 | **Priority:** High

---

## 1. Executive Summary

| Section | Details |
| :--- | :--- |
| **Problem Statement** | The RAG pipeline stores vector chunks in Qdrant without `owner_id` metadata and performs retrieval queries without user-scoped filtering. Any user or agent can semantically search and retrieve chunks from any document regardless of who uploaded it, creating a data leakage risk in shared environments. |
| **High-Level Solution** | Add `owner_id` to every vector chunk payload during ingestion by propagating the authenticated user's identity through the Celery pipeline. Enforce mandatory user-scoped filtering on all retrieval queries by replacing the current opt-in `scope` parameter with a default-private model. Create a Qdrant keyword index on `owner_id` for filtering performance. Provide a migration CLI command for backfilling existing vectors. |
| **Success Metrics** | (1) Every new Qdrant point contains `metadata.owner_id` matching the uploader's username. (2) User A's queries return zero results from User B's documents. (3) Search latency remains within 10% of current baseline after adding the `owner_id` filter. (4) All existing vectors are backfilled with `owner_id` via migration script. |

---

## 2. Affected Components

| Layer | Component | Action (New/Modified) | File Path |
| :--- | :--- | :--- | :--- |
| Domain | `VectorChunk` metadata contract | Modified — document `owner_id` as required metadata key | `rag/core/vector/domain/model.py` |
| Domain | `PipelineContext` | Modified — add `owner_id` field | `rag/core/pipeline/domain/port.py` |
| Application | `RetrievalService.search()` | Modified — enforce `owner_id` filter by default | `rag/core/retrieval/service.py` |
| Application | `PipelineDispatchService.start_pipeline()` | Modified — pass `upload_by` as owner context (already does, verify propagation) | `rag/core/pipeline/dispatch_service.py` |
| Adapter — API / Inbound | `docs_bp /query.match` | Modified — remove `scope` param, always pass `g.user_id` as `owner_id` | `rag/infrastructure/http/docs.py` |
| Adapter — API / Inbound | `slack_bp` search endpoint | Modified — same owner-scoped filtering | `rag/infrastructure/http/slack.py` |
| Adapter — Outbound | `QdrantVectorRepository.initialize()` | Modified — add `metadata.owner_id` keyword index | `rag/infrastructure/qdrant/qdrant_vector_repository.py` |
| Adapter — Pipeline Handler | `DocumentPipelineHandler.chunk_and_embed()` | Modified — inject `owner_id` into chunk metadata | `rag/core/data_sources/types/document/pipeline_handler.py` |
| Adapter — Pipeline Handler | `SlackPipelineHandler.chunk_and_embed()` | Modified — inject `owner_id` into chunk metadata | `rag/core/data_sources/types/slack/pipeline_handler.py` |
| Adapter — Celery | `build_context()` | Modified — extract `owner_id` from `source_data` and add to `PipelineContext` | `rag/infrastructure/celery/workers/pipeline_tasks.py` |
| Config / Infra | Migration CLI command | New — backfill `owner_id` on existing Qdrant vectors | `rag/infrastructure/cli/migrate_owner_id.py` |
| Config / Infra | Qdrant payload index | New — keyword index on `metadata.owner_id` | (applied via `QdrantVectorRepository.initialize()` + migration) |

---

## 3. Technical Design

### 3.1 PipelineContext — Add `owner_id`

**Purpose:** Carry the uploading user's identity through the entire pipeline execution.

**File:** `rag/core/pipeline/domain/port.py`

**Current signature:**
```python
@dataclass(frozen=True)
class PipelineContext:
    pipeline_id: str
    source_type: str
    source_id: str
    source_name: str
    metadata: Dict[str, Any]
```

**Proposed change:** Add an explicit `owner_id: str` field. This is safer than relying on `metadata["upload_by"]` because the frozen dataclass makes the field immutable and statically visible:

```python
@dataclass(frozen=True)
class PipelineContext:
    pipeline_id: str
    source_type: str
    source_id: str
    source_name: str
    owner_id: str
    metadata: Dict[str, Any]
```

**Dependencies:** All callers that construct `PipelineContext` must supply `owner_id`.

**Backward compatibility:** `owner_id` is a required positional-style argument. The only call site is `build_context()` in `pipeline_tasks.py` — single place to update.

### 3.2 Celery Task — Extract `owner_id` from `source_data`

**Purpose:** The Celery adapter translates message format to domain types. `owner_id` must be extracted from the registered source data (where `upload_by` is already present).

**File:** `rag/infrastructure/celery/workers/pipeline_tasks.py`

**Current `build_context()` builds:**
```python
return PipelineContext(
    pipeline_id=pipeline_id,
    source_type=source_type.upper(),
    source_id=source_id,
    source_name=source_name,
    metadata=metadata,
)
```

**Proposed change:**
```python
owner_id = source_data.get("upload_by") or metadata.get("upload_by", "")
if not owner_id:
    raise ValueError("owner_id (upload_by) is required for pipeline execution")

return PipelineContext(
    pipeline_id=pipeline_id,
    source_type=source_type.upper(),
    source_id=source_id,
    source_name=source_name,
    owner_id=owner_id,
    metadata=metadata,
)
```

**Key logic:** The `upload_by` field already flows through the registration pipeline into `source_data` (see `BaseRegistration._build_registered_source()` at `rag/core/registration/base_registration.py:84`). The Celery task simply needs to extract it and reject messages that lack it.

### 3.3 Document Pipeline Handler — Inject `owner_id` into chunk metadata

**Purpose:** Every `VectorChunk` stored in Qdrant must carry `owner_id` in its metadata payload so retrieval queries can filter by owner at the database level.

**File:** `rag/core/data_sources/types/document/pipeline_handler.py`

**Current `chunk_and_embed()` enrichment (lines 112-116):**
```python
for idx, chunk in enumerate(chunks):
    chunk.setdefault("metadata", {}).update({
        "source_id": context.source_id,
        "source_type": self.source_type,
    })
```

**Proposed change:**
```python
for idx, chunk in enumerate(chunks):
    chunk.setdefault("metadata", {}).update({
        "source_id": context.source_id,
        "source_type": self.source_type,
        "owner_id": context.owner_id,
    })
```

**Same change applies to `SlackPipelineHandler.chunk_and_embed()`** — `owner_id` must be added to the metadata enrichment step identically.

### 3.4 Qdrant Vector Repository — Add `owner_id` index

**Purpose:** A keyword index on `metadata.owner_id` is essential for Qdrant to efficiently filter search results by owner without full scan.

**File:** `rag/infrastructure/qdrant/qdrant_vector_repository.py`

**Current `initialize()` creates indexes for:**
```python
self._create_payload_index("metadata.source_type", qmodels.PayloadSchemaType.KEYWORD)
self._create_payload_index("metadata.channel_name", qmodels.PayloadSchemaType.KEYWORD)
self._create_payload_index("metadata.source_id", qmodels.PayloadSchemaType.KEYWORD)
```

**Proposed change — add:**
```python
self._create_payload_index("metadata.owner_id", qmodels.PayloadSchemaType.KEYWORD)
```

**Note:** For existing collections, the migration CLI (section 3.7) will create the index and backfill data.

### 3.5 Retrieval Service — Enforce owner-scoped filtering

**Purpose:** All retrieval queries must be scoped to the requesting user by default. The current `scope` parameter (`"public"` / `"private"`) is replaced with mandatory `owner_id` filtering.

**File:** `rag/core/retrieval/service.py`

**Current behavior:**
- `scope="public"` → no user filter (all documents searchable)
- `scope="private"` → adds `metadata.upload_by` filter

**Proposed behavior:**
- Always add `metadata.owner_id` filter matching the requesting user
- Remove the `scope` and `user` parameters
- Add required `owner_id: str` parameter

**Proposed signature:**
```python
def search(
    self,
    query: str,
    owner_id: str,
    limit: int = 5,
    doc_ids: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
```

**Key logic:**
```python
# Build vector search filters
filters: Dict[str, Any] = {}

# MANDATORY owner scoping — private by default
filters["metadata.owner_id"] = owner_id

if allowed_source_ids:
    filters["metadata.source_id"] = list(allowed_source_ids)

# ... rest unchanged
```

**Impact on SearchQuery dataclass:** Remove `scope` and `user` fields, add `owner_id: str`.

### 3.6 Flask Endpoints — Pass `owner_id` from session

**Purpose:** Inbound adapters extract the authenticated user's identity and pass it to the retrieval service.

**File:** `rag/infrastructure/http/docs.py`

**Current `query_match` (line 188-195):**
```python
svc = retrieval_service("DOCUMENT")
results = svc.search(
    query=query,
    limit=top_k_results,
    scope=scope,
    user=g.user_id,
    doc_ids=doc_ids,
    tags=tags,
)
```

**Proposed change:**
```python
svc = retrieval_service("DOCUMENT")
results = svc.search(
    query=query,
    owner_id=g.user_id,
    limit=top_k_results,
    doc_ids=doc_ids,
    tags=tags,
)
```

- Remove the `scope` query parameter from `@from_query`
- Same change for the Slack search endpoint
- The `@rag_require_session` decorator already populates `g.user_id` with the authenticated `username` from the Redis session (via `require_team_session` in `global_utils/flask/decorators.py:163`)

### 3.7 Migration CLI — Backfill existing vectors

**Purpose:** Existing Qdrant vectors lack `owner_id`. A migration script must backfill this field using the `upload_by` stored in the MongoDB `data_sources.sources` collection.

**File:** `rag/infrastructure/cli/migrate_owner_id.py` (new)

**Key logic (pseudocode):**
```python
def migrate_owner_id(qdrant_client, mongo_sources_collection, collection_name):
    # 1. Create keyword index on metadata.owner_id
    qdrant_client.create_payload_index(
        collection_name=collection_name,
        field_name="metadata.owner_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )

    # 2. Build source_id -> owner_id lookup from MongoDB
    source_owner_map = {
        doc["source_id"]: doc["upload_by"]
        for doc in mongo_sources_collection.find({}, {"source_id": 1, "upload_by": 1})
    }

    # 3. Scroll through all Qdrant points
    offset = None
    while True:
        points, offset = qdrant_client.scroll(
            collection_name=collection_name,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        if not points:
            break

        # 4. For each point, resolve owner_id from source_id
        for point in points:
            source_id = point.payload.get("metadata", {}).get("source_id", "")
            owner_id = source_owner_map.get(source_id, "unknown")

            # 5. Set payload (partial update — only adds/updates owner_id)
            qdrant_client.set_payload(
                collection_name=collection_name,
                payload={"metadata": {"owner_id": owner_id}},
                points=[point.id],
            )

        if offset is None:
            break
```

**Dependencies:** Requires access to both Qdrant and MongoDB. Reads MongoDB `data_sources.sources` collection to map `source_id → upload_by`.

**Idempotency:** Safe to re-run — `set_payload` is an upsert on the payload key, and `create_payload_index` is idempotent if the index already exists.

**Entry point:** Add as a CLI command invokable via `python -m infrastructure.cli.migrate_owner_id` or integrate into the existing entry point pattern if one exists.

---

## 4. Data Flow

### Ingestion (Write Path)

```
1. User uploads document via UI
2. POST /api/pipelines/embed
   → @rag_require_session populates g.user_id (from Redis session → UserSessionData.username)
   → PipelineDispatchService.start_pipeline(upload_by=g.user_id)
   
3. RegistrationService.register_sources(upload_by=...)
   → BaseRegistration._build_registered_source() includes upload_by in response dict
   → DataSource persisted to MongoDB with upload_by

4. CeleryPipelineDispatcher.dispatch(source_data={..., "upload_by": "alice"})
   → RabbitMQ → Celery worker

5. execute_pipeline_task()
   → build_context() extracts owner_id from source_data["upload_by"]
   → PipelineContext(owner_id="alice", ...)

6. PipelineExecutor.execute(handler, context)
   → handler.chunk_and_embed(context, processed)
      → Each chunk enriched with metadata.owner_id = context.owner_id

7. QdrantVectorRepository.store(chunks)
   → Qdrant point payload: {"text": "...", "metadata": {"owner_id": "alice", "source_id": "...", ...}}
```

### Retrieval (Read Path)

```
1. GET /api/docs/query.match?query=...
   → @rag_require_session populates g.user_id

2. RetrievalService.search(query=..., owner_id=g.user_id)
   → MANDATORY: filters["metadata.owner_id"] = owner_id
   → Optional: filters["metadata.source_id"] = [resolved source_ids]

3. QdrantVectorRepository.search(query_embedding, filters)
   → Qdrant applies Filter(must=[FieldCondition(key="metadata.owner_id", match="alice")])
   → Only points with matching owner_id are considered for similarity search

4. Results returned — guaranteed to belong to requesting user
```

---

## 5. Risk & Reliability

### 5a. Edge Cases & Failure Modes

| Risk / Edge Case | Mitigation |
| :--- | :--- |
| **Legacy vectors without `owner_id`** | Migration script (section 3.7) backfills from MongoDB. Points with unmapped `source_id` get `owner_id="unknown"` — these will only be visible to searches explicitly filtered by `owner_id="unknown"` (i.e., no user will accidentally see them). |
| **Celery task receives `source_data` without `upload_by`** | `build_context()` raises `ValueError`, task fails and is visible in pipeline monitoring. No silent data leakage — fail loud. |
| **User ID format inconsistency** | The auth decorator sets `g.user_id = data.username` (Keycloak username). The same `username` flows through `upload_by` in the pipeline. Both sides use the same `UserSessionData.username` field, ensuring consistency. |
| **Breaking change to `scope` parameter** | Frontend must remove the `scope` query parameter from search API calls. Coordinate deployment with UI update. Alternatively, keep `scope` as ignored parameter for one release cycle for backward compatibility. |
| **`PipelineContext` signature change breaks tests** | Update all test fixtures in `rag/tests/unit/conftest.py` and individual tests that construct `PipelineContext` to include `owner_id`. |
| **Qdrant `set_payload` merges nested objects** | Qdrant's `set_payload` with `{"metadata": {"owner_id": "alice"}}` will merge into existing metadata, not replace it. This is the desired behavior — other metadata fields (`source_id`, `source_type`) are preserved. |
| **MCP servers / agents calling RAG search** | Must propagate user context. Agents inherit the querying user's session via the same session cookie / auth header. No code change needed — the `@rag_require_session` decorator applies to all callers. |

### 5b. External Dependency Failure Modes

| Dependency | Failure Scenario (401 / 503 / timeout) | Behavior (silent / noisy) | Degradation Path |
| :--- | :--- | :--- | :--- |
| **Qdrant** (index creation during migration) | 503 — Qdrant unreachable | Noisy — migration script fails with exception | Retry migration when Qdrant is available. Index creation is idempotent. |
| **MongoDB** (source_id → owner lookup during migration) | 503 — MongoDB unreachable | Noisy — migration fails | Retry migration. Read-only operation, no side effects on failure. |
| **Redis** (session validation) | 503 — Redis unreachable | Noisy — 401 returned to user | Existing behavior unchanged. No new Redis dependency introduced. |

### 5c. Local Development & Partial-Access Deployment

| Dependency | Local Dev Strategy | Deployment Without This Dependency |
| :--- | :--- | :--- |
| **Qdrant** | Existing local Qdrant container (already part of dev setup). `owner_id` index is created on first `initialize()` call. Migration script runs against local Qdrant. | Without Qdrant: RAG service is non-functional (existing constraint). No new dependency introduced. |
| **MongoDB** | Existing local MongoDB (already part of dev setup). Source documents already contain `upload_by` field. | Without MongoDB: registration fails (existing constraint). No new dependency introduced. |
| **Redis** (identity sessions) | Existing local Redis (already part of dev setup). `DevOAuthClient` creates sessions with username. `g.user_id` is populated from session. | Without Redis: auth fails with 401 (existing constraint). No new dependency introduced. |

### 5d. AI-Specific Risks

*Not applicable — this feature does not involve LLM / AI components.*

---

## 6. Open Questions

- [ ] **Shared document access (future):** The ticket explicitly puts sharing/collaborative permissions out of scope. However, the design should be forward-compatible. The chosen approach (per-point `owner_id` metadata + filter) supports future extension by adding an `allowed_viewers: List[str]` field and using Qdrant's `should` filter (OR logic). Should we reserve the payload field name now?

- [ ] **MCP server agent identity:** When an MCP server or agent makes a RAG search call on behalf of a user, does the session cookie propagate correctly through the proxy chain? This needs verification in the deployment topology (Nginx → MAS → RAG).

- [ ] **`scope=public` backward compatibility:** The current API supports `scope=public` for cross-user search. Removing it is a breaking change for any external API consumers. Should we keep it behind a feature flag or admin override for a transition period, or is immediate removal acceptable?

- [ ] **Migration batch size and performance:** For large Qdrant collections, the point-by-point `set_payload` in the migration script may be slow. Should we implement batch `set_payload` (Qdrant supports it via `PointIdsList`) and what is the expected collection size to estimate migration duration?

- [ ] **Upload endpoint auth:** The `/docs/upload` endpoint currently has NO `@rag_require_session` decorator (see `rag/infrastructure/http/docs.py:20-39`). Documents uploaded via this unauthenticated endpoint have no `upload_by` context. Should this endpoint also require auth, or is it intentionally unauthenticated (e.g., for internal service-to-service calls)?

---

## 7. Reviewer Feedback

<!-- This section is populated by the Design Reviewer (Phase 2). Do not fill manually. -->

### Verdict: **[PENDING]**

<!-- One of: APPROVE / NEEDS REVISION / REJECT -->

### Critical Findings

<!-- Issues that must be fixed before proceeding. -->

### Architectural Violations

<!-- Hexagonal architecture violations with layer, issue, and fix. -->

### Efficiency Concerns

<!-- Performance or scalability problems with alternatives. -->

### Duplication & Reusability Issues

<!-- Existing components that should be reused. -->

### Risks to Existing System

<!-- Breaking changes, side effects, migration concerns. -->

### Local Dev & Partial-Access Deployment Findings

<!-- Missing local-dev or partial-access deployment strategies. -->

### Recommended Improvements

<!-- Concrete suggestions to improve the design. -->

### Revision Items

<!-- If verdict is not APPROVE, list every item the Designer must address. -->

- [ ] ...
