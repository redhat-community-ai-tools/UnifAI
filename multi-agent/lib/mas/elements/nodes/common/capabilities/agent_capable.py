"""
Agent capability mixin for nodes.

This module provides the AgentCapableMixin that orchestrates the agent system
components into a cohesive capability that can be added to nodes. It provides
complete agent behavior with direct tool management and streaming support.

Design Principles:
- Self-contained: Manages tools directly without ToolCapableMixin
- Configuration-driven: Behavior controlled via config objects  
- Multiple APIs: Simple (run_agent) and advanced (create_iterator)
- SOLID compliance: Clean dependencies and interfaces
"""

import time
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, TypeVar, Generic, Iterator, Callable
from enum import Enum

from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.tools.common.execution import ToolExecutorManager, ExecutorConfig
from mas.elements.tools.common.execution.models import (
    ToolExecutionRequest, ToolExecutionResponse, BatchToolExecutionResponse
)
from mas.elements.nodes.common.agent import (
    AgentAction, AgentObservation, AgentFinish, AgentStep, StepType,
    AgentConfig
)
from mas.elements.nodes.common.agent.parsers import OutputParser, ToolCallParser, ParseError
from mas.elements.nodes.common.agent.strategies import AgentStrategy, ReActStrategy
from mas.elements.nodes.common.agent.strategies.plan_execute import PlanAndExecuteStrategy
from mas.elements.nodes.common.agent.execution import (
    AgentIterator, AgentActionExecutor, ExecutionMode, ExecutionHandlerFactory
)
from mas.elements.nodes.common.agent.constants import (
    EarlyStoppingPolicy, ExecutionDefaults, StrategyType, ErrorMessages
)
from mas.core.contracts import SupportsStreaming
from global_utils.utils.async_bridge import get_async_bridge

T = TypeVar("T", bound=SupportsStreaming)


class AgentCapableMixin(Generic[T]):
    """
    Self-contained agent capability mixin with direct tool management.
    
    Provides complete agent behavior including tool management, execution,
    and streaming support. No longer depends on ToolCapableMixin.
    
    Required Mixins (checked via __init_subclass__):
    - LlmCapableMixin: Provides chat() method
    - BaseNode: Provides _stream() and is_streaming()
    
    Public APIs:
    - run_agent(): Simple automatic execution
    - stream_agent(): Real-time streaming execution
    - create_iterator(): Advanced step-by-step control
    - create_strategy(): Factory for creating strategies
    - add_pre_execution_hook(): Add custom pre-execution hooks
    - add_post_execution_hook(): Add custom post-execution hooks
    
    Example:
        class MyAgentNode(
            AgentCapableMixin,
            LlmCapableMixin,
            BaseNode
        ):
            def run(self, state):
                # Create strategy with tools
                strategy = self.create_strategy(
                    tools=my_tools,
                    strategy_type=StrategyType.REACT.value
                )
                
                # Run agent
                messages = self._build_messages(state)
                result = self.run_agent(messages, strategy)
                return result
    """
    
    def __init_subclass__(cls) -> None:
        """
        Verify that required capabilities are present.
        
        Checks that the class has the required methods from other mixins
        to ensure proper composition.
        """
        required_attrs = ["chat", "_stream", "is_streaming"]
        missing = []
        
        for attr in required_attrs:
            if not any(hasattr(base, attr) for base in cls.__mro__):
                missing.append(attr)
        
        if missing:
            capabilities_map = {
                "chat": "LlmCapableMixin",
                "_stream": "BaseNode",
                "is_streaming": "BaseNode"
            }
            missing_mixins = {capabilities_map[attr] for attr in missing}
            raise TypeError(
                f"{cls.__name__} requires {', '.join(missing_mixins)} "
                f"to provide: {missing}"
            )
        
        super().__init_subclass__()
    
    def __init__(self, **kwargs):
        """Initialize agent capability."""
        super().__init__(**kwargs)
        self._tool_executor_manager: Optional[ToolExecutorManager] = None
        self._default_executor_config: Optional[ExecutorConfig] = None
        self._custom_pre_hooks: List[Callable] = []
        self._custom_post_hooks: List[Callable] = []
    
    # -------------------------------------------------------------------------
    # Hook Management API
    # -------------------------------------------------------------------------
    
    def add_pre_execution_hook(self, hook: Callable) -> None:
        """Add a custom pre-execution hook."""
        self._custom_pre_hooks.append(hook)
        # If executor already exists, add to it immediately
        if self._tool_executor_manager:
            self._tool_executor_manager.add_pre_execution_hook(hook)
    
    def add_post_execution_hook(self, hook: Callable) -> None:
        """Add a custom post-execution hook."""
        self._custom_post_hooks.append(hook)
        # If executor already exists, add to it immediately
        if self._tool_executor_manager:
            self._tool_executor_manager.add_post_execution_hook(hook)
    
    def set_default_executor_config(self, config: ExecutorConfig) -> None:
        """Set default configuration for ToolExecutorManager."""
        self._default_executor_config = config
    
    # -------------------------------------------------------------------------
    # Streaming Hooks (moved from ToolCapableMixin)
    # -------------------------------------------------------------------------
    
    def _ensure_executor(self, tools: List[BaseTool], config: Optional[ExecutorConfig] = None) -> ToolExecutorManager:
        """
        Ensure ToolExecutorManager exists with current tools and config.
        
        Creates or updates the executor manager as needed. Registers all hooks.
        
        Args:
            tools: Tools to register
            config: Optional executor config (uses default if None)
            
        Returns:
            Configured ToolExecutorManager
        """
        # Use provided config or default
        executor_config = config or self._default_executor_config or ExecutorConfig.create_default()
        
        # Create new executor (could optimize to reuse if config unchanged)
        self._tool_executor_manager = ToolExecutorManager(**executor_config.to_dict())
        self._tool_executor_manager.set_tools({tool.name: tool for tool in tools})
        
        # Setup standard hooks if streaming
        if hasattr(self, 'is_streaming') and hasattr(self, '_stream'):
            with get_async_bridge() as bridge:
                bridge.run(self._setup_standard_hooks())
        
        # Add custom hooks
        for hook in self._custom_pre_hooks:
            self._tool_executor_manager.add_pre_execution_hook(hook)
        for hook in self._custom_post_hooks:
            self._tool_executor_manager.add_post_execution_hook(hook)
        
        return self._tool_executor_manager
    
    async def _setup_standard_hooks(self: T) -> None:
        """Setup standard pre/post execution hooks for streaming."""
        if not self._tool_executor_manager:
            return
        
        # Standard pre-execution hook
        async def standard_pre_hook(tool, args, context):
            tool_call_id = context.get('tool_call_id', 
                                      f"call_{tool.name}_{id(args)}") if context else f"call_{tool.name}_{id(args)}"
            if self.is_streaming():
                self._stream({
                    "type": "tool_calling",
                    "tool": tool.name,
                    "call_id": tool_call_id,
                    "args": args
                })

        # Standard post-execution hook  
        async def standard_post_hook(response, context):
            pass
            # if self.is_streaming():
            #     self._stream({
            #         "type": "tool_result",
            #         "tool": response.tool_name,
            #         "call_id": response.tool_call_id,
            #         "output": response.result if response.success else f"Error: {response.error}"
            #     })

        # Add standard hooks
        self._tool_executor_manager.add_pre_execution_hook(standard_pre_hook)
        self._tool_executor_manager.add_post_execution_hook(standard_post_hook)
    
    def create_strategy(
        self,
        tools: List[BaseTool],
        strategy_type: str = StrategyType.REACT.value,
        *,
        parser: Optional[OutputParser] = None,
        system_message: Optional[str] = None,
        **kwargs
    ) -> AgentStrategy:
        """
        Factory method for creating agent strategies.
        
        Supports different strategy types and custom configuration.
        New strategies can be added by extending this method.
        
        Args:
            tools: Tools available to the strategy
            strategy_type: Type of strategy (StrategyType.REACT.value, etc.)
            parser: Custom output parser (default: ToolCallParser)
            system_message: System message from node (takes priority)
            **kwargs: Strategy-specific configuration
            
        Returns:
            Configured AgentStrategy instance
            
        Raises:
            ValueError: If strategy_type is unknown
        """
        if parser is None:
            parser = ToolCallParser()
        
        # Create llm_chat callable that binds self.chat
        llm_chat = lambda msgs, tools_subset: self.chat(msgs, tools_subset)
        
        if strategy_type == StrategyType.REACT.value:
            return ReActStrategy(
                llm_chat=llm_chat,
                tools=tools,
                parser=parser,
                system_message=system_message,
                **kwargs
            )
        elif strategy_type == StrategyType.PLAN_AND_EXECUTE.value:
            return PlanAndExecuteStrategy(
                llm_chat=llm_chat,
                tools=tools,
                parser=parser,
                system_message=system_message,
                **kwargs
            )
        # Add more strategies here as needed
        
        available_types = [e.value for e in StrategyType]
        raise ValueError(ErrorMessages.UNKNOWN_STRATEGY_TYPE.format(
            available_types=", ".join(available_types)
        ))
    
    
    
    def create_iterator(
        self,
        messages: List[ChatMessage],
        strategy: AgentStrategy,
        *,
        config: Optional[AgentConfig] = None,
        on_action: Optional[Callable[[AgentAction], bool]] = None
    ) -> AgentIterator:
        """
        Create iterator for step-by-step agent execution.
        
        Provides fine-grained control over agent execution with support
        for different modes and custom callbacks.
        
        Args:
            messages: Initial conversation messages
            strategy: Agent strategy to use
            config: Agent configuration (uses defaults if None)
            on_action: Callback to approve/reject actions
            
        Returns:
            Configured AgentIterator for step-by-step execution
        """
        if config is None:
            config = AgentConfig()
        
        # Get tools from strategy
        tools = list(strategy.all_tools.values())
        
        # Ensure executor exists with strategy's tools and config
        executor_manager = self._ensure_executor(tools, config.executor_config)
        
        # Create action executor
        action_executor = AgentActionExecutor(
            tool_executor_manager=executor_manager,
            validate_args=True
        )
        
        # Create execution handler based on mode (Strategy pattern)
        execution_handler = ExecutionHandlerFactory.create(
            mode=config.execution_mode,
            action_executor=action_executor
        )
        
        iterator = AgentIterator(
            strategy=strategy,
            execution_handler=execution_handler,
            stream=self._stream if self.is_streaming() else None,
            on_action=on_action,
        )
        
        # Set initial messages
        iterator.messages = list(messages)
        
        return iterator
    
    def run_agent(
        self,
        messages: List[ChatMessage],
        strategy: AgentStrategy,
        *,
        config: Optional[AgentConfig] = None
    ) -> Dict[str, Any]:
        """
        High-level API: Run agent to completion automatically.
        
        Simple interface for automatic agent execution. Creates an iterator
        and runs it to completion, returning the final result.
        
        Args:
            messages: Initial conversation messages
            strategy: Agent strategy to use
            config: Agent configuration
            
        Returns:
            Dictionary with output, reasoning, and optional intermediate steps
        """
        if config is None:
            config = AgentConfig()
        
        iterator = self.create_iterator(messages, strategy, config=config)
        
        result = {
            "output": None,
            "reasoning": "",
            "error": None,
            "success": False,
            "steps": [],
            "observations": [],
            "metadata": {}
        }
        
        start_time = time.time()
        
        try:
            for step in iterator:
                if config.return_intermediate:
                    result["steps"].append(step)
                
                # Handle different step types
                if step.type == StepType.FINISH:
                    finish_data = step.data
                    result.update(finish_data.as_dict())
                    result["success"] = True
                    break
                    
                elif step.type == StepType.ERROR:
                    result["error"] = str(step.data)
                    result["success"] = False
                    if config.early_stopping == "first_error":
                        break
                
                # Check execution time limit
                if config.max_execution_time:
                    elapsed = time.time() - start_time
                    if elapsed > config.max_execution_time:
                        result["error"] = f"Execution timeout ({elapsed:.1f}s)"
                        result["success"] = False
                        break
            
            # If no output set and no error, agent completed without output
            if result["output"] is None and not result["error"]:
                result["output"] = "Agent completed without producing output"
                result["success"] = False
                
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
            result["success"] = False
        
        # Add execution metadata
        result["metadata"] = {
            "execution_time": time.time() - start_time,
            "total_steps": len(iterator.history),
            "observations": len(iterator.observations),
            "strategy": strategy.strategy_name,
            "execution_mode": config.execution_mode.value
        }
        
        # Include intermediate data if requested
        if config.return_intermediate:
            result["observations"] = iterator.observations
            result["history"] = iterator.history
        
        return result
    
    def stream_agent(
        self,
        messages: List[ChatMessage],
        strategy: AgentStrategy,
        *,
        config: Optional[AgentConfig] = None,
        on_action: Optional[Callable[[AgentAction], bool]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream agent execution events in real-time.
        
        Yields execution events as they occur, allowing for real-time
        monitoring and intervention. Useful for UI integration.
        
        Args:
            messages: Initial conversation messages
            strategy: Agent strategy to use
            config: Agent configuration
            on_action: Callback to approve/reject actions
            
        Yields:
            Dictionary events with type, data, and metadata
        """
        if config is None:
            config = AgentConfig()
        
        # For streaming, we want automatic execution with real-time events
        # Use the requested execution mode (don't force GUIDED)
        stream_config = AgentConfig(
            execution_mode=config.execution_mode,  # Respect user's choice
            executor_config=config.executor_config,
            max_execution_time=config.max_execution_time,
            max_actions_per_minute=config.max_actions_per_minute,
            early_stopping=config.early_stopping,
            return_intermediate=config.return_intermediate
        )
        
        iterator = self.create_iterator(
            messages, 
            strategy,
            config=stream_config,
            on_action=on_action
        )
        
        pending_actions = []
        start_time = time.time()
        
        try:
            for step in iterator:
                yield {
                    "type": f"agent_{step.type.value}",
                    "data": self._serialize_step(step),
                    "timestamp": step.timestamp,
                    "metadata": step.metadata
                }
                
                if step.type == StepType.ACTION:
                    action = step.data
                    pending_actions.append(action)
                    
                # Observations will be yielded automatically by the iterator
                # in AUTO mode, or can be handled via guided confirmation in GUIDED mode
                
                elif step.type == StepType.FINISH:
                    # Yield final summary
                    yield {
                        "type": "agent_complete",
                        "data": {
                            "output": step.data.output,
                            "reasoning": step.data.reasoning,
                            "success": True,
                            "execution_time": time.time() - start_time,
                            "total_steps": len(iterator.history),
                            "actions_taken": len(pending_actions)
                        },
                        "timestamp": time.time(),
                        "metadata": {"final": True}
                    }
                    break
                
                elif step.type == StepType.ERROR:
                    yield {
                        "type": "agent_error", 
                        "data": {
                            "error": str(step.data),
                            "recoverable": getattr(step.data, 'recoverable', False),
                            "execution_time": time.time() - start_time
                        },
                        "timestamp": time.time(),
                        "metadata": {"error": True}
                    }
                    
                    if config.early_stopping == "first_error":
                        break
                        
        except Exception as e:
            yield {
                "type": "agent_error",
                "data": {
                    "error": f"Unexpected error: {e}",
                    "execution_time": time.time() - start_time
                },
                "timestamp": time.time(),
                "metadata": {"unexpected_error": True}
            }
    
    def _serialize_step(self, step: AgentStep) -> Dict[str, Any]:
        """
        Serialize step data for streaming/API consumption.
        
        Args:
            step: AgentStep to serialize
            
        Returns:
            Dictionary representation of step data
        """
        if step.type == StepType.ACTION:
            action = step.data
            return {
                "id": action.id,
                "tool": action.tool,
                "tool_input": action.tool_input,
                "reasoning": action.reasoning,
                "status": action.status.value
            }
            
        elif step.type == StepType.OBSERVATION:
            obs = step.data
            return {
                "action_id": obs.action_id,
                "tool": obs.tool,
                "output": obs.output,
                "success": obs.success,
                "execution_time": obs.execution_time,
                "error": str(obs.error) if obs.error else None
            }
            
        elif step.type == StepType.FINISH:
            finish = step.data
            return finish.as_dict()
            
        elif step.type == StepType.ERROR:
            return {
                "error": str(step.data),
                "error_type": type(step.data).__name__,
                "recoverable": getattr(step.data, 'recoverable', False)
            }
            
        elif step.type == StepType.PLANNING:
            if hasattr(step.data, 'content'):
                return {"reasoning": step.data.content}
            return {"data": str(step.data)}
        
        # Fallback
        return {"data": str(step.data)}
