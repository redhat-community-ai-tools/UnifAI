from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, List, Dict, Any


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"  # new role for tool response


@dataclass(frozen=True)
class ToolCall:
    """
    Minimal representation of a tool call.
    """
    name: str
    args: Dict
    tool_call_id: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass(frozen=True)
class ChatMessage:
    """
    Immutable message with optional tool call or tool result.
    """
    role: Role
    content: str
    tool_calls: Optional[List[ToolCall]] = None  # for assistant messages
    tool_call_id: Optional[str] = None  # for tool messages
    additional_kwargs: Optional[Dict[str, Any]] = None  # for thought signatures etc.
