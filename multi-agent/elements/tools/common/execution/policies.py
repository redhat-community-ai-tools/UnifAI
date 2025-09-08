"""
Error handling and resilience policies.
"""
import asyncio
import time
from typing import Any, Dict, Optional, List, Union
from abc import ABC, abstractmethod
from elements.tools.common.base_tool import BaseTool
from .interfaces import ErrorHandler
from .exceptions import RetryExhaustedError, CircuitBreakerError, ToolExecutionError


class BaseErrorHandler(ErrorHandler):
    """Base error handler with common functionality."""
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
    
    async def handle_error(
        self,
        error: Exception,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Handle error - to be implemented by subclasses."""
        raise NotImplementedError


class RetryPolicy(BaseErrorHandler):
    """Retry failed executions with exponential backoff."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        super().__init__("RetryPolicy")
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    async def handle_error(
        self,
        error: Exception,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Retry execution with exponential backoff."""
        delay = self.initial_delay
        last_error = error
        
        print(f"Warning: Starting retry policy for {tool.name} after error: {error}")
        
        for attempt in range(self.max_retries):
            print(
                f"Retrying {tool.name} after error: {error}. "
                f"Attempt {attempt + 1}/{self.max_retries}"
            )
            
            # Apply jitter to delay if enabled
            actual_delay = delay
            if self.jitter:
                import random
                actual_delay = delay * (0.5 + random.random() * 0.5)
            
            await asyncio.sleep(actual_delay)
            
            try:
                # Try to execute the tool again
                result = await tool.arun(**args)
                
                print(f"Retry successful for {tool.name} on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                last_error = e
                print(f"Warning: Retry attempt {attempt + 1} failed for {tool.name}: {e}")
                
                # Calculate next delay
                delay = min(delay * self.exponential_base, self.max_delay)
        
        # All retries exhausted
        print(f"Error: All {self.max_retries} retry attempts exhausted for {tool.name}")
        raise RetryExhaustedError(
            f"All {self.max_retries} retry attempts failed",
            tool_name=tool.name,
            attempts=self.max_retries,
            last_error=last_error
        )


class FallbackPolicy(BaseErrorHandler):
    """Fallback to alternative tools on failure."""
    
    def __init__(self, fallback_tools: List[BaseTool]):
        super().__init__("FallbackPolicy")
        self.fallback_tools = fallback_tools
    
    async def handle_error(
        self,
        error: Exception,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Try fallback tools in order."""
        print(f"Warning: Primary tool {tool.name} failed: {error}")
        print(f"Trying {len(self.fallback_tools)} fallback tools")
        
        for i, fallback in enumerate(self.fallback_tools):
            try:
                print(f"Trying fallback tool {i+1}/{len(self.fallback_tools)}: {fallback.name}")
                
                result = await fallback.arun(**args)
                
                print(f"Fallback tool {fallback.name} succeeded")
                return result
                
            except Exception as e:
                print(f"Warning: Fallback {fallback.name} failed: {e}")
                continue
        
        # All fallbacks failed
        print(f"Error: All fallback tools failed for {tool.name}")
        raise ToolExecutionError(
            f"Primary tool and all {len(self.fallback_tools)} fallbacks failed",
            tool_name=tool.name,
            original_error=error
        )


class CircuitBreakerPolicy(BaseErrorHandler):
    """Circuit breaker pattern for fault tolerance."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        reset_timeout: float = 300.0
    ):
        super().__init__("CircuitBreakerPolicy")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.reset_timeout = reset_timeout
        
        # State per tool
        self._tool_states: Dict[str, Dict[str, Any]] = {}
    
    def _get_tool_state(self, tool_name: str) -> Dict[str, Any]:
        """Get or create state for a tool."""
        if tool_name not in self._tool_states:
            self._tool_states[tool_name] = {
                "state": "closed",  # closed, open, half-open
                "failure_count": 0,
                "last_failure_time": 0,
                "half_open_calls": 0,
                "last_success_time": time.time()
            }
        return self._tool_states[tool_name]
    
    async def handle_error(
        self,
        error: Exception,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Handle error with circuit breaker logic."""
        tool_state = self._get_tool_state(tool.name)
        current_time = time.time()
        
        # Check if circuit should transition from open to half-open
        if tool_state["state"] == "open":
            if current_time - tool_state["last_failure_time"] >= self.recovery_timeout:
                tool_state["state"] = "half-open"
                tool_state["half_open_calls"] = 0
                print(f"Circuit breaker for {tool.name} transitioning to HALF-OPEN")
            else:
                remaining_time = self.recovery_timeout - (current_time - tool_state["last_failure_time"])
                print(f"Warning: Circuit breaker is OPEN for {tool.name}. Remaining: {remaining_time:.1f}s")
                raise CircuitBreakerError(
                    f"Circuit breaker is OPEN for {tool.name}",
                    tool_name=tool.name
                )
        
        # Record failure
        tool_state["failure_count"] += 1
        tool_state["last_failure_time"] = current_time
        
        print(f"Warning: Circuit breaker recorded failure for {tool.name}. "
              f"Count: {tool_state['failure_count']}/{self.failure_threshold}")
        
        # Check if we should open the circuit
        if tool_state["failure_count"] >= self.failure_threshold:
            tool_state["state"] = "open"
            print(f"Error: Circuit breaker OPENED for {tool.name}")
            raise CircuitBreakerError(
                f"Circuit breaker opened due to {self.failure_threshold} failures",
                tool_name=tool.name,
                original_error=error
            )
        
        # For half-open state, check if we should close or open
        if tool_state["state"] == "half-open":
            tool_state["half_open_calls"] += 1
            if tool_state["half_open_calls"] >= self.half_open_max_calls:
                # Multiple failures in half-open, go back to open
                tool_state["state"] = "open"
                tool_state["last_failure_time"] = current_time
                print(f"Error: Circuit breaker returned to OPEN for {tool.name}")
        
        # Circuit is still allowing calls, propagate the error
        raise error
    
    def record_success(self, tool_name: str) -> None:
        """Record a successful execution (call this from the executor)."""
        tool_state = self._get_tool_state(tool_name)
        
        if tool_state["state"] == "half-open":
            # Success in half-open state - close the circuit
            tool_state["state"] = "closed"
            tool_state["failure_count"] = 0
            tool_state["last_success_time"] = time.time()
            print(f"Circuit breaker CLOSED for {tool_name} after successful test")
        elif tool_state["state"] == "closed":
            # Regular success - update timestamp and maybe reset failure count
            tool_state["last_success_time"] = time.time()
            # Gradually reduce failure count on success
            if tool_state["failure_count"] > 0:
                tool_state["failure_count"] = max(0, tool_state["failure_count"] - 1)
    
    def get_tool_status(self, tool_name: str) -> Dict[str, Any]:
        """Get current status of a tool's circuit breaker."""
        return self._get_tool_state(tool_name).copy()
    
    def can_execute(self, tool_name: str) -> bool:
        """Check if a tool can be executed based on circuit breaker state."""
        tool_state = self._get_tool_state(tool_name)
        current_time = time.time()
        
        if tool_state["state"] == "open":
            # Check if we can transition to half-open
            if current_time - tool_state["last_failure_time"] >= self.recovery_timeout:
                tool_state["state"] = "half-open"
                tool_state["half_open_calls"] = 0
                print(f"Circuit breaker for {tool_name} transitioning to HALF-OPEN")
                return True
            return False
        
        # Closed or half-open states allow execution
        return True
    
    def record_failure(self, tool_name: str) -> None:
        """Record a failure for a tool (call this from the executor)."""
        tool_state = self._get_tool_state(tool_name)
        current_time = time.time()
        
        tool_state["failure_count"] += 1
        tool_state["last_failure_time"] = current_time
        
        print(f"Warning: Circuit breaker recorded failure for {tool_name}. "
              f"Count: {tool_state['failure_count']}/{self.failure_threshold}")
        
        # Check if we should open the circuit
        if tool_state["failure_count"] >= self.failure_threshold:
            tool_state["state"] = "open"
            print(f"Error: Circuit breaker OPENED for {tool_name}")
        
        # For half-open state, check if we should go back to open
        if tool_state["state"] == "half-open":
            tool_state["half_open_calls"] += 1
            if tool_state["half_open_calls"] >= self.half_open_max_calls:
                # Multiple failures in half-open, go back to open
                tool_state["state"] = "open"
                tool_state["last_failure_time"] = current_time
                print(f"Error: Circuit breaker returned to OPEN for {tool_name}")


class CompositeErrorHandler(BaseErrorHandler):
    """Compose multiple error handlers in a chain."""
    
    def __init__(self, handlers: List[ErrorHandler], stop_on_success: bool = True):
        super().__init__("CompositeErrorHandler")
        self.handlers = handlers
        self.stop_on_success = stop_on_success
    
    async def handle_error(
        self,
        error: Exception,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Try each handler in sequence."""
        last_error = error
        
        for i, handler in enumerate(self.handlers):
            try:
                print(f"Debug: Trying error handler {i+1}/{len(self.handlers)}: {getattr(handler, 'name', type(handler).__name__)}")
                result = await handler.handle_error(last_error, tool, args, context)
                
                if self.stop_on_success:
                    print(f"Error handler {i+1} succeeded for {tool.name}")
                    return result
                    
            except Exception as e:
                print(f"Warning: Error handler {i+1} failed: {e}")
                last_error = e
                continue
        
        # All handlers failed
        print(f"Error: All {len(self.handlers)} error handlers failed for {tool.name}")
        raise last_error


class ConditionalErrorHandler(BaseErrorHandler):
    """Apply different handlers based on error type or conditions."""
    
    def __init__(self, handlers: Dict[type, ErrorHandler], default_handler: ErrorHandler = None):
        super().__init__("ConditionalErrorHandler")
        self.handlers = handlers
        self.default_handler = default_handler
    
    async def handle_error(
        self,
        error: Exception,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Route to appropriate handler based on error type."""
        error_type = type(error)
        
        # Find handler for this error type (including inheritance)
        handler = None
        for exc_type, exc_handler in self.handlers.items():
            if isinstance(error, exc_type):
                handler = exc_handler
                break
        
        if handler is None:
            handler = self.default_handler
        
        if handler is None:
            print(f"Error: No handler found for error type {error_type.__name__}")
            raise error
        
        print(f"Debug: Using handler {getattr(handler, 'name', type(handler).__name__)} for {error_type.__name__}")
        return await handler.handle_error(error, tool, args, context)


class RateLimitPolicy(BaseErrorHandler):
    """Handle rate limiting with backoff."""
    
    def __init__(self, calls_per_minute: int = 60, backoff_factor: float = 1.5):
        super().__init__("RateLimitPolicy")
        self.calls_per_minute = calls_per_minute
        self.backoff_factor = backoff_factor
        self._call_times: Dict[str, List[float]] = {}
    
    async def _wait_for_rate_limit(self, tool_name: str) -> None:
        """Wait if rate limit would be exceeded."""
        current_time = time.time()
        
        if tool_name not in self._call_times:
            self._call_times[tool_name] = []
        
        call_times = self._call_times[tool_name]
        
        # Remove old calls (older than 1 minute)
        cutoff_time = current_time - 60
        call_times[:] = [t for t in call_times if t > cutoff_time]
        
        # Check if we're at the limit
        if len(call_times) >= self.calls_per_minute:
            # Calculate wait time
            oldest_call = min(call_times)
            wait_time = 60 - (current_time - oldest_call)
            wait_time *= self.backoff_factor  # Apply backoff
            
            print(f"Warning: Rate limit reached for {tool_name}. Waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        # Record this call
        call_times.append(current_time)
    
    async def handle_error(
        self,
        error: Exception,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Handle rate limit errors by waiting and retrying."""
        # Check if this is a rate limit error (customize as needed)
        error_str = str(error).lower()
        if "rate limit" in error_str or "too many requests" in error_str:
            print(f"Warning: Rate limit error detected for {tool.name}: {error}")
            
            # Wait based on rate limiting
            await self._wait_for_rate_limit(tool.name)
            
            # Retry the operation
            try:
                return await tool.arun(**args)
            except Exception as retry_error:
                print(f"Error: Retry after rate limit still failed: {retry_error}")
                raise retry_error
        
        # Not a rate limit error, re-raise
        raise error
