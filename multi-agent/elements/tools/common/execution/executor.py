"""
Tool execution manager for multi-agent systems.

This module provides the core ToolExecutorManager class that orchestrates
tool execution using different strategies and error handling policies.
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Callable, Awaitable

from elements.tools.common.base_tool import BaseTool
from global_utils.utils.async_bridge import AsyncBridge

from .interfaces import ErrorHandler, ExecutionValidator, ExecutionStrategy
from .strategies import (
    SequentialStrategy, ParallelStrategy,
    ConcurrentLimitedStrategy
)
from .models import (
    ExecutionMode, ToolExecutionRequest, ToolExecutionResponse, BatchToolExecutionResponse,
    ExecutorMetrics as ExecutorMetricsModel, ExecutorHealth, CircuitBreakerStatus,
    CircuitBreakerReport, CircuitBreakerState
)
from .results import ExecutionMetrics
from .policies import RetryPolicy, CircuitBreakerPolicy
from .validators import ArgumentValidator, CompositeValidator
from .exceptions import ToolExecutionError, ValidationError


class ToolExecutorManager:
    """
    Professional tool execution manager with clean architecture.
    
    Features:
    - Strategy-based execution (Sequential, Parallel, Concurrent Limited)
    - Clean request/response API
    - Proper error handling
    - Tool registry management
    - Async-first design
    """

    def __init__(
            self,
            max_concurrent: int = 5,
            default_timeout: Optional[float] = None,
            enable_metrics: bool = True,
            error_handler: Optional[ErrorHandler] = None,
            validators: Optional[List[ExecutionValidator]] = None,
            enable_circuit_breaker: bool = False
    ):
        """
        Initialize the tool executor manager.
        
        Args:
            max_concurrent: Maximum concurrent executions for ConcurrentLimitedStrategy
            default_timeout: Default timeout for tool execution
            enable_metrics: Whether to enable execution metrics
            error_handler: Error handling policy (RetryPolicy, CircuitBreakerPolicy, etc.)
            validators: List of validators to apply before tool execution
            enable_circuit_breaker: Whether to enable circuit breaker pattern
        """
        self._max_concurrent = max_concurrent
        self._default_timeout = default_timeout
        self._enable_metrics = enable_metrics
        self._async_bridge = AsyncBridge()

        # Error handling
        self._error_handler = error_handler

        # Validation setup
        self._validators = validators or []

        # Circuit breaker
        self._circuit_breaker = CircuitBreakerPolicy() if enable_circuit_breaker else None

        # Initialize execution strategies
        self._strategies: Dict[ExecutionMode, ExecutionStrategy] = {
            ExecutionMode.SEQUENTIAL: SequentialStrategy(),
            ExecutionMode.PARALLEL: ParallelStrategy(),
            ExecutionMode.CONCURRENT_LIMITED: ConcurrentLimitedStrategy(max_concurrent)
        }

        # Execution hooks
        self._pre_execution_hooks: List[Callable] = []
        self._post_execution_hooks: List[Callable] = []

        # Metrics
        self._metrics = ExecutionMetrics()

        # Tool registry
        self._tool_registry: Dict[str, BaseTool] = {}

        # Thread safety
        self._lock = asyncio.Lock()

    # Clean API using request/response models
    async def execute_requests_async(
            self,
            requests: List[ToolExecutionRequest],
            mode: ExecutionMode = ExecutionMode.PARALLEL
    ) -> BatchToolExecutionResponse:
        """
        Execute tool requests using clean request/response models.
        
        Args:
            requests: List of ToolExecutionRequest objects
            mode: Execution mode
            
        Returns:
            BatchToolExecutionResponse with responses keyed by tool_call_id
        """
        start_time = time.time()
        print(f"Starting execution of {len(requests)} tool requests using {mode.value} strategy")

        # Get the appropriate strategy based on execution mode
        strategy = self._strategies.get(mode)
        if not strategy:
            raise ValueError(f"No strategy found for execution mode: {mode}")

        # Execute using the strategy's request/response interface
        # Fix: Pass the async function directly, strategies handle await
        response_list = await strategy.execute_requests(requests, self._execute_single_request)

        # Convert list to dict keyed by tool_call_id
        responses = {response.tool_call_id: response for response in response_list}
        return BatchToolExecutionResponse(
            responses=responses,
            total_time=time.time() - start_time,
            execution_mode=mode.value,
            metadata={
                "request_count": len(requests),
                "tool_names": [req.tool_name for req in requests]
            }
        )

    async def _execute_single_request(
            self,
            request: ToolExecutionRequest
    ) -> ToolExecutionResponse:
        """Execute a single tool request with comprehensive error handling and hooks."""
        start_time = time.time()

        # Get the tool
        tool = self._tool_registry.get(request.tool_name)
        if not tool:
            return ToolExecutionResponse(
                tool_call_id=request.tool_call_id,
                tool_name=request.tool_name,
                success=False,
                error=Exception(f"Tool '{request.tool_name}' not found"),
                execution_time=time.time() - start_time
            )

        try:
            # Create enhanced context with tool_call_id for hooks
            enhanced_context = (request.context or {}).copy()
            enhanced_context['tool_call_id'] = request.tool_call_id

            # Pre-execution hooks
            await self._run_pre_execution_hooks(tool, request.args, enhanced_context)

            # Validation - run all validators
            for validator in self._validators:
                is_valid, error_msg = await validator.validate(tool, request.args, request.context)
                if not is_valid:
                    raise ValidationError(error_msg or "Validation failed", tool_name=tool.name)

            # Circuit breaker check
            if self._circuit_breaker:
                if not self._circuit_breaker.can_execute(tool.name):
                    raise Exception(f"Circuit breaker is open for tool {tool.name}")

            # Execute the tool with timeout
            result = await self._execute_with_timeout(tool, request.args, self._default_timeout)

            # Record success in circuit breaker
            if self._circuit_breaker:
                self._circuit_breaker.record_success(tool.name)

            response = ToolExecutionResponse(
                tool_call_id=request.tool_call_id,
                tool_name=request.tool_name,
                success=True,
                result=result,
                execution_time=time.time() - start_time
            )

            # Post-execution hooks
            await self._run_post_execution_hooks(response, enhanced_context)

            # Update metrics (thread-safe)
            if self._enable_metrics:
                async with self._lock:
                    self._metrics._execution_count = getattr(self._metrics, '_execution_count', 0) + 1

            return response

        except Exception as e:
            print(f"Error executing tool {request.tool_name}: {e}")

            # Record failure in circuit breaker
            if self._circuit_breaker:
                self._circuit_breaker.record_failure(tool.name)

            # Try error handler
            if self._error_handler:
                try:
                    handled_result = await self._error_handler.handle_error(e, tool, request.args, request.context)
                    response = ToolExecutionResponse(
                        tool_call_id=request.tool_call_id,
                        tool_name=request.tool_name,
                        success=True,
                        result=handled_result,
                        execution_time=time.time() - start_time
                    )
                    await self._run_post_execution_hooks(response, request.context)
                    return response
                except Exception:
                    pass  # Fall through to error response

            # Update error metrics (thread-safe)
            if self._enable_metrics:
                async with self._lock:
                    self._metrics._error_count = getattr(self._metrics, '_error_count', 0) + 1

            error_response = ToolExecutionResponse(
                tool_call_id=request.tool_call_id,
                tool_name=request.tool_name,
                success=False,
                error=e,
                execution_time=time.time() - start_time
            )

            # Post-execution hooks for errors too
            await self._run_post_execution_hooks(error_response, request.context)

            return error_response

    # Tool registry management
    def add_tool(self, tool: BaseTool) -> None:
        """Add a single tool to the registry."""
        self._tool_registry[tool.name] = tool

    def add_tools(self, tools: Dict[str, BaseTool]) -> None:
        """Add multiple tools to the registry."""
        self._tool_registry.update(tools)

    def set_tools(self, tools: Dict[str, BaseTool]) -> None:
        """Set the tool registry (replaces existing tools)."""
        self._tool_registry = tools.copy()

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the registry. Returns True if tool was removed."""
        return self._tool_registry.pop(tool_name, None) is not None

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tool_registry.get(tool_name)

    def get_tool_names(self) -> List[str]:
        """Get list of all tool names."""
        return list(self._tool_registry.keys())

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool exists in the registry."""
        return tool_name in self._tool_registry

    def _get_available_tools(self) -> List[BaseTool]:
        """Get available tools from the tool registry."""
        return list(self._tool_registry.values())

    # Metrics and monitoring
    @property
    def metrics(self) -> ExecutorMetricsModel:
        """Get comprehensive execution metrics."""
        total_executions = getattr(self._metrics, "_execution_count", 0)
        total_errors = getattr(self._metrics, "_error_count", 0)

        return ExecutorMetricsModel(
            total_executions=total_executions,
            total_errors=total_errors,
            success_rate=(
                    (total_executions - total_errors) / total_executions * 100) if total_executions > 0 else 100.0,
            error_rate=(total_errors / total_executions * 100) if total_executions > 0 else 0.0,
            tools_registered=len(self._tool_registry),
            tool_names=list(self._tool_registry.keys()),
            strategies={mode.value: strategy.name for mode, strategy in self._strategies.items()},
            features={
                "error_handler_enabled": self._error_handler is not None,
                "circuit_breaker_enabled": self._circuit_breaker is not None,
                "validators_enabled": len(self._validators) > 0,
                "metrics_enabled": self._enable_metrics,
                "pre_hooks_count": len(self._pre_execution_hooks),
                "post_hooks_count": len(self._post_execution_hooks)
            }
        )

    def get_health(self) -> ExecutorHealth:
        """Get health status of the executor."""
        return ExecutorHealth(
            status="healthy",
            strategies_loaded=len(self._strategies),
            tools_registered=len(self._tool_registry),
            max_concurrent=self._max_concurrent,
            metrics_enabled=self._enable_metrics,
            features_enabled={
                "error_handler": self._error_handler is not None,
                "circuit_breaker": self._circuit_breaker is not None,
                "validators": len(self._validators) > 0,
                "pre_hooks": len(self._pre_execution_hooks) > 0,
                "post_hooks": len(self._post_execution_hooks) > 0
            }
        )

    # Execution hooks management
    def add_pre_execution_hook(self, hook):
        """Add a pre-execution hook. Hook signature: async def hook(tool, args, context)."""
        self._pre_execution_hooks.append(hook)

    def add_post_execution_hook(self, hook):
        """Add a post-execution hook. Hook signature: async def hook(result, context)."""
        self._post_execution_hooks.append(hook)

    def remove_pre_execution_hook(self, hook):
        """Remove a pre-execution hook."""
        if hook in self._pre_execution_hooks:
            self._pre_execution_hooks.remove(hook)

    def remove_post_execution_hook(self, hook):
        """Remove a post-execution hook."""
        if hook in self._post_execution_hooks:
            self._post_execution_hooks.remove(hook)

    def add_streaming_hooks(self, pre_hook=None, post_hook=None):
        """Add streaming hooks for tool execution events."""
        if pre_hook:
            self.add_pre_execution_hook(pre_hook)
        if post_hook:
            self.add_post_execution_hook(post_hook)

    async def _run_pre_execution_hooks(self, tool: BaseTool, args: Dict[str, Any], context: Optional[Dict[str, Any]]):
        """Run all pre-execution hooks (thread-safe)."""
        # Get a snapshot of hooks to avoid issues if hooks are modified during execution
        async with self._lock:
            hooks_snapshot = self._pre_execution_hooks.copy()

        for hook in hooks_snapshot:
            try:
                await hook(tool, args, context)
            except Exception as e:
                print(f"Warning: Pre-execution hook failed: {e}")

    async def _run_post_execution_hooks(self, result: ToolExecutionResponse, context: Optional[Dict[str, Any]]):
        """Run all post-execution hooks (thread-safe)."""
        # Get a snapshot of hooks to avoid issues if hooks are modified during execution
        async with self._lock:
            hooks_snapshot = self._post_execution_hooks.copy()

        for hook in hooks_snapshot:
            try:
                await hook(result, context)
            except Exception as e:
                print(f"Warning: Post-execution hook failed: {e}")

    async def _execute_with_timeout(self, tool: BaseTool, args: Dict[str, Any], timeout: Optional[float]):
        """Execute tool with timeout support."""
        if timeout:
            try:
                return await asyncio.wait_for(
                    self._execute_tool_direct(tool, args),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                raise Exception(f"Tool {tool.name} execution timed out after {timeout}s")
        else:
            return await self._execute_tool_direct(tool, args)

    async def _execute_tool_direct(self, tool: BaseTool, args: Dict[str, Any]):
        """Direct tool execution without additional handling."""
        return await tool.arun(**args)

    # Circuit breaker monitoring
    def get_circuit_breaker_status(self, tool_name: str = None) -> CircuitBreakerReport:
        """Get circuit breaker status for tools."""
        if not self._circuit_breaker:
            return CircuitBreakerReport(enabled=False, tool_statuses={})

        if tool_name:
            # Return status for single tool
            tool_state = self._circuit_breaker.get_tool_status(tool_name)
            cb_status = CircuitBreakerStatus(
                tool_name=tool_name,
                state=CircuitBreakerState(tool_state.get("state", "closed")),
                failure_count=tool_state.get("failure_count", 0),
                can_execute=self._circuit_breaker.can_execute(tool_name),
                last_failure_time=tool_state.get("last_failure_time"),
                last_success_time=tool_state.get("last_success_time"),
                half_open_calls=tool_state.get("half_open_calls", 0)
            )
            return CircuitBreakerReport(enabled=True, tool_statuses={tool_name: cb_status})
        else:
            # Return status for all tools
            tool_statuses = {}
            for name in self._tool_registry.keys():
                tool_state = self._circuit_breaker.get_tool_status(name)
                cb_status = CircuitBreakerStatus(
                    tool_name=name,
                    state=CircuitBreakerState(tool_state.get("state", "closed")),
                    failure_count=tool_state.get("failure_count", 0),
                    can_execute=self._circuit_breaker.can_execute(name),
                    last_failure_time=tool_state.get("last_failure_time"),
                    last_success_time=tool_state.get("last_success_time"),
                    half_open_calls=tool_state.get("half_open_calls", 0)
                )
                tool_statuses[name] = cb_status

            return CircuitBreakerReport(enabled=True, tool_statuses=tool_statuses)


# Factory functions
def create_executor(max_concurrent: int = 5, **kwargs) -> ToolExecutorManager:
    """Create a basic tool executor."""
    return ToolExecutorManager(max_concurrent=max_concurrent, **kwargs)


def create_robust_executor(
        max_concurrent: int = 3,
        default_timeout: float = 30.0,
        validate_args: bool = True,
        **kwargs
) -> ToolExecutorManager:
    """Create a robust tool executor with comprehensive error handling and validation."""
    validators = []
    if validate_args:
        validators.append(ArgumentValidator(strict=True))

    return ToolExecutorManager(
        max_concurrent=max_concurrent,
        default_timeout=default_timeout,
        error_handler=RetryPolicy(max_retries=2, initial_delay=0.5),
        enable_circuit_breaker=True,
        enable_metrics=True,
        validators=validators,
        **kwargs
    )
