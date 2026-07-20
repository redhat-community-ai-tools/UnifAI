"""
Agent execution control system.

This module provides fine-grained control over agent execution with different
modes and validation capabilities. Includes:

- AgentIterator: Step-by-step execution control with multiple modes
- AgentActionExecutor: Bridge between agent actions and tool system
- ExecutionMode: Different execution patterns (auto, guided)

Key Components:
- ExecutionMode: AUTO (automatic), GUIDED (confirmation)
- AgentIterator: Main execution controller with streaming support
- AgentActionExecutor: Executes actions using ToolExecutorManager directly

Example:
    ```python
    from agent.execution import AgentIterator, AgentActionExecutor, ExecutionMode
    
    iterator = AgentIterator(
        strategy=strategy,
        tool_executor=executor.execute,
        mode=ExecutionMode.AUTO
    )
    
    for step in iterator:
        if step.type == StepType.FINISH:
            break
    ```
"""

from .iterator import AgentIterator
from .executor import AgentActionExecutor
from .handler_factory import ExecutionHandlerFactory
from .handlers import (
    ExecutionHandler,
    AutoExecutionHandler,
    GuidedExecutionHandler,
    ExecutionMode,
)
from .hitl_handler import HITLExecutionHandler

__all__ = [
    "AgentIterator",
    "AgentActionExecutor",
    "ExecutionHandler",
    "AutoExecutionHandler", 
    "GuidedExecutionHandler",
    "HITLExecutionHandler",
    "ExecutionHandlerFactory",
    "ExecutionMode",
]
