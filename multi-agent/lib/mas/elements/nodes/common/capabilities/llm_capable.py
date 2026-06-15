from __future__ import annotations

import logging
from typing import Any, ClassVar, Generic, List, Optional, TypeVar

from mas.core.contracts import SupportsStreaming
from mas.elements.llms.common.base_llm import BaseLLM
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.tools.common.tool_definition import ToolDefinition

TSupportStream = TypeVar("TSupportStream", bound=SupportsStreaming)

logger = logging.getLogger(__name__)


class LlmCapableMixin(Generic[TSupportStream]):
    """Clean LLM capability mixin with streaming support.

    Provides chat functionality with optional tool binding, supporting both
    streaming and non-streaming modes. Designed for composition with other
    node capabilities.

    Requirements:
    - Host class must implement SupportsStreaming (_stream, is_streaming)
    """

    MIXIN_READS: ClassVar[set[str]] = set()
    MIXIN_WRITES: ClassVar[set[str]] = set()

    def __init_subclass__(cls) -> None:
        """Verify that host class implements required streaming interface."""
        if not issubclass(cls, SupportsStreaming):
            raise TypeError(
                f"{cls.__name__} requires streaming support (_stream + is_streaming)."
            )
        super().__init_subclass__()

    def __init__(
            self,
            *,
            llm: BaseLLM,
            system_message: str = "",
            **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.llm = llm
        self.system_message = system_message

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def chat(
            self: TSupportStream,
            messages: List[ChatMessage],
            tools: Optional[List[BaseTool]] = None,
    ) -> ChatMessage:
        """Primary chat interface with optional dynamic tool binding.

        When tools are provided, converts them to ``ToolDefinition`` and creates
        a temporary LLM instance with tools bound for this specific call.
        """
        definitions = self._tools_to_definitions(tools)
        llm_instance = self.llm.bind_tools(definitions)

        if self.is_streaming():
            return self._stream_chat(messages, llm_instance)
        return llm_instance.chat(messages)

    def bind_tools(self, tools: List[BaseTool]) -> None:
        """Permanently bind tools to this instance's LLM.

        Creates a new LLM instance with tools bound, replacing the current one.
        Prefer dynamic binding via ``chat(tools=...)`` for most use cases.
        """
        definitions = self._tools_to_definitions(tools)
        self.llm = self.llm.bind_tools(definitions)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _tools_to_definitions(tools: Optional[List[BaseTool]]) -> List[ToolDefinition]:
        """Convert executable domain tools to schema-only definitions for the LLM."""
        if not tools:
            return []
        return [t.to_definition() for t in tools]

    def _stream_chat(
            self: TSupportStream,
            messages: List[ChatMessage],
            llm_instance: BaseLLM,
            *,
            event_type: str = "llm_token",
    ) -> ChatMessage:
        """Handle streaming chat with any LLM instance."""
        accumulated_text = ""
        final_message: Optional[ChatMessage] = None

        for chunk in llm_instance.stream(messages):
            if isinstance(chunk, str):
                accumulated_text += chunk
                if self.is_streaming():
                    self._stream({"type": event_type, "chunk": chunk})
            elif isinstance(chunk, ChatMessage):
                final_message = chunk
                break
            else:
                raise TypeError(
                    f"LLM stream returned unexpected type: {type(chunk)}"
                )

        return final_message or ChatMessage(
            role=Role.ASSISTANT,
            content=accumulated_text,
        )
