"""
Tool execution framework for multi-agent systems.

This module provides a comprehensive, SOLID-designed tool execution framework
that supports various execution strategies, error handling policies, and
monitoring capabilities.

Main Components:
- ToolExecutorManager: Core executor with sync/async support
- ExecutionMode: Different execution strategies (sequential, parallel, etc.)
- Error handling policies: Retry, circuit breaker, fallback patterns
- Result types: Structured results with metrics and metadata
- Hooks system: Pre/post execution extensibility

Usage:
    from elements.tools.common.execution import (
        ToolExecutorManager, ExecutionMode, 
        ToolExecutionRequest
    )
    
    # Create executor
    executor = ToolExecutorManager()
    
    # Execute single tool
    result = executor.execute(tool, {"arg": "value"})
    
    # Execute batch using clean API
    requests = [
        ToolExecutionRequest(tool_name="tool1", tool_call_id="1", args=args1),
        ToolExecutionRequest(tool_name="tool2", tool_call_id="2", args=args2)
    ]
    batch_result = await executor.execute_requests_async(
        requests, mode=ExecutionMode.PARALLEL
    )
"""

# Core components
from .executor import ToolExecutorManager, create_executor, create_robust_executor
from .interfaces import ToolExecutor, ErrorHandler, ExecutionValidator, ExecutionStrategy
from .results import ToolExecutionResult, BatchExecutionResult, ExecutionMetrics
from .models import (
    ToolExecutionRequest, ToolExecutionResponse, BatchToolExecutionResponse,
    ExecutorMetrics, ExecutorHealth, CircuitBreakerStatus, CircuitBreakerReport,
    CircuitBreakerState, ExecutorConfig, ExecutionMode
)

# Strategies
from .strategies import (
    SequentialStrategy,
    ParallelStrategy, 
    ConcurrentLimitedStrategy,
    BatchedStrategy,
    PriorityStrategy
)

# Error handling policies
from .policies import (
    BaseErrorHandler,
    RetryPolicy,
    FallbackPolicy,
    CircuitBreakerPolicy,
    CompositeErrorHandler,
    ConditionalErrorHandler,
    RateLimitPolicy
)

# Validation components
from .validators import (
    ArgumentValidator,
    CompositeValidator
)

# Exceptions
from .exceptions import (
    ToolExecutionError,
    ValidationError,
    TimeoutError,
    CircuitBreakerError,
    StrategyError,
    RetryExhaustedError,
    ToolNotFoundError,
    ConcurrencyLimitError,
    PermissionError
)

__all__ = [
    # Core
    "ToolExecutorManager",
    "create_executor", 
    "create_robust_executor",
    "ToolExecutor",
    "ErrorHandler",
    "ExecutionValidator",
    
    # Results
    "ToolExecutionResult",
    "BatchExecutionResult", 
    "ExecutionMetrics",
    
    # Models
    "ExecutionMode",
    "ToolExecutionRequest",
    "ToolExecutionResponse", 
    "BatchToolExecutionResponse",
    "ExecutorMetrics",
    "ExecutorHealth",
    "CircuitBreakerStatus",
    "CircuitBreakerReport",
    "CircuitBreakerState",
    "ExecutorConfig",
    
    # Strategies
    "ExecutionStrategy",
    "SequentialStrategy",
    "ParallelStrategy",
    "ConcurrentLimitedStrategy", 
    "BatchedStrategy",
    "PriorityStrategy",
    
    # Policies
    "BaseErrorHandler",
    "RetryPolicy",
    "FallbackPolicy",
    "CircuitBreakerPolicy",
    "CompositeErrorHandler",
    "ConditionalErrorHandler",
    "RateLimitPolicy",
    
    # Validators
    "ArgumentValidator",
    "CompositeValidator",
    
    # Exceptions
    "ToolExecutionError",
    "ValidationError",
    "TimeoutError",
    "CircuitBreakerError",
    "StrategyError", 
    "RetryExhaustedError",
    "ToolNotFoundError",
    "ConcurrencyLimitError",
    "PermissionError"
]

# Version info
__version__ = "1.0.0"
