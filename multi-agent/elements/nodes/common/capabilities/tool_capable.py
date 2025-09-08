import asyncio
import logging
from typing import (
    Any, Dict, List, Optional,
    Callable, TypeVar, Generic
)
from core.contracts import SupportsStreaming
from elements.llms.common.chat.message import ChatMessage, ToolCall, Role
from elements.tools.common.base_tool import BaseTool
from global_utils.utils.async_bridge import get_async_bridge

# Tool execution framework
from elements.tools.common.execution import (
    ToolExecutorManager,
    ExecutionMode,
    ExecutorConfig
)
from elements.tools.common.execution.models import (
    ToolExecutionRequest,
    ToolExecutionResponse,
    BatchToolExecutionResponse
)

T = TypeVar("T", bound=SupportsStreaming)


class ToolCapableMixin(Generic[T]):
    """
    Mixin for tool-equipped agents.

    Responsibilities:
      1. Enforce streaming protocol (_stream + is_streaming).
      2. Register tools into a name→instance map.
      3. Extract ToolCall objects from assistant messages.
      4. Invoke each tool (async or sync) and wrap results as ChatMessage(role=TOOL).
      5. Stream each tool result via self._stream().
      6. Provide invoke_tools() for ad-hoc use.
      7. Provide _execute_tool_cycle() which:
         - Runs chat→invoke_tools→feed back for up to max_rounds.
         - Streams lifecycle events: cycle_start, assistant_complete, tool_result, cycle_end.
         - Returns the final ChatMessage from the assistant.
    """

    def __init_subclass__(cls) -> None:
        # DIP: ensure host implements SupportsStreaming
        if not issubclass(cls, SupportsStreaming):
            raise TypeError(
                f"{cls.__name__} requires streaming support (_stream + is_streaming)."
            )
        super().__init_subclass__()

    def __init__(
            self,
            *,
            tools: List[BaseTool],
            executor_config: Optional[ExecutorConfig] = None,
            **kwargs: Any
    ):
        """
        :param tools: List of BaseTool instances for this agent.
        :param executor_config: Configuration for ToolExecutorManager (ExecutorConfig)
        """
        super().__init__(**kwargs)
        # SRP: only one job—manage the tool registry
        self._tools: Dict[str, BaseTool] = {tool.name: tool for tool in tools}

        # Initialize execution framework with typed configuration
        if executor_config is None:
            # Use default production-ready configuration
            config = ExecutorConfig.create_default()
        else:
            # Use provided ExecutorConfig directly
            config = executor_config

        self._executor = ToolExecutorManager(**config.to_dict())

        # Add streaming hooks if this object supports streaming
        bridge = get_async_bridge()
        bridge.run(self._setup_streaming_hooks())

    @property
    def tools(self) -> List[BaseTool]:
        """Expose tools as a simple list."""
        return list(self._tools.values())

    def set_tools(self, tools: List[BaseTool]):
        """Set tools (replaces existing tools in both mixin and executor)."""
        self._tools = {tool.name: tool for tool in tools}
        self._executor.set_tools(self._tools)

    def add_tool(self, tool: BaseTool):
        """Add a tool to both the mixin and executor registries."""
        self._tools[tool.name] = tool
        self._executor.add_tool(tool)

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from both registries. Returns True if tool was removed."""
        removed_from_mixin = self._tools.pop(tool_name, None) is not None
        removed_from_executor = self._executor.remove_tool(tool_name)
        return removed_from_mixin or removed_from_executor

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        return tool_name in self._tools

    def get_tool_names(self) -> List[str]:
        """Get list of available tool names."""
        return list(self._tools.keys())

    def _extract_tool_calls(self, msg: ChatMessage) -> List[ToolCall]:
        return msg.tool_calls or []

    async def _ainvoke_tool(self: T, tc: ToolCall) -> ChatMessage:
        """Async-invoke a single tool using the clean request/response API."""
        # Create a clean execution request
        request = ToolExecutionRequest(
            tool_name=tc.name,
            tool_call_id=tc.tool_call_id,
            args=tc.args,
            context={"single_tool_execution": True}
        )

        # Execute using the clean request/response API
        batch_response = await self._executor.execute_requests_async(
            requests=[request],
            mode=ExecutionMode.PARALLEL  # Even single tools use the same API
        )

        # Get the response
        response = batch_response.get_response(tc.tool_call_id)
        if not response:
            raise RuntimeError(f"No response received for tool call {tc.tool_call_id}")

        # Convert to ChatMessage
        content = str(response.result) if response.success else f"Error: {response.error}"
        return ChatMessage(
            role=Role.TOOL,
            content=content,
            tool_call_id=response.tool_call_id
        )

    async def _ainvoke_all(self, msg: ChatMessage):
        """Invoke all ToolCalls using the clean request/response model."""
        calls = self._extract_tool_calls(msg)

        if not calls:
            return []

        # Create clean execution requests
        requests = [
            ToolExecutionRequest(
                tool_name=tc.name,
                tool_call_id=tc.tool_call_id,
                args=tc.args,
                context={"message_id": getattr(msg, 'id', None)}
            )
            for tc in calls
        ]

        try:
            # Execute using the clean request/response API
            batch_response = await self._executor.execute_requests_async(
                requests=requests,
                mode=ExecutionMode.PARALLEL
            )

            # Convert responses to ChatMessages in the correct order
            messages = []
            for request in requests:  # Iterate in original order
                response = batch_response.get_response(request.tool_call_id)

                if response:
                    content = str(response.result) if response.success else f"Error: {response.error}"
                    messages.append(ChatMessage(
                        role=Role.TOOL,
                        content=content,
                        tool_call_id=response.tool_call_id
                    ))
                else:
                    # Shouldn't happen, but handle gracefully
                    messages.append(ChatMessage(
                        role=Role.TOOL,
                        content=f"No response received for tool call",
                        tool_call_id=request.tool_call_id
                    ))

            return messages

        except Exception as e:
            # If the new API fails, re-raise the error
            # No fallback to legacy - we use the clean API exclusively
            raise RuntimeError(f"Tool execution failed: {e}") from e

    def invoke_tools(self, msg: ChatMessage) -> List[ChatMessage]:
        """
        Sync entrypoint: returns a list of ChatMessages(role=TOOL) for any tool calls.
        """
        if msg.role != Role.ASSISTANT or not msg.tool_calls:
            return []
        bridge = get_async_bridge()
        return bridge.run(self._ainvoke_all(msg))

    def _execute_tool_cycle(
            self: T,
            initial_history: List[ChatMessage],
            chat_function: Callable[[List[ChatMessage]], ChatMessage],
            max_rounds: int = 20
    ) -> ChatMessage:
        """
        Runs the “LLM → tool invokes → feed back → repeat” loop up to max_rounds.

        :param initial_history: starting list of ChatMessages
        :param chat_function:   a method like self._chat
        :param max_rounds:      how many iterations to allow
        :returns: the final assistant ChatMessage
        """
        history = initial_history.copy()
        assistant: Optional[ChatMessage] = None

        # Stream cycle start
        if self.is_streaming():
            self._stream({"type": "tool_cycle_start"})

        for _ in range(max_rounds):
            # Ask the LLM (streams internally if enabled)
            assistant = chat_function(history)
            history.append(assistant)

            # Invoke any requested tools
            tool_msgs = self.invoke_tools(assistant)
            if not tool_msgs:
                break

            history.extend(tool_msgs)

        if assistant is None:
            raise RuntimeError("LLM did not produce any response within the tool cycle.")

        return assistant

    def get_executor_metrics(self) -> Dict[str, Any]:
        """Get metrics from the execution framework."""
        return self._executor.metrics

    def get_executor_health(self) -> Dict[str, Any]:
        """Get health status from the execution framework."""
        return self._executor.get_health()

    async def _setup_streaming_hooks(self):
        """Setup streaming hooks for the executor if streaming is available."""
        if hasattr(self, 'is_streaming') and hasattr(self, '_stream'):
            # Create pre-execution hook for tool calling

            async def pre_execution_hook(tool, args, context):
                tool_call_id = context.get('tool_call_id',
                                           f"call_{tool.name}_{id(args)}") if context else f"call_{tool.name}_{id(args)}"
                if self.is_streaming():
                    self._stream({
                        "type": "tool_calling",
                        "tool": tool.name,
                        "call_id": tool_call_id,
                        "args": args
                    })

                # Create post-execution hook for tool result  

            async def post_execution_hook(response, context):
                if self.is_streaming():
                    self._stream({
                        "type": "tool_result",
                        "tool": response.tool_name,
                        "call_id": response.tool_call_id,
                        "output": response.result if response.success else f"Error: {response.error}"
                    })

            # Add hooks to the executor
            self._executor.add_pre_execution_hook(pre_execution_hook)
            self._executor.add_post_execution_hook(post_execution_hook)
