# Refactor: Move Cancellation from Domain to Adapter Layer

## The Problem

Cancellation logic was spread across 8 files, spanning both domain and adapter layers. Domain-level code (nodes, agent iterator, IEM packet processing) was polling an `is_cancelled()` check each iteration. This check was injected from the Temporal activity via a `threading.Event`, threading a `cancel_check` callable all the way down through the adapter → executor → node → agent iterator chain.

This violated several principles:

- **Single Responsibility**: Domain code (agent iteration, node execution, packet processing) should not be responsible for checking cancellation. Its job is to run business logic.
- **Dependency direction**: The domain layer was aware of a concurrency primitive (`Callable[[], bool]` backed by `threading.Event.is_set`) that originated from the adapter layer.
- **Portability**: The cancellation mechanism was tightly coupled to the Temporal activity's threading model. If we swap the execution engine, the domain code's cancellation checks become meaningless.

## The Insight

Two existing adapter-layer mechanisms already handle cancellation without any domain involvement:

### 1. Temporal Heartbeat (detection)

The `execute_graph_node` activity sends `activity.heartbeat("running")` every 5 seconds while the node executes in a thread. This heartbeat call serves dual duty — it keeps the activity alive AND receives the cancellation signal. When the workflow is cancelled, the very next `activity.heartbeat()` raises `CancelledError`. The worker detects the cancellation and acts on it immediately.

### 2. Redis Channel Silent Drop (enforcement)

`RedisSessionChannel.emit()` silently returns (no-op) when the channel is closed (`self._closed` is `True`). Once the `CancelledError` handler calls `channel.close()`, all subsequent `emit()` calls from the still-running agent thread are silently discarded. The agent's output goes nowhere — the client sees instant cancellation.

The in-memory `_closed` flag is sufficient because the activity's `CancelledError` handler closes the **same** channel instance the agent thread is using. Python's GIL guarantees the boolean write is visible immediately across threads. There is no need for a Redis-level cancel key — that was a redundant cross-process signaling mechanism that added an `EXISTS` round-trip on every `emit()` call during normal operation. It has been removed.

### What happens to the agent thread?

The agent thread is not forcefully killed — Python threads cannot be interrupted mid-syscall. It finishes its current LLM call or tool execution naturally. But since the channel is closed, all output is silently dropped. The thread returns to the pool when it completes (within a 10-second grace period, or whenever the in-flight call finishes). This is an acceptable trade-off: a brief tail of wasted compute in exchange for clean architecture.

## The Cancellation Flow (after refactoring)

```
User clicks Cancel
  → POST /session.cancel
    → BackgroundSessionEngine.cancel(handle)
      → Temporal wf_handle.cancel()

In the workflow (SessionWorkflow):
  → execute_graph() detects Temporal cancellation
    → Raises SessionCancelledException (adapter translates native signal)
    → BackgroundSessionRunner catches it → calls ops.cancel()
      → cancel_session activity → BackgroundLifecycleHandler.cancel()
        → SessionLifecycle.cancel(record) — marks CANCELLED, stamps metadata
        → channel.close(cancelled=True) — sends CLOSE signal to Redis stream

Meanwhile, in the running activity (execute_graph_node):
  → activity.heartbeat() raises CancelledError (next heartbeat cycle, ≤5s)
    → CancelledError propagates to workflow → SessionCancelledException
      → runner calls ops.cancel() → lifecycle handler closes channel
        → Sets _closed = True (in-memory, instant)
    → Grace period: waits up to 10s for thread to finish
    → Re-raises CancelledError → activity reports as cancelled to Temporal

Agent thread (still running in background):
  → Calls channel.emit(data)
    → emit() checks self._closed → True → silently returns
  → Eventually finishes naturally → thread returns to pool
```

## What Changed

### Deleted

| File | What |
|------|------|
| `lib/mas/elements/nodes/common/capabilities/cancellation_capable.py` | Entire `CancellationCapableMixin` — the `set_cancel_check()` / `is_cancelled()` mixin that was mixed into `BaseNode` |

### Domain Layer (cancellation awareness removed)

| File | Change |
|------|--------|
| `lib/mas/elements/nodes/common/base_node.py` | Removed `CancellationCapableMixin` from inheritance. Removed `is_cancelled()` guard in `__call__` |
| `lib/mas/elements/nodes/common/agent/execution/iterator.py` | Removed `is_cancelled` parameter from `__init__`. Removed two `is_cancelled()` check sites (pre-think and pre-tool-execution) |
| `lib/mas/elements/nodes/common/capabilities/agent_capable.py` | Removed `is_cancelled` from `create_iterator()`, `run_agent()`, and `stream_agent()` |
| `lib/mas/elements/nodes/common/capabilities/iem_capable.py` | Removed `is_cancelled()` check from `process_packets()` loop |
| `lib/mas/core/contracts.py` | Removed `SupportsCancellation` protocol |
| `lib/mas/engine/distributed/node_executor.py` | Removed `cancel_check` parameter and `set_cancel_check` injection |

### Adapter Layer (heartbeat extracted, Redis cancel key removed)

| File | Change |
|------|--------|
| `adapters/inbound/temporal/activities/heartbeat.py` | **New file.** `@heartbeat` decorator. Decorates sync activity functions to run in a thread with periodic heartbeats and graceful shutdown on cancel |
| `adapters/inbound/temporal/activities/graph_node_activities.py` | Simplified — `execute_node` is decorated with `@heartbeat`. Removed `threading.Event`, `cancel_event`, inline heartbeat loop, grace period methods, and explicit thread pool management |
| `adapters/outbound/channels/redis/channel.py` | Removed Redis cancel key mechanism from `__init__`, `emit()`, and `close()`. The in-memory `_closed` flag is sufficient — no need for a Redis `EXISTS` round-trip on every emit |
| `adapters/outbound/channels/redis/constants.py` | Removed `CANCELLED_PREFIX` and `CANCEL_FLAG_TTL` constants |

### Port (contract clarified)

| File | Change |
|------|--------|
| `lib/mas/core/channels/protocols.py` | Added docstring to `SessionChannel.emit()` documenting the silent-drop contract: "No-op if the channel has been closed or cancelled. Implementations must not raise." |

## What Was NOT Changed

- **`LocalSessionChannel.emit()`** — already silently drops on closed. No changes needed.
- **`ChatMessage.is_cancelled: bool`** — this is a UI metadata field (tells the frontend to show a cancellation notice), not domain cancellation logic.
- **`lifecycle.py` setting `is_cancelled=True` on messages** — same, UI metadata.
- **`cancel_session` activity flow** — stays as-is.
- **Temporal workflow cancel propagation** — stays as-is.

## Net Result

- **11 files changed**, 1 file deleted, 1 file created
- **~100 lines removed** from domain and adapter code
- **~80 lines added** in one adapter-layer module (`heartbeat.py`)
- Domain layer has zero knowledge of cancellation
- Redis channel has zero cancel-key overhead — `emit()` is a simple `_closed` check + `XADD`
- Cancellation behavior is identical from the user's perspective
