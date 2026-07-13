# Architecture Design Review (ADR)

**Feature Name:** Scheduled Workflow Prompts

**Author:** Agent | **Date:** 2026-07-13 | **Priority:** High

---

## 1. Executive Summary

| Section | Details |
| :--- | :--- |
| **Problem Statement** | All blueprint execution is currently on-demand (user calls create → submit/execute). There is no way to schedule recurring execution of a blueprint on an interval or cron expression. Users need automated, hands-off execution for monitoring dashboards, periodic data refreshes, and scheduled reports. |
| **High-Level Solution** | Introduce a `Prompt` domain model that can optionally carry a schedule definition, and a `ScheduleService` that uses Temporal's native Schedules API to trigger a fresh session creation + execution on each tick. The Prompt model unifies prompt content with scheduling metadata, and the schedule option appears as a dropdown in the UI. |
| **Success Metrics** | Schedules create and execute sessions end-to-end within the configured interval/cron. Scheduled sessions are indistinguishable from manual sessions (same status flow, chat, state). Zero impact to existing manual submit/execute flow. |

---

## 2. Affected Components

| Layer | Component | Action (New/Modified) | File Path |
| :--- | :--- | :--- | :--- |
| Domain | `Prompt` model (with optional schedule) | **New** | `lib/mas/prompts/models.py` |
| Domain | `ScheduleDefinition` value object | **New** | `lib/mas/prompts/models.py` |
| Domain | `ScheduleStatus` enum | **New** | `lib/mas/prompts/models.py` |
| Domain | `PromptRepository` port (ABC) | **New** | `lib/mas/prompts/repository.py` |
| Domain | `SchedulePort` outbound port (ABC) | **New** | `lib/mas/prompts/ports.py` |
| Application | `PromptService` | **New** | `lib/mas/prompts/service.py` |
| Application | `SessionService` | **Modified** — add `source` metadata awareness | `lib/mas/session/service.py` |
| Adapter — Inbound | Flask schedule endpoints | **New** | `adapters/inbound/flask/endpoints/prompts.py` |
| Adapter — Inbound | `ScheduledSessionWorkflow` | **New** | `adapters/inbound/temporal/workflows/scheduled_session_workflow.py` |
| Adapter — Inbound | `ScheduleActivities` | **New** | `adapters/inbound/temporal/activities/schedule_activities.py` |
| Adapter — Outbound | `TemporalScheduleAdapter` | **New** | `adapters/outbound/temporal/schedule_adapter.py` |
| Adapter — Outbound | `MongoPromptRepository` | **New** | `adapters/outbound/mongo/prompt_repository.py` |
| Adapter — Inbound | Endpoint registration | **Modified** | `adapters/inbound/flask/endpoints/__init__.py` |
| Adapter — Inbound | Worker registration | **Modified** | `adapters/inbound/temporal/worker.py` |
| Adapter — Shared | Temporal DTO models | **Modified** — add `ScheduledSessionParams` | `adapters/temporal/models.py` |
| Database | `prompts` collection | **New** | — |
| Config / Infra | `schedules_coll` config | **Modified** | `config/app_config.py` |
| Config / Infra | Container wiring | **Modified** | `bootstrap/container.py` |

---

## 3. Technical Design

### 3.0 Domain — `Prompt` Model

**Purpose**: First-class domain model representing a reusable prompt that can optionally be tied to a schedule. This replaces the flat `PromptShortcutItem` for scheduled use cases and provides the "scheduled" dropdown option in the UI.

**Interfaces / Ports**:

```python
class ScheduleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DELETED = "deleted"

class ScheduleOverlapPolicy(str, Enum):
    SKIP = "skip"
    BUFFER_ONE = "buffer_one"
    CANCEL_OTHER = "cancel_other"
    ALLOW_ALL = "allow_all"

class ScheduleDefinition(BaseModel):
    """Value object — the scheduling configuration for a prompt."""
    model_config = ConfigDict(frozen=True)

    interval: Optional[timedelta] = None       # e.g. every 30 min
    cron_expression: Optional[str] = None      # e.g. "0 9 * * MON-FRI"
    overlap_policy: ScheduleOverlapPolicy = ScheduleOverlapPolicy.SKIP
    enabled: bool = True

    @model_validator(mode="after")
    def _exactly_one_trigger(self) -> "ScheduleDefinition":
        if not self.interval and not self.cron_expression:
            raise ValueError("Either interval or cron_expression is required")
        if self.interval and self.cron_expression:
            raise ValueError("Specify interval or cron_expression, not both")
        return self

class Prompt(BaseModel):
    """
    A reusable prompt that can optionally be scheduled for recurring execution.
    
    When `schedule` is None, this is a manual-only prompt.
    When `schedule` is set, the prompt is executed on the defined interval/cron.
    """
    prompt_id: str = Field(default_factory=lambda: str(uuid4()))
    blueprint_id: str
    identity: Identity
    text: str                                    # the prompt content / user_prompt
    inputs: Dict[str, Any] = Field(default_factory=dict)
    schedule: Optional[ScheduleDefinition] = None
    schedule_status: ScheduleStatus = ScheduleStatus.ACTIVE
    temporal_schedule_id: Optional[str] = None   # set by adapter after creation
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

**Key decisions**:
- `Prompt` owns both the content (`text`, `inputs`) and the optional scheduling config. This keeps the domain model cohesive — a prompt *is* what gets executed, and it *may* be scheduled.
- `ScheduleDefinition` is a frozen value object with mutual-exclusion validation (interval XOR cron).
- `schedule_status` lives on the Prompt because the domain needs to know whether the schedule is active for listing/filtering. Temporal is still the source of truth for next-run/pause state.

**Dependencies**: `Identity`, `BaseModel` (Pydantic)

### 3.1 Domain — `PromptRepository` Port

**Purpose**: Persistence port for the Prompt aggregate.

```python
class PromptRepository(ABC):
    @abstractmethod
    def save(self, prompt: Prompt) -> str: ...

    @abstractmethod
    def load(self, prompt_id: str) -> Prompt: ...

    @abstractmethod
    def update(self, prompt: Prompt) -> bool: ...

    @abstractmethod
    def delete(self, prompt_id: str) -> bool: ...

    @abstractmethod
    def list_by_identity(
        self, identity: Identity,
        *, skip: int = 0, limit: int = 100,
        scheduled_only: bool = False,
    ) -> List[Prompt]: ...

    @abstractmethod
    def find_by_blueprint(self, blueprint_id: str) -> List[Prompt]: ...
```

**Dependencies**: `Prompt`, `Identity`

### 3.2 Domain — `SchedulePort` Outbound Port

**Purpose**: Abstracts the scheduling infrastructure (Temporal Schedules API) behind a domain port so the domain never imports `temporalio`.

```python
class SchedulePort(ABC):
    @abstractmethod
    def create_schedule(self, prompt: Prompt) -> str:
        """Create a schedule targeting ScheduledSessionWorkflow. Returns temporal_schedule_id."""

    @abstractmethod
    def pause(self, temporal_schedule_id: str) -> None: ...

    @abstractmethod
    def resume(self, temporal_schedule_id: str) -> None: ...

    @abstractmethod
    def delete(self, temporal_schedule_id: str) -> None: ...

    @abstractmethod
    def trigger_now(self, temporal_schedule_id: str) -> None: ...
```

**Dependencies**: `Prompt`

### 3.3 Application — `PromptService`

**Purpose**: Orchestrates prompt CRUD and schedule lifecycle. Single entry point for all prompt/schedule operations.

```python
class PromptService:
    def __init__(
        self,
        prompt_repo: PromptRepository,
        schedule_port: Optional[SchedulePort],
        blueprint_service: BlueprintService,
    ): ...

    def create(
        self, *, identity: Identity, blueprint_id: str,
        text: str, inputs: dict,
        schedule: Optional[dict] = None,
    ) -> Prompt:
        """Validate blueprint exists, persist prompt, optionally create Temporal schedule."""

    def pause(self, prompt_id: str, *, identity: Identity) -> Prompt: ...
    def resume(self, prompt_id: str, *, identity: Identity) -> Prompt: ...
    def delete(self, prompt_id: str, *, identity: Identity) -> None: ...
    def trigger_now(self, prompt_id: str, *, identity: Identity) -> str: ...
    def list(self, *, identity: Identity, scheduled_only: bool = False) -> List[Prompt]: ...
    def get(self, prompt_id: str, *, identity: Identity) -> Prompt: ...
```

**Key logic (create)**:
1. Validate `blueprint_service.exists(blueprint_id)` — raise `BlueprintNotFoundError` if missing
2. Parse `ScheduleDefinition` from `schedule` dict (if provided)
3. Build `Prompt` model
4. `prompt_repo.save(prompt)`
5. If `schedule` is set and `schedule_port` is not None:
   - `temporal_id = schedule_port.create_schedule(prompt)`
   - Update prompt with `temporal_schedule_id`, re-save
6. Return prompt

**Dependencies**: `PromptRepository`, `SchedulePort` (optional), `BlueprintService`

### 3.4 Adapter — `TemporalScheduleAdapter`

**Purpose**: Implements `SchedulePort` using Temporal's native Schedules API (`temporalio>=1.4.0`).

```python
class TemporalScheduleAdapter(SchedulePort):
    def create_schedule(self, prompt: Prompt) -> str:
        # Build ScheduleSpec from prompt.schedule (interval or cron)
        # Map ScheduleOverlapPolicy → temporalio.common.ScheduleOverlapPolicy
        # Create Schedule targeting "ScheduledSessionWorkflow" with ScheduledSessionParams
        # Return schedule handle ID

    def pause(self, temporal_schedule_id: str) -> None:
        # schedule_handle.pause()

    def resume(self, temporal_schedule_id: str) -> None:
        # schedule_handle.unpause()

    def delete(self, temporal_schedule_id: str) -> None:
        # schedule_handle.delete()

    def trigger_now(self, temporal_schedule_id: str) -> None:
        # schedule_handle.trigger()
```

**Dependencies**: `temporal.client.get_temporal_client()`, `AppConfig` (for task_queue)

### 3.5 Adapter — `ScheduledSessionWorkflow`

**Purpose**: Temporal workflow triggered on each schedule tick. Creates a new session from the prompt's blueprint and executes it end-to-end.

```python
@workflow.defn
class ScheduledSessionWorkflow:
    @workflow.run
    async def run(self, params: ScheduledSessionParams) -> str:
        # Activity 1: create session from blueprint
        run_id = await workflow.execute_activity(
            "create_scheduled_session", params, ...
        )
        # Activity 2: stage inputs
        await workflow.execute_activity(
            "stage_scheduled_inputs",
            StageScheduledInputsParams(run_id=run_id, inputs=params.inputs, text=params.text),
            ...
        )
        # Child workflow: delegate to existing SessionWorkflow
        await workflow.execute_child_workflow(
            SessionWorkflow.run, SessionWorkflowParams(...), ...
        )
        return run_id
```

**Key design**: Reuses the existing `SessionWorkflow` as a child workflow. The scheduled workflow only adds the session creation + input staging orchestration on top. This means zero duplication of the begin → execute → complete/fail lifecycle.

### 3.6 Adapter — `ScheduleActivities`

**Purpose**: Activity implementations for `ScheduledSessionWorkflow`.

```python
class ScheduleActivities:
    def __init__(
        self,
        session_service: SessionService,
        input_projector: SessionInputProjector,
        session_manager: UserSessionManager,
    ): ...

    @activity.defn(name="create_scheduled_session")
    def create_scheduled_session(self, params: ScheduledSessionParams) -> str:
        identity = params.identity
        metadata = SessionMeta(source="schedule", schedule_id=params.prompt_id)
        return self.session_service.create(
            identity=identity,
            blueprint_id=params.blueprint_id,
            metadata=metadata,
        )

    @activity.defn(name="stage_scheduled_inputs")
    def stage_scheduled_inputs(self, params: StageScheduledInputsParams) -> None:
        record = self.session_manager.get_record(params.run_id)
        inputs = {**params.inputs}
        if params.text:
            inputs["user_prompt"] = params.text
        self.input_projector.apply(record, inputs)
```

**Dependencies**: `SessionService`, `SessionInputProjector`, `UserSessionManager`

### 3.7 Adapter — `MongoPromptRepository`

**Purpose**: MongoDB implementation of `PromptRepository`.

Follows the same pattern as `MongoBlueprintRepository`:
- Constructor takes `db_name`, `coll_name`
- Uses `get_mongo_url()` for connection
- Creates indices on `prompt_id` (unique), `identity.type + identity.id`, `blueprint_id`
- Serializes/deserializes `Prompt` via `model_dump(mode="json")` / `Prompt(**doc)`

**Collection**: `prompts`

### 3.8 Adapter — Flask Endpoints

**Purpose**: REST API for prompt/schedule management. Follows existing RPC-style conventions.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| POST | `/api/prompts/prompt.create` | Create prompt (with optional schedule) |
| GET | `/api/prompts/prompt.list` | List prompts for identity |
| GET | `/api/prompts/prompt.get` | Get single prompt |
| POST | `/api/prompts/prompt.schedule.pause` | Pause schedule |
| POST | `/api/prompts/prompt.schedule.resume` | Resume schedule |
| DELETE | `/api/prompts/prompt.delete` | Delete prompt + schedule |
| POST | `/api/prompts/prompt.schedule.trigger` | Manual one-off trigger |

All endpoints use `@with_require_identity_authorization` and access `current_app.container.prompt_service`.

### 3.9 Container Wiring

```python
# In AppContainer.__init__():

# Prompt repository
self.prompt_repo = MongoPromptRepository(
    db_name=cfg.mongo_db,
    coll_name=cfg.prompts_coll,
)

# Schedule adapter (conditional on Temporal)
schedule_adapter = self._create_schedule_adapter(cfg.engine_name)

# Prompt service
self.prompt_service = PromptService(
    prompt_repo=self.prompt_repo,
    schedule_port=schedule_adapter,
    blueprint_service=self.blueprint_service,
)

# --- static method ---
@staticmethod
def _create_schedule_adapter(engine_name: str):
    if engine_name == "temporal":
        from outbound.temporal.schedule_adapter import TemporalScheduleAdapter
        return TemporalScheduleAdapter()
    return None
```

### 3.10 Worker Registration

```python
# In worker.py — add to run_worker():

schedule_activities = ScheduleActivities(
    session_service=container.session_service,
    input_projector=container.input_projector,
    session_manager=container.session_manager,
)

# Add to Worker() constructor:
workflows=[..., ScheduledSessionWorkflow],
activities=[
    ...,
    schedule_activities.create_scheduled_session,
    schedule_activities.stage_scheduled_inputs,
],
```

### 3.11 Temporal DTO Models

```python
# In temporal/models.py:

class ScheduledSessionParams(BaseModel):
    """Input to ScheduledSessionWorkflow — one per schedule tick."""
    prompt_id: str
    blueprint_id: str
    identity: Identity
    text: str = ""
    inputs: Dict[str, Any] = Field(default_factory=dict)

class StageScheduledInputsParams(BaseModel):
    """Input to the stage_scheduled_inputs activity."""
    run_id: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    text: str = ""
```

---

## 4. Data Flow

### Schedule Creation

```
UI → POST /api/prompts/prompt.create
  → Flask endpoint (parse request, resolve identity)
    → PromptService.create(identity, blueprint_id, text, inputs, schedule)
      → BlueprintService.exists(blueprint_id) → validates blueprint
      → PromptRepository.save(prompt) → Mongo insert
      → SchedulePort.create_schedule(prompt) → Temporal Schedules API
        → Creates Temporal Schedule targeting ScheduledSessionWorkflow
      → PromptRepository.update(prompt) → stores temporal_schedule_id
    ← returns Prompt
  ← returns JSON response with prompt_id
```

### Schedule Tick (Recurring Execution)

```
Temporal Scheduler tick
  → Starts ScheduledSessionWorkflow(ScheduledSessionParams)
    → Activity: create_scheduled_session
      → SessionService.create(identity, blueprint_id, metadata={source: "schedule", schedule_id})
      ← run_id
    → Activity: stage_scheduled_inputs
      → SessionInputProjector.apply(record, inputs)
      ← (persisted, status = QUEUED)
    → Child workflow: SessionWorkflow.run(SessionWorkflowParams)
      → (existing lifecycle: begin → execute_graph → complete/fail)
    ← run_id
```

### Pause / Resume / Delete

```
UI → POST /api/prompts/prompt.schedule.pause
  → PromptService.pause(prompt_id, identity)
    → PromptRepository.load(prompt_id) → access check
    → SchedulePort.pause(temporal_schedule_id) → Temporal API
    → prompt.schedule_status = PAUSED
    → PromptRepository.update(prompt)
```

---

## 5. Risk & Reliability

### 5a. Edge Cases & Failure Modes

| Risk / Edge Case | Mitigation |
| :--- | :--- |
| Blueprint deleted while schedule is active | `ScheduledSessionWorkflow` resolves blueprint at execution time. If missing, the `create_scheduled_session` activity fails, Temporal retries per retry policy, and the session is marked FAILED. The schedule continues ticking (next tick may succeed if blueprint is recreated). Consider adding monitoring/alerting. |
| Schedule creation succeeds in Temporal but Mongo update fails | `prompt.temporal_schedule_id` will be null. On retry, `create_schedule` is idempotent if we use `prompt_id` as the Temporal schedule ID (dedup by ID). |
| Long-running session overlaps next tick | Default `SKIP` overlap policy prevents pileup. Configurable per prompt. |
| Cron expression with sub-minute granularity | Temporal Schedules support minute-level minimum. Validate at `ScheduleDefinition` level. |
| User deletes prompt but Temporal schedule deletion fails | Wrap in try/catch, mark prompt as `DELETED` in Mongo regardless. Add a background cleanup task or log warning for manual intervention. |
| Identity/team changes while schedule is active | Schedule stores full `Identity` snapshot. Sessions are created under the original identity. No drift — behavior matches "the user who created the schedule". |
| Worker restart mid-tick | Temporal's durable execution guarantees the workflow resumes. No special handling needed. |

### 5b. External Dependency Failure Modes

| Dependency | Failure Scenario (401 / 503 / timeout) | Behavior (silent / noisy) | Degradation Path |
| :--- | :--- | :--- | :--- |
| Temporal Server | 503 / timeout during schedule creation | Noisy — API returns 500 | Manual prompt still works (no schedule). Retry via UI. |
| Temporal Server | Unreachable during schedule tick | Silent — Temporal handles retries internally | Schedule fires when Temporal recovers (backfill policy). |
| MongoDB | Unreachable during prompt save | Noisy — API returns 500 | Standard retry from UI. No partial state (save is atomic). |
| MongoDB | Unreachable during scheduled session creation | Noisy — activity fails, Temporal retries | Session creation retried automatically per retry policy. |

### 5c. Local Development & Partial-Access Deployment

| Dependency | Local Dev Strategy | Deployment Without This Dependency |
| :--- | :--- | :--- |
| Temporal Server | Local Temporal dev server (`temporal server start-dev`) — same as existing setup | `schedule_port = None` when `engine_name != "temporal"`. `PromptService` still works for CRUD (no scheduling). API returns 400 on schedule operations. |
| MongoDB | Local MongoDB container (existing) | No fallback — required for all data persistence (same as today). |

### 5d. AI-Specific Risks

*Not applicable — this feature does not involve LLM / AI components directly. The scheduled sessions execute existing blueprints which may contain LLM nodes, but those risks are handled by the existing session execution pipeline.*

---

## 6. Open Questions

- [ ] **Prompt vs PromptShortcut relationship**: Should existing `PromptShortcutItem` entries be convertible to `Prompt` instances? Or are they separate concepts? (Current proposal: separate — `PromptShortcutItem` is a UI convenience on a blueprint; `Prompt` is a first-class executable entity.)
- [ ] **Maximum schedules per user/blueprint**: Should we enforce a limit on how many active schedules a user can create? (Suggest: configurable via `AppConfig`, default 10.)
- [ ] **Schedule history / audit log**: Should completed schedule ticks be queryable beyond the session list? (Suggest: defer — sessions already have `metadata.source = "schedule"` for filtering.)
- [ ] **Backfill policy**: When a schedule is paused and then resumed, should missed ticks be backfilled? (Suggest: no backfill by default — Temporal supports this but it could cause a burst of sessions.)
- [ ] **Blueprint-level vs prompt-level scheduling**: The proposal ties schedules to prompts (which reference blueprints). An alternative is scheduling at the blueprint level directly. Which is preferred? (Current proposal: prompt-level gives more flexibility — same blueprint, different inputs/prompts on different schedules.)
- [ ] **UI dropdown options**: Confirm the exact UI flow — is "Scheduled" one of several execution modes in a dropdown (alongside "Manual", "On-demand")?

---

## 7. Reviewer Feedback

<!-- This section is populated by the Design Reviewer (Phase 2). Do not fill manually. -->

### Verdict: **[PENDING]**

### Review of Proposed Implementation (from Ticket Description)

The implementation suggestions from the ticket are **largely sound** but require the following adjustments to align with the actual codebase patterns:

**Accepted as-is:**
- Temporal Schedules API approach (native, crash-safe, no extra infra)
- Two-phase session creation pattern (create → stage → execute as child workflow)
- `source="schedule"` metadata tagging
- Overlap policy defaulting to SKIP
- TemporalScheduleAdapter wrapping the Schedule API
- Flask endpoint set (POST create, GET list, POST pause/resume, DELETE, POST trigger)
- Container wiring pattern (conditional on `engine_name == "temporal"`)

**Adjusted:**

| Ticket Proposal | Adjustment | Reason |
| :--- | :--- | :--- |
| Standalone `ScheduleDefinition` model as the primary aggregate | **Merged into `Prompt` model** — `ScheduleDefinition` becomes a value object on `Prompt` | The user requested a `Prompt` model class with a "scheduled" option. This is more cohesive: a prompt *is* the content being scheduled. |
| File at `lib/mas/schedules/models.py` | **Changed to `lib/mas/prompts/models.py`** | Aligns with the user's request for a "prompts" model. The domain concept is "prompt" (with optional schedule), not "schedule" (with attached prompt). |
| `ScheduleRepository` + `MongoScheduleRepository` | **Changed to `PromptRepository` + `MongoPromptRepository`** | Repository owns the aggregate root (`Prompt`), not the value object (`ScheduleDefinition`). |
| `ScheduleService` | **Changed to `PromptService`** | Service named after the aggregate it manages. |
| Endpoint prefix `/api/schedule.*` | **Changed to `/api/prompts/prompt.*`** | Follows existing convention: resource group as URL prefix, RPC-style action. |
| `ScheduledSessionWorkflow` activities call `SessionService.create` directly | Activities use `SessionService.create` + `SessionInputProjector.apply` **as separate activities** | Matches the two-phase invariant (staging is separate from creation). Keeps activity granularity fine for retry isolation. |
| Routes at `adapters/inbound/flask/routes/` | **Changed to `adapters/inbound/flask/endpoints/`** | Actual codebase uses `endpoints/`, not `routes/`. |

**Rejected:**

| Ticket Proposal | Reason |
| :--- | :--- |
| `ScheduleStatus` as a separate enum with `deleted` state | Deletion is a hard delete (remove from Mongo + delete Temporal schedule). No need for a soft-delete status. `ACTIVE` and `PAUSED` suffice. *Note: ADR keeps `DELETED` as a fallback for the edge case where Temporal deletion fails but Mongo is already updated.* |

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
