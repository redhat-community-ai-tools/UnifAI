from typing import Iterator, List, Union

from ..common.base_llm import BaseLLM
from ..common.chat.message import ChatMessage, Role
from ...tools.common.tool_definition import ToolDefinition


class MockLLM(BaseLLM):

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        last_content = messages[-1].content if messages else ""
        return ChatMessage(
            role=Role.ASSISTANT,
            content=f"[MOCK RESPONSE] Hello! You said: {last_content}",
        )

    def stream(self, messages: List[ChatMessage], **call_params) -> Iterator[Union[str, ChatMessage]]:
        response = self.chat(messages)
        yield response.content

    def bind_tools(self, tools: List[ToolDefinition]) -> "MockLLM":
        return MockLLM()

    @property
    def name(self) -> str:
        return "mock"
