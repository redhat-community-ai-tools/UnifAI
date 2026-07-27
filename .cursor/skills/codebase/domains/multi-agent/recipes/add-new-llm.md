---
name: add-new-llm
scope: Step-by-step recipe for adding a new LLM adapter to MAS
parent: ../SKILL.md
when_to_load: Creating a new LLM element under lib/mas/elements/llms/
---

# Add a New LLM

## Package Structure

Create the following tree under `lib/mas/elements/llms/<name>/`:

```
<name>/
├── identifiers.py              # TYPE constant + META dataclass
├── config.py                   # Pydantic config extending BaseLLMConfig
├── <name>.py                   # BaseLLM implementation
├── <name>_factory.py           # BaseFactory subclass
├── message_converter.py        # Domain ChatMessage ↔ SDK messages
├── tools_converter.py          # ToolDefinition ↔ SDK tool schema
├── spec/
│   ├── __init__.py             # re-exports the spec class
│   └── spec.py                 # BaseElementSpec subclass
└── (optional)
    ├── validator.py            # connection/key validation
    └── stream_aggregator.py    # streaming chunk assembly logic
```

---

## Step 1: Identifiers

```python
# identifiers.py
from dataclasses import dataclass

@dataclass(frozen=True)
class _Meta:
    name: str
    description: str
    tags: list

class Identifier:
    TYPE = "<name>"   # e.g., "openai", "google_genai", "anthropic"

META = _Meta(
    name="<Display Name>",
    description="<One-line description>",
    tags=["llm"],
)
```

---

## Step 2: Config

```python
# config.py
from typing import Literal
from mas.elements.llms.common.base_config import BaseLLMConfig
from mas.elements.llms.<name>.identifiers import Identifier

class <Name>Config(BaseLLMConfig):
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    # Add provider-specific fields:
    #   temperature: float = 0.7
    #   max_tokens: int = 4096
    #   extra: Dict[str, Any] = Field(default_factory=dict)
```

`BaseLLMConfig` provides: `model_name: str`, `api_key: str`, `base_url: HttpUrl`, `verify_ssl: bool`.

---

## Step 3: Message Converter

Stateless class with `to_*` / `from_*` static methods. This is the SDK boundary.

```python
# message_converter.py
from typing import List, Dict, Any
from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall

class <Name>MessageConverter:
    @staticmethod
    def to_<name>(messages: List[ChatMessage]) -> <SDKMessageType>:
        """Convert domain messages to SDK format."""
        # Map Role.SYSTEM → sdk system message
        # Map Role.USER → sdk user message
        # Map Role.ASSISTANT → sdk assistant message (include tool_calls)
        # Map Role.TOOL → sdk tool result message (include tool_call_id)

    @staticmethod
    def from_<name>(response: <SDKResponseType>) -> ChatMessage:
        """Convert SDK response to domain ChatMessage."""
        # Extract content, tool_calls, role
        # Return ChatMessage(role=Role.ASSISTANT, content=..., tool_calls=...)
```

### Domain message model reference

```python
class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class ToolCall(BaseModel):     # frozen
    name: str
    args: Dict[str, Any]
    tool_call_id: str

class ChatMessage(BaseModel):  # frozen
    role: Role
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    additional_kwargs: Optional[Dict[str, Any]] = None
    sender_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## Step 4: Tools Converter

```python
# tools_converter.py
from typing import List
from mas.elements.tools.common.tool_definition import ToolDefinition

class <Name>ToolsConverter:
    @staticmethod
    def to_<name>(tools: List[ToolDefinition]) -> List[<SDKToolType>]:
        """Convert domain ToolDefinition to SDK tool schema."""
        # ToolDefinition has: name, description, parameters (JSON Schema dict)
        # Map to SDK's tool format
```

### ToolDefinition reference

```python
class ToolDefinition(BaseModel):  # frozen
    name: str
    description: str = ""
    parameters: Dict[str, Any] = {"type": "object", "properties": {}}
```

---

## Step 5: LLM Implementation

```python
# <name>.py
import copy
from typing import List, Iterator, Union, Any
from mas.elements.llms.common.base_llm import BaseLLM
from mas.elements.llms.common.chat.message import ChatMessage
from mas.elements.tools.common.tool_definition import ToolDefinition

class <Name>LLM(BaseLLM):
    def __init__(self, *, model_name: str, api_key: str, base_url: str, **kwargs):
        # Initialize SDK client
        self._client = <SDKClient>(api_key=api_key, base_url=base_url)
        self._model = model_name
        self._tools: List[ToolDefinition] = []

    @property
    def name(self) -> str:
        return self._model

    def bind_tools(self, tools: List[ToolDefinition]) -> "<Name>LLM":
        """Return a NEW instance with tools bound. Original is unchanged."""
        clone = copy.copy(self)
        clone._tools = <Name>ToolsConverter.to_<name>(tools)
        return clone

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        sdk_messages = <Name>MessageConverter.to_<name>(messages)
        sdk_tools = <Name>ToolsConverter.to_<name>(self._tools) if self._tools else None
        response = self._client.create(messages=sdk_messages, tools=sdk_tools, ...)
        return <Name>MessageConverter.from_<name>(response)

    def stream(self, messages: List[ChatMessage], **call_params) -> Iterator[Union[str, ChatMessage]]:
        sdk_messages = <Name>MessageConverter.to_<name>(messages)
        sdk_tools = <Name>ToolsConverter.to_<name>(self._tools) if self._tools else None
        # Yield str tokens during generation
        # Yield final ChatMessage when tool calls are assembled or generation completes
        for chunk in self._client.create_stream(messages=sdk_messages, tools=sdk_tools, ...):
            if chunk.is_text:
                yield chunk.text
            # When complete, yield ChatMessage with full content + tool_calls
        yield <Name>MessageConverter.from_<name>(accumulated_response)
```

### Key contract rules

- `bind_tools()` is **immutable** — always return a new instance
- `stream()` yields `str` tokens during generation, then yields the final `ChatMessage`
- `chat()` returns a complete `ChatMessage` in one call
- SDK client initialization happens in `__init__`, not at call time
- SDK imports are expected in this file (Established Pattern)

---

## Step 6: Factory

```python
# <name>_factory.py
from mas.elements.common.base_factory import BaseFactory
from mas.elements.llms.<name>.config import <Name>Config
from mas.elements.llms.<name>.<name> import <Name>LLM
from mas.elements.llms.<name>.identifiers import Identifier

class <Name>Factory(BaseFactory[<Name>Config, <Name>LLM]):
    def accepts(self, cfg: <Name>Config, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: <Name>Config, **deps) -> <Name>LLM:
        return <Name>LLM(
            model_name=cfg.model_name,
            api_key=cfg.api_key,
            base_url=str(cfg.base_url),
            # provider-specific config fields...
        )
```

---

## Step 7: Spec

```python
# spec/spec.py
from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.elements.llms.<name>.identifiers import Identifier, META
from mas.elements.llms.<name>.config import <Name>Config
from mas.elements.llms.<name>.<name>_factory import <Name>Factory

class <Name>ElementSpec(BaseElementSpec):
    category = ResourceCategory.LLM
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = <Name>Config
    factory_cls = <Name>Factory
    tags = META.tags
    # Optional:
    # validator_cls = <Name>Validator
```

`spec/__init__.py`:
```python
from mas.elements.llms.<name>.spec.spec import <Name>ElementSpec
```

---

## Step 8: Register in Union Type

Add the config to the `LLMsSpec` discriminated union:

**File:** `lib/mas/elements/llms/types.py`

```python
from mas.elements.llms.<name>.config import <Name>Config

LLMsSpec = Annotated[
    Union[
        ...,
        <Name>Config,   # ← add here
    ],
    Field(discriminator="type")
]
```

---

## Reference Implementations

| Archetype | Reference | Notes |
|-----------|-----------|-------|
| Full-featured (streaming + tools + validation) | `llms/openai/` | OpenAI SDK, `stream_aggregator.py` for chunk assembly |
| Google multimodal (system instruction split) | `llms/google_genai/` | `SplitMessages` pattern for Gemini's separate system instruction |
| Test stub | `llms/mock/` | Returns canned responses, useful as starting skeleton |

---

## Reviewer Checklist

| Check | Expected |
|-------|----------|
| `spec/__init__.py` exists and exports spec | Auto-discovery depends on it |
| `type: Literal[Identifier.TYPE]` in config | Discriminated union requires it |
| Config added to `LLMsSpec` union in `llms/types.py` | Blueprint deserialization needs it |
| `bind_tools()` returns new instance | Immutability contract |
| `stream()` yields `str` then final `ChatMessage` | Streaming contract |
| Message converter is stateless (static methods) | No hidden state across calls |
| SDK imports confined to LLM module | Expected in elements layer |

| DO NOT flag | Why |
|-------------|-----|
| Direct SDK imports (`openai`, `google.genai`, etc.) | Elements ARE the integration layer — see Established Patterns |
| LangChain type imports in converter modules | LangChain bridge is a first-class integration target |
