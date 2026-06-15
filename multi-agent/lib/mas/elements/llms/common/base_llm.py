from abc import ABC, abstractmethod
from typing import Any, Iterator, List, Union

from mas.elements.tools.common.tool_definition import ToolDefinition
from .chat.message import ChatMessage


class BaseLLM(ABC):
    """Abstract base class for all LLM integrations (OpenAI, Google GenAI, etc.)."""

    @abstractmethod
    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        """Perform a single conversational completion and return the full response."""
        ...

    @abstractmethod
    def stream(self, messages: List[ChatMessage], **call_params: Any) -> Iterator[Union[str, ChatMessage]]:
        """Stream conversational completion with real-time token generation.

        Yields either incremental text tokens (str) or complete ChatMessage objects.
        For tool calling, yields final ChatMessage with tool_calls populated.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier for the LLM (for logging/debug)."""
        ...

    @abstractmethod
    def bind_tools(self, tools: List[ToolDefinition]) -> "BaseLLM":
        """Bind tool schemas to the LLM for function-calling.

        Accepts ToolDefinition (schema-only, no execution logic).
        Returns a new instance with tools bound, leaving the original unchanged.
        """
        ...
