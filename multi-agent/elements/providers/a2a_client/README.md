# A2A Client

A clean, extensible client for the [A2A (Agent-to-Agent) Protocol](https://a2a-protocol.org/latest/specification/).

## Package Structure

```
a2a_client/
├── __init__.py                 # Public API exports
├── identifiers.py              # Identifier.TYPE = "a2a_agent", META
├── config.py                   # A2AProviderConfig (Pydantic)
├── a2a_provider_factory.py     # Factory pattern for creation
│
├── provider.py                 # A2AProvider - HIGH LEVEL (ChatMessage API)
├── client.py                   # A2AClient - LOW LEVEL (SDK wrapper)
├── result.py                   # A2AResult - Unified response wrapper
├── converter.py                # A2AConverter - ChatMessage <-> A2A
│
└── handlers/
    ├── __init__.py             # Exports BaseHandler + handlers
    ├── base_handler.py         # BaseHandler ABC + auto-registration
    └── handlers.py             # 4 concrete handlers
```

## Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              YOUR APPLICATION                                │
│                          (uses ChatMessage)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              A2AProvider                                     │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  PUBLIC API:                                                          │  │
│  │  • send_message(ChatMessage) → (ChatMessage, metadata)                │  │
│  │  • stream_message(ChatMessage) → Iterator[ChatMessage]                │  │
│  │  • cancel_task(task_id) → (ChatMessage, metadata)                     │  │
│  │  • send_message_sync() / stream_message_sync()                        │  │
│  │  • skills, agent_card                                                 │  │
│  │                                                                       │  │
│  │  RESPONSIBILITIES:                                                    │  │
│  │  • Polling for completion                                             │  │
│  │  • Multi-turn conversations (task_id, context_id)                     │  │
│  │  • Sync/async bridging                                                │  │
│  │  • Error handling (raise_on_error flag)                               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│                              A2AConverter                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  OUTBOUND: ChatMessage → A2A Message                                  │  │
│  │  • to_a2a_message(ChatMessage, task_id, context_id, part_metadata)    │  │
│  │                                                                       │  │
│  │  INBOUND: A2AResult → ChatMessage                                     │  │
│  │  • to_chat_message(A2AResult) → ConversionResult                      │  │
│  │  • Extracts text from Parts (TextPart, FilePart, DataPart)            │  │
│  │  • Formats errors for display                                         │  │
│  │  • Fallback text for status-only events                               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               A2AClient                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  API (uses SDK types):                                                │  │
│  │  • send(Message) → A2AResult                                          │  │
│  │  • stream(Message) → AsyncIterator[A2AResult]                         │  │
│  │  • get_task(id) → A2AResult                                           │  │
│  │  • cancel_task(id) → A2AResult                                        │  │
│  │  • agent_card, skills                                                 │  │
│  │  • supports_streaming(), supports_push_notifications()                │  │
│  │                                                                       │  │
│  │  LIFECYCLE:                                                           │  │
│  │  • async with A2AClient(url) as client:                               │  │
│  │  • Fetches AgentCard on connect                                       │  │
│  │  • Manages httpx.AsyncClient                                          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│                              BaseHandler                                     │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  DISPATCH:                                                            │  │
│  │  • BaseHandler.handle(sdk_obj) → A2AResult                            │  │
│  │                                                                       │  │
│  │  REGISTRY (auto-populated via __init_subclass__):                     │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Task                    → TaskHandler                          │  │  │
│  │  │  Message                 → MessageHandler                       │  │  │
│  │  │  TaskStatusUpdateEvent   → StatusEventHandler                   │  │  │
│  │  │  TaskArtifactUpdateEvent → ArtifactEventHandler                 │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            A2AResult (Pydantic)                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  UNIFIED WRAPPER for all SDK response types                           │  │
│  │                                                                       │  │
│  │  kind: ResultKind (TASK | MESSAGE | STATUS_EVENT | ARTIFACT_EVENT |   │  │
│  │                    ERROR)                                             │  │
│  │                                                                       │  │
│  │  SDK Objects (one set per kind):                                      │  │
│  │  • task: Task                                                         │  │
│  │  • message: Message                                                   │  │
│  │  • status_event: TaskStatusUpdateEvent                                │  │
│  │  • artifact_event: TaskArtifactUpdateEvent                            │  │
│  │  • error: JSONRPCError                                                │  │
│  │                                                                       │  │
│  │  Properties:                                                          │  │
│  │  • state → TaskState                                                  │  │
│  │  • is_terminal, is_complete, is_success, is_failure                   │  │
│  │  • is_canceled, is_working, is_submitted                              │  │
│  │  • requires_input, requires_auth                                      │  │
│  │  • artifacts, is_append, is_last_chunk                                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Official A2A SDK (a2a)                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  a2a.client: A2AClient, A2ACardResolver                               │  │
│  │  a2a.types: Task, Message, Part, Artifact, TaskState, etc.            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Remote A2A Agent                                   │
│                        (JSON-RPC over HTTP/SSE)                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Send Message Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  ChatMessage │     │ A2A Message  │     │  SDK sends   │     │ Remote Agent │
│  (your type) │────►│ (SDK type)   │────►│  JSON-RPC    │────►│  processes   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │                    │
       │              to_a2a_message()      client.send()         HTTP POST
       │                                                              │
       ▼                                                              ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  ChatMessage │◄────│  A2AResult   │◄────│BaseHandler   │◄────│ Task or     │
│  + metadata  │     │  (unified)   │     │.handle()     │     │ Message     │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │                    │
       │              to_chat_message()    type dispatch         SDK parses
```

## Streaming Flow

```
client.stream(message)
        │
        ▼
   ┌────────────────────────────────────────────────────┐
   │              SSE Stream from Agent                  │
   │                                                     │
   │  chunk 1: TaskArtifactUpdateEvent (text chunk)     │
   │  chunk 2: TaskArtifactUpdateEvent (text chunk)     │
   │  chunk 3: TaskStatusUpdateEvent (working)          │
   │  chunk 4: TaskArtifactUpdateEvent (text chunk)     │
   │  chunk 5: TaskStatusUpdateEvent (completed, final) │
   │  chunk 6: Task (full result)                       │
   └────────────────────────────────────────────────────┘
        │
        ▼ (each chunk)
   ┌────────────────────────────────────────────────────┐
   │  BaseHandler.handle(chunk.root.result)             │
   │       │                                            │
   │       ├─► TaskArtifactUpdateEvent → ArtifactHandler│
   │       ├─► TaskStatusUpdateEvent → StatusHandler    │
   │       └─► Task → TaskHandler                       │
   │                                                    │
   │  Returns: A2AResult                                │
   └────────────────────────────────────────────────────┘
        │
        ▼
   ┌────────────────────────────────────────────────────┐
   │  converter.to_chat_message(result)                 │
   │       │                                            │
   │       └─► ChatMessage (yielded to caller)          │
   └────────────────────────────────────────────────────┘
```

## TaskState State Machine

```
                              ┌─────────────┐
                              │  submitted  │
                              └──────┬──────┘
                                     │
                                     ▼
                              ┌─────────────┐
                   ┌──────────│   working   │──────────┐
                   │          └──────┬──────┘          │
                   │                 │                 │
                   ▼                 ▼                 ▼
            ┌───────────┐    ┌─────────────┐   ┌──────────────┐
            │  failed   │    │  completed  │   │input-required│
            └───────────┘    └─────────────┘   └──────────────┘
                   │                                   │
                   │                                   │
                   ▼                                   ▼
            ┌───────────┐                      ┌──────────────┐
            │ rejected  │                      │auth-required │
            └───────────┘                      └──────────────┘
                   │
                   ▼
            ┌───────────┐
            │ canceled  │
            └───────────┘

    ┌────────────────────────────────────────────────────────┐
    │ TERMINAL STATES: completed, failed, canceled, rejected │
    │ NON-TERMINAL: submitted, working, input/auth-required  │
    └────────────────────────────────────────────────────────┘
```

## Handler Auto-Registration

```python
# When Python loads handlers.py:

class TaskHandler(BaseHandler):    # Class definition starts
    handled_types = {Task}          # Class attribute set
    ...                             # Class definition ends
         │
         ▼
BaseHandler.__init_subclass__(TaskHandler)  # Python calls this automatically
         │
         ▼
BaseHandler._registry[Task] = TaskHandler   # Handler registered!


# Final registry state:
BaseHandler._registry = {
    Task                    : TaskHandler,
    Message                 : MessageHandler,
    TaskStatusUpdateEvent   : StatusEventHandler,
    TaskArtifactUpdateEvent : ArtifactEventHandler,
}
```

## Quick Usage

### High-Level API (Recommended)

```python
from elements.providers.a2a_client import A2AProvider
from elements.llms.common.chat.message import ChatMessage, Role

# Create provider
provider = A2AProvider.create_sync("http://localhost:10000")

# Send message
response, metadata = provider.send_message_sync(
    ChatMessage(role=Role.USER, content="Hello!")
)
print(response.content)

# Stream message
for chunk in provider.stream_message_sync(message):
    print(chunk.content, end="", flush=True)

# Cancel task
response, metadata = provider.cancel_task_sync(task_id)
```

### Low-Level API

```python
from elements.providers.a2a_client import A2AClient
from a2a.types import Message, TextPart, Part, Role

async with A2AClient("http://localhost:10000") as client:
    msg = Message(
        role=Role.user,
        parts=[Part(root=TextPart(text="Hello!"))],
        message_id="123",
    )
    result = await client.send(msg)
    print(result.state, result.artifacts)
```

## A2AResult Properties

| Property | Description |
|----------|-------------|
| `kind` | ResultKind enum (TASK, MESSAGE, STATUS_EVENT, ARTIFACT_EVENT, ERROR) |
| `state` | TaskState from task or status_event |
| `is_terminal` | True if completed/failed/canceled/rejected |
| `is_complete` | True if work is done |
| `is_success` | True if state == completed |
| `is_failure` | True if failed/rejected or error |
| `is_canceled` | True if canceled |
| `requires_input` | True if input-required state |
| `requires_auth` | True if auth-required state |
| `artifacts` | List of artifacts from task/event |
| `is_streaming` | True if from streaming endpoint |

## Configuration

```python
from elements.providers.a2a_client import A2AProviderConfig

config = A2AProviderConfig(
    base_url="http://localhost:10000",
    headers={"Authorization": "Bearer token"},  # Optional
    agent_card=None,  # Optional, fetched if not provided
)
```

## Key Classes

| Class | File | Purpose |
|-------|------|---------|
| `A2AProvider` | provider.py | High-level API with ChatMessage |
| `A2AClient` | client.py | Low-level SDK wrapper |
| `A2AResult` | result.py | Unified response wrapper |
| `A2AConverter` | converter.py | ChatMessage <-> A2A conversion |
| `BaseHandler` | handlers/base_handler.py | Abstract handler + registry |
| `TaskHandler` | handlers/handlers.py | Handles Task responses |
| `MessageHandler` | handlers/handlers.py | Handles Message responses |
| `StatusEventHandler` | handlers/handlers.py | Handles status events |
| `ArtifactEventHandler` | handlers/handlers.py | Handles artifact events |
| `A2AProviderConfig` | config.py | Configuration model |
| `A2AProviderFactory` | a2a_provider_factory.py | Factory for creation |
