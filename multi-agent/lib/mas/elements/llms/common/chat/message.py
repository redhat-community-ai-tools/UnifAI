from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """Minimal representation of a tool call."""
    name: str
    args: Dict
    tool_call_id: str

    model_config = ConfigDict(frozen=True)


class ChatMessage(BaseModel):
    """Immutable message with optional tool call or tool result."""
    role: Role
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    additional_kwargs: Optional[Dict[str, Any]] = None
    sender_id: Optional[str] = None
    metadata: Dict[str, Any] = {}

    model_config = ConfigDict(frozen=True)

    @property
    def is_cancelled(self) -> bool:
        """Check if this message has been marked as cancelled."""
        return bool(self.metadata.get("is_cancelled"))
