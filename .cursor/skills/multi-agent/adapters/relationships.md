---
name: adapters-relationships
scope: Deep implementation details for adapter conventions and port-to-adapter wiring
parent: _index.md
when_to_load: Implementing a new adapter, debugging wiring issues, or understanding Flask/Temporal patterns
---

# Flask Endpoint Conventions

## Decorator Stack Order

```
@bp.route("/api/<service>.<action>", methods=["POST"])
@with_require_identity_authorization     # resolves Identity
@from_body({"field": fields.Str()})      # parses request body
def handler(identity, **kwargs):         # receives both
    svc = current_app.container.<service>_service
    return jsonify(svc.<action>(identity=identity, **kwargs))
```

## Streaming Pattern

```python
return Response(
    with_heartbeats(channel_reader),
    mimetype="application/x-ndjson",
    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
)
```

## Error Mapping

Domain exceptions → HTTP: `BlueprintNotFoundError` → 404, `ValidationError` → 400.

---

# Temporal Conventions

## Workflow Structure

- Workflows implement `BackgroundSessionOps` (structural typing via Protocol)
- Lifecycle ordering lives in domain (`BackgroundSessionRunner`) — NOT in workflow
- Activities access container from worker context
- Workflow params are Pydantic models in `temporal/models.py`

## Rules

- Workflows NEVER import domain services (activities do)
- Inputs already staged before workflow starts
- `pydantic_data_converter` handles GraphState serialization

---

# Outbound Adapter Patterns

## Repository (Mongo)

```python
class MongoSessionRepository(SessionRepository):
    def __init__(self, mongodb_port, mongodb_ip, db_name, collection_name): ...
    def find_by_id(self, session_id, identity): ...  # scoped by identity
```

## Engine (LangGraph/Temporal)

```python
class LangGraphBuilder(BaseGraphBuilder):
    def compile(self) -> BaseGraphExecutor: ...

class LangGraphExecutor(BaseGraphExecutor):
    def run(self, initial_state, **kwargs) -> GraphState: ...
```

## External Service

```python
class GeminiFileUploadAdapter(IFileUploadService):
    def __init__(self, api_key, model_name): ...
    def upload_batch(self, files) -> List[FileUploadResult]: ...
```

---

# New Technology Directory Template

```
outbound/<technology>/
├── __init__.py              Re-export adapter classes
├── <port_a>_adapter.py      First port implementation
├── <port_b>_adapter.py      Second port (if applicable)
└── _client.py               Shared client setup (internal, _ prefix)
```
