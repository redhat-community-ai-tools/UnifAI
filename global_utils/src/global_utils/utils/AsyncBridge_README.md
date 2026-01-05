# AsyncBridge

**Safe sync→async execution bridge for Python applications.**

AsyncBridge provides a centralized, thread-safe way to run async code from synchronous contexts without causing deadlocks or event loop conflicts.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Execution Flows](#execution-flows)
- [Design Principles](#design-principles)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)

---

## Overview

### The Problem

Python's async/await pattern is powerful but creates a fundamental barrier: you cannot call `async` functions directly from synchronous code. Common solutions like `asyncio.run()` fail when an event loop is already running, and `loop.run_until_complete()` can cause deadlocks.

### The Solution

AsyncBridge uses **anyio's BlockingPortal** to safely bridge the sync→async boundary:

```
┌─────────────────────┐         ┌─────────────────────┐
│   SYNC CONTEXT      │         │   ASYNC CONTEXT     │
│   (Main Thread)     │         │  (Background Thread)│
│                     │         │                     │
│  bridge.run(coro)───┼────────>│  await coro         │
│                     │         │                     │
│  result <───────────┼─────────│  return result      │
└─────────────────────┘         └─────────────────────┘
```

### Key Features

- **Singleton Pattern**: Process-wide shared portal for efficiency
- **Thread-Safe**: All operations protected by locks
- **Deadlock Prevention**: Detects unsafe execution contexts
- **Timeout Support**: Configurable timeouts with anyio integration
- **Concurrent Execution**: Run multiple awaitables in parallel
- **Real-Time Streaming**: Iterate over async generators synchronously
- **API Compatibility**: Multiple fallback strategies for different anyio versions

---

## Quick Start

### Basic Usage

```python
from global_utils.utils.async_bridge import get_async_bridge

# Run a single async function
async def fetch_data():
    await asyncio.sleep(1)
    return {"status": "ok"}

with get_async_bridge() as bridge:
    result = bridge.run(fetch_data())
    print(result)  # {"status": "ok"}
```

### Convenience Function

```python
from global_utils.utils.util import run_async

result = run_async(fetch_data())
```

### Run Multiple Concurrently

```python
with get_async_bridge() as bridge:
    results = bridge.run_many([
        fetch_user(1),
        fetch_user(2),
        fetch_user(3),
    ])
    # All three run concurrently, results in order
```

### Stream Async Iterator

```python
async def stream_tokens():
    for token in ["Hello", " ", "World"]:
        await asyncio.sleep(0.1)
        yield token

with get_async_bridge() as bridge:
    for token in bridge.iterate(stream_tokens()):
        print(token, end='', flush=True)  # Prints in real-time
```

---

## Architecture

### ASCII Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SYNC CONTEXT (Main Thread)                         │
│                                                                                 │
│   ┌────────────────┐      ┌────────────────────────────────────────────────┐   │
│   │ Your Sync Code │─────>│              AsyncBridge (Singleton)            │   │
│   │   validates()  │      │  ┌────────────────────────────────────────┐    │   │
│   │   create_sync()│      │  │     BlockingPortalAsyncRunner          │    │   │
│   │   run_sync()   │      │  │                                        │    │   │
│   └────────────────┘      │  │  ┌──────────────────────────────────┐  │    │   │
│                           │  │  │ ExecutionGuard                   │  │    │   │
│                           │  │  │ - Validates we're NOT in an      │  │    │   │
│                           │  │  │   event loop thread (deadlock!)  │  │    │   │
│                           │  │  └──────────────────────────────────┘  │    │   │
│                           │  │                                        │    │   │
│                           │  │  ┌──────────────────────────────────┐  │    │   │
│                           │  │  │ TimeoutManager                   │  │    │   │
│                           │  │  │ - Resolves timeouts              │  │    │   │
│                           │  │  │ - Applies anyio.fail_after()     │  │    │   │
│                           │  │  └──────────────────────────────────┘  │    │   │
│                           │  │                                        │    │   │
│                           │  │  ┌──────────────────────────────────┐  │    │   │
│                           │  │  │ ConcurrentExecutor               │  │    │   │
│                           │  │  │ - Runs many awaitables with      │  │    │   │
│                           │  │  │   semaphore-based concurrency    │  │    │   │
│                           │  │  └──────────────────────────────────┘  │    │   │
│                           │  │                                        │    │   │
│                           │  └────────────────────────────────────────┘    │   │
│                           │                      │                          │   │
│                           │                      ▼                          │   │
│                           │  ┌────────────────────────────────────────┐    │   │
│                           │  │    PortalLifecycleManager              │    │   │
│                           │  │    - Thread-safe with RLock            │    │   │
│                           │  │    - Reference counting for lifecycle  │    │   │
│                           │  │    - Multiple fallback strategies      │    │   │
│                           │  └──────────────────┬─────────────────────┘    │   │
│                           └─────────────────────┼──────────────────────────┘   │
│                                                 │                               │
└─────────────────────────────────────────────────┼───────────────────────────────┘
                                                  │
                              ┌───────────────────┴───────────────────┐
                              │    anyio BlockingPortal               │
                              │    (Context Manager)                  │
                              │                                       │
                              │  - Creates dedicated async thread     │
                              │  - Bridges sync→async boundary        │
                              │  - portal.call() / portal.start_task  │
                              └───────────────────┬───────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ASYNC CONTEXT (Background Thread)                        │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                        Event Loop (asyncio)                              │   │
│   │                                                                          │   │
│   │   ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────┐   │   │
│   │   │ awaitable 1   │  │ awaitable 2   │  │ async iterator (stream)   │   │   │
│   │   │ (your async   │  │ (MCP call)    │  │ async for item in ...     │   │   │
│   │   │  function)    │  │               │  │                           │   │   │
│   │   └───────────────┘  └───────────────┘  └───────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Class Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Class Hierarchy                                 │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─────────────────┐                                                   │
│  │   SingletonMeta │ ← Metaclass ensuring one instance per process     │
│  └────────┬────────┘                                                   │
│           │                                                            │
│           ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    AsyncBridge (Singleton)                       │  │
│  │  - Public API: run(), run_many(), iterate(), close()           │  │
│  │  - Context manager support: __enter__/__exit__                  │  │
│  │  - Delegates to BlockingPortalAsyncRunner (Composition)         │  │
│  └──────────────────────────────────┬──────────────────────────────┘  │
│                                     │ has-a                            │
│                                     ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │               BlockingPortalAsyncRunner                          │  │
│  │  - Implements AsyncRunner Protocol                               │  │
│  │  - Orchestrates components                                       │  │
│  │  - Template Method pattern for execution                         │  │
│  └───┬───────────────┬────────────────┬────────────────┬───────────┘  │
│      │               │                │                │               │
│      ▼               ▼                ▼                ▼               │
│  ┌─────────┐  ┌────────────┐  ┌───────────────┐  ┌──────────────┐     │
│  │Execution│  │  Timeout   │  │   Portal      │  │ Concurrent   │     │
│  │ Guard   │  │  Manager   │  │   Lifecycle   │  │  Executor    │     │
│  │         │  │            │  │   Manager     │  │              │     │
│  │ Prevent │  │ Handle     │  │               │  │ Run many     │     │
│  │deadlock │  │ timeouts   │  │ Thread-safe   │  │ awaitables   │     │
│  │detection│  │            │  │ portal mgmt   │  │ concurrently │     │
│  └─────────┘  └────────────┘  └───────────────┘  └──────────────┘     │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                     BridgeConfig (Immutable)                     │  │
│  │  - default_timeout: Optional[float]                             │  │
│  │  - max_concurrent: int = 100                                    │  │
│  │  - portal_backend: str = "asyncio"                              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## API Reference

### `AsyncBridge`

The main class providing sync→async execution.

#### `run(awaitable, timeout=None) -> Any`

Run a single awaitable from sync context.

```python
result = bridge.run(async_function(), timeout=30.0)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `awaitable` | `Awaitable[Any]` | The async function/coroutine to execute |
| `timeout` | `Optional[float]` | Timeout in seconds (None = no timeout) |

#### `run_many(awaitables, timeout=None, limit=None) -> list[Any]`

Run multiple awaitables concurrently.

```python
results = bridge.run_many([coro1(), coro2(), coro3()], limit=10)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `awaitables` | `Iterable[Awaitable[Any]]` | Collection of awaitables |
| `timeout` | `Optional[float]` | Timeout per awaitable |
| `limit` | `Optional[int]` | Max concurrent executions (default: 100) |

#### `iterate(async_iterator, timeout=None) -> Iterator[Any]`

Iterate over an async iterator with real-time streaming.

```python
for item in bridge.iterate(async_generator()):
    process(item)  # Items yielded as they arrive
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `async_iterator` | `AsyncIterator[Any]` | Async generator/iterator |
| `timeout` | `Optional[float]` | Timeout for entire iteration |

#### `close() -> None`

Release resources (decrements reference count).

#### `force_close() -> None`

Force close all resources (for application shutdown).

### `BridgeConfig`

Immutable configuration for the bridge.

```python
from global_utils.utils.async_bridge import BridgeConfig, AsyncBridge

config = BridgeConfig(
    default_timeout=30.0,    # Default timeout for all operations
    max_concurrent=50,       # Max concurrent awaitables in run_many
    portal_backend="asyncio" # Backend: "asyncio" or "trio"
)

bridge = AsyncBridge(config)
```

### Convenience Functions

```python
from global_utils.utils.async_bridge import (
    get_async_bridge,   # Get singleton instance
    run_async,          # Quick single execution
    run_many_async,     # Quick concurrent execution
)

# Singleton access
bridge = get_async_bridge()

# One-shot execution
result = run_async(some_coroutine())

# One-shot concurrent execution
results = run_many_async([coro1(), coro2()])
```

---

## Execution Flows

### Single Awaitable Execution

```
  Sync Code                    AsyncBridge                  Async Thread
      │                            │                             │
      │  bridge.run(awaitable)     │                             │
      ├───────────────────────────>│                             │
      │                            │                             │
      │                   ┌────────┴────────┐                    │
      │                   │ 1. ExecutionGuard                    │
      │                   │    validate_sync_execution()         │
      │                   │    - Check if in event loop thread   │
      │                   │    - Raise error if deadlock risk    │
      │                   └────────┬────────┘                    │
      │                            │                             │
      │                   ┌────────┴────────┐                    │
      │                   │ 2. PortalLifecycleManager            │
      │                   │    acquire_portal()                  │
      │                   │    - Lock (RLock)                    │
      │                   │    - Increment ref_count             │
      │                   │    - Create portal if needed         │
      │                   └────────┬────────┘                    │
      │                            │                             │
      │                   ┌────────┴────────┐                    │
      │                   │ 3. TimeoutManager                    │
      │                   │    resolve_timeout()                 │
      │                   └────────┬────────┘                    │
      │                            │                             │
      │                            │  portal.call(_runner)       │
      │                            ├────────────────────────────>│
      │                            │                             │
      │                            │        ┌────────────────────┤
      │                            │        │ 4. Execute in      │
      │                            │        │    async context   │
      │                            │        │    with timeout    │
      │                            │        └────────────────────┤
      │                            │                             │
      │                            │<────────────────────────────┤
      │                            │      result / exception     │
      │<───────────────────────────┤                             │
      │     return result          │                             │
```

### Real-Time Streaming

```
  Sync Code                    AsyncBridge                        Async Thread
      │                            │                                    │
      │  for item in bridge.iterate(async_gen):                         │
      ├───────────────────────────>│                                    │
      │                            │                                    │
      │                   ┌────────┴────────┐                           │
      │                   │ Setup:                                      │
      │                   │ - Create Queue()                            │
      │                   │ - Define _DONE, _ERROR sentinels            │
      │                   └────────┬────────┘                           │
      │                            │                                    │
      │                            │  portal.start_task_soon(_producer) │
      │                            ├───────────────────────────────────>│
      │                            │                                    │
      │                            │               ┌────────────────────┤
      │                            │               │ async for item     │
      │                            │               │   in async_gen:    │
      │                            │               │     queue.put(item)│
      │                            │               └─────────┬──────────┤
      │                            │                         │          │
      │   ┌────────────────────────┤                         │          │
      │   │ while True:            │                         │          │
      │   │   item = queue.get()   │<════════════════════════╡ item 1   │
      │   │   yield item ─────────>│                         │          │
      │<──┤ item 1                 │<════════════════════════╡ item 2   │
      │<──┤ item 2                 │<════════════════════════╡ _DONE    │
      │   └────────────────────────┤                         │          │
      │  (iteration complete)      │                         └──────────┤
```

### Portal Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PortalLifecycleManager                               │
│                                                                         │
│  Thread-Safe State Machine with Reference Counting                      │
│                                                                         │
│   ┌──────────┐    acquire()     ┌──────────────┐                       │
│   │   IDLE   │─────────────────>│   ACTIVE     │                       │
│   │ portal=  │                  │  portal!=    │                       │
│   │   None   │<─────────────────│   None       │                       │
│   │ ref=0    │   release()      │  ref>0       │                       │
│   └──────────┘   (when ref→0)   └──────────────┘                       │
│        │                                                                │
│        │ force_close()                                                  │
│        ▼                                                                │
│   ┌──────────┐                                                          │
│   │  CLOSED  │  ← RuntimeError on any acquire()                        │
│   └──────────┘                                                          │
│                                                                         │
│  Portal Creation Fallbacks:                                             │
│  ─────────────────────────                                              │
│  1. anyio.from_thread.start_blocking_portal()                          │
│  2. start_blocking_portal(backend="asyncio")                           │
│  3. anyio.start_blocking_portal() (legacy)                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Design Principles

### SOLID Principles Applied

| Principle | Implementation |
|-----------|---------------|
| **Single Responsibility** | Each class has one job: `ExecutionGuard` validates, `TimeoutManager` handles timeouts, etc. |
| **Open/Closed** | Easy to extend with new execution strategies without modifying existing code |
| **Liskov Substitution** | `AsyncRunner` protocol allows swapping implementations |
| **Interface Segregation** | Minimal `AsyncRunner` protocol with only essential methods |
| **Dependency Inversion** | Components depend on abstractions (protocols), not concretions |

### Key Design Decisions

1. **Composition over Inheritance**: `AsyncBridge` uses `BlockingPortalAsyncRunner` via composition to avoid metaclass conflicts with `SingletonMeta`

2. **Reference Counting**: Portal stays alive while in use, automatically cleans up when no references remain

3. **Graceful Degradation**: Multiple fallback strategies ensure compatibility across anyio versions

4. **Thread Safety**: All shared state protected by `RLock` (reentrant lock)

---

## Common Patterns

### Pattern 1: Validator with Network Calls

```python
from global_utils.utils.async_bridge import get_async_bridge

class MyValidator:
    def validate(self, config):
        """Sync validate method with internal async calls."""
        messages = []
        
        with get_async_bridge() as bridge:
            bridge.run(self._check_connection(config, messages))
        
        return self._build_report(messages)
    
    async def _check_connection(self, config, messages):
        """Async connection check."""
        async with aiohttp.ClientSession() as session:
            response = await session.get(config.url)
            # ... validation logic
```

### Pattern 2: Sync Wrapper for Async Provider

```python
class MyProvider:
    async def fetch_data(self) -> dict:
        """Async method."""
        return await self._client.get_data()
    
    def fetch_data_sync(self) -> dict:
        """Sync wrapper for async method."""
        with get_async_bridge() as bridge:
            return bridge.run(self.fetch_data())
```

### Pattern 3: Streaming Response

```python
class StreamingProvider:
    async def stream_response(self, prompt: str):
        """Async generator for streaming."""
        async for token in self._model.generate(prompt):
            yield token
    
    def stream_response_sync(self, prompt: str):
        """Sync streaming with real-time output."""
        with get_async_bridge() as bridge:
            for token in bridge.iterate(self.stream_response(prompt)):
                yield token
```

### Pattern 4: Batch Concurrent Execution

```python
async def fetch_user(user_id: int) -> User:
    async with aiohttp.ClientSession() as session:
        response = await session.get(f"/users/{user_id}")
        return User(**await response.json())

def fetch_all_users(user_ids: list[int]) -> list[User]:
    """Fetch multiple users concurrently."""
    with get_async_bridge() as bridge:
        return bridge.run_many(
            [fetch_user(uid) for uid in user_ids],
            timeout=30.0,
            limit=10  # Max 10 concurrent requests
        )
```

---

## Troubleshooting

### RuntimeError: "AsyncBridge.run() called from event loop thread"

**Cause**: You're trying to use `bridge.run()` from inside an async function.

**Solution**: Use `await` directly instead:

```python
# ❌ Wrong
async def my_async_function():
    with get_async_bridge() as bridge:
        result = bridge.run(other_async())  # RuntimeError!

# ✅ Correct
async def my_async_function():
    result = await other_async()
```

### RuntimeError: "AsyncBridge has been closed"

**Cause**: Attempting to use a bridge after `force_close()` was called.

**Solution**: Don't call `force_close()` until application shutdown.

### TimeoutError during iteration

**Cause**: The async iterator took longer than the specified timeout.

**Solution**: Increase timeout or handle the exception:

```python
try:
    with get_async_bridge() as bridge:
        for item in bridge.iterate(slow_generator(), timeout=60.0):
            process(item)
except TimeoutError:
    logger.warning("Iteration timed out")
```

### Portal Creation Fails

**Cause**: Incompatible anyio version or missing backend.

**Solution**: Ensure anyio is properly installed:

```bash
pip install anyio>=3.0.0
```

---

## File Location

```
global_utils/
└── src/
    └── global_utils/
        └── utils/
            ├── async_bridge.py      # Main implementation
            ├── singleton.py         # SingletonMeta metaclass
            └── AsyncBridge_README.md  # This file
```

---

## Dependencies

- `anyio` - Async library abstraction layer
- `asyncio` - Python's built-in async framework
- `threading` - Thread safety primitives

---

## Related Modules

- `global_utils.utils.util.run_async()` - Convenience wrapper
- `global_utils.utils.singleton.SingletonMeta` - Singleton pattern implementation

