"""
Protocol interfaces for the tool execution framework.

This module defines the interfaces that components must implement
to work with the execution framework.
"""
from abc import ABC, abstractmethod
from typing import Protocol, List, Dict, Any, Optional, runtime_checkable, Callable, Awaitable

from elements.tools.common.base_tool import BaseTool
from .models import ToolExecutionRequest, ToolExecutionResponse, ExecutionMode


@runtime_checkable
class ToolExecutor(Protocol):
    """Protocol for tool executors."""
    
    async def execute_requests_async(
        self,
        requests: List[ToolExecutionRequest],
        mode: ExecutionMode = ExecutionMode.PARALLEL
    ) -> Any:
        """Execute tool requests."""
        ...
    
    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to the executor."""
        ...
    
    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the executor."""
        ...


@runtime_checkable
class ErrorHandler(Protocol):
    """Protocol for error handling policies."""
    
    async def handle_error(
        self,
        error: Exception,
        tool: BaseTool,
        args: Dict[str, Any],
        attempt: int = 1,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Handle execution error."""
        ...


@runtime_checkable
class ExecutionValidator(Protocol):
    """Protocol for pre-execution validation."""
    
    async def validate(
        self,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate before execution."""
        ...


@runtime_checkable
class ExecutionHook(Protocol):
    """Protocol for execution hooks."""
    
    async def __call__(self, *args, **kwargs) -> None:
        """Execute the hook."""
        ...


class ExecutionStrategy(ABC):
    """Base class for execution strategies."""
    
    @abstractmethod
    async def execute_requests(
        self,
        requests: List[ToolExecutionRequest],
        executor_func: Callable[[ToolExecutionRequest], Awaitable[ToolExecutionResponse]]
    ) -> List[ToolExecutionResponse]:
        """Execute tool requests using the strategy."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for logging."""
        pass


@runtime_checkable
class StreamingHandler(Protocol):
    """Protocol for streaming execution events."""
    
    async def on_tool_start(
        self,
        tool_name: str,
        args: Dict[str, Any],
        tool_call_id: str
    ) -> None:
        """Called when tool execution starts."""
        ...
    
    async def on_tool_complete(
        self,
        tool_name: str,
        result: Any,
        tool_call_id: str,
        execution_time: float
    ) -> None:
        """Called when tool execution completes successfully."""
        ...
    
    async def on_tool_error(
        self,
        tool_name: str,
        error: Exception,
        tool_call_id: str,
        execution_time: float
    ) -> None:
        """Called when tool execution fails."""
        ...


@runtime_checkable
class CircuitBreaker(Protocol):
    """Protocol for circuit breaker implementations."""
    
    def can_execute(self, tool_name: str) -> bool:
        """Check if tool can be executed."""
        ...
    
    def record_success(self, tool_name: str) -> None:
        """Record successful execution."""
        ...
    
    def record_failure(self, tool_name: str) -> None:
        """Record failed execution."""
        ...
    
    def get_tool_status(self, tool_name: str) -> Dict[str, Any]:
        """Get status for a specific tool."""
        ...


@runtime_checkable
class MetricsCollector(Protocol):
    """Protocol for metrics collection."""
    
    def record_execution(
        self,
        tool_name: str,
        execution_time: float,
        success: bool,
        error: Optional[Exception] = None
    ) -> None:
        """Record tool execution metrics."""
        ...
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        ...
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        ...


# Type aliases for commonly used types
ExecutorFunction = Any  # Callable that executes a single request
HookFunction = Any      # Callable for pre/post execution hooks
