"""
Custom exceptions for tool execution.
"""


class ToolExecutionError(Exception):
    """Base exception for tool execution errors."""
    
    def __init__(self, message: str, tool_name: str = None, original_error: Exception = None):
        super().__init__(message)
        self.tool_name = tool_name
        self.original_error = original_error
    
    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.tool_name:
            base_msg = f"[{self.tool_name}] {base_msg}"
        if self.original_error:
            base_msg += f" (Original: {self.original_error})"
        return base_msg


class ValidationError(ToolExecutionError):
    """Raised when tool validation fails."""
    pass


class TimeoutError(ToolExecutionError):
    """Raised when tool execution times out."""
    pass


class CircuitBreakerError(ToolExecutionError):
    """Raised when circuit breaker is open."""
    pass


class StrategyError(ToolExecutionError):
    """Raised when execution strategy fails."""
    pass


class RetryExhaustedError(ToolExecutionError):
    """Raised when all retry attempts are exhausted."""
    
    def __init__(self, message: str, tool_name: str = None, attempts: int = 0, last_error: Exception = None):
        super().__init__(message, tool_name, last_error)
        self.attempts = attempts
        self.last_error = last_error


class ToolNotFoundError(ToolExecutionError):
    """Raised when a requested tool is not found."""
    
    def __init__(self, tool_name: str, available_tools: list = None):
        message = f"Tool '{tool_name}' not found"
        if available_tools:
            message += f". Available tools: {', '.join(available_tools)}"
        super().__init__(message, tool_name)
        self.available_tools = available_tools or []


class ConcurrencyLimitError(ToolExecutionError):
    """Raised when concurrency limits are exceeded."""
    pass


class PermissionError(ToolExecutionError):
    """Raised when tool execution is not permitted."""
    pass

