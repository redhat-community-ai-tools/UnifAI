"""
Execution strategies for different concurrency patterns.
"""
import asyncio
from typing import Callable, List, Awaitable

from .models import ToolExecutionRequest, ToolExecutionResponse
from .interfaces import ExecutionStrategy
from .exceptions import StrategyError



class SequentialStrategy(ExecutionStrategy):
    """Execute tools one after another."""
    
    @property
    def name(self) -> str:
        return "sequential"
    
    async def execute_requests(
        self,
        requests: List[ToolExecutionRequest],
        executor_func: Callable[[ToolExecutionRequest], Awaitable[ToolExecutionResponse]]
    ) -> List[ToolExecutionResponse]:
        """Execute tool requests sequentially."""
        print(f"Executing {len(requests)} tool requests sequentially")
        
        responses = []
        for i, request in enumerate(requests):
            print(f"Executing request {i+1}/{len(requests)}: {request.tool_name}")
            try:
                response = await executor_func(request)
                responses.append(response)
            except Exception as e:
                print(f"Error: Sequential execution failed for request {request.tool_call_id}: {e}")
                raise StrategyError(f"Sequential execution failed: {e}") from e
        
        print("Sequential execution completed")
        return responses


class ParallelStrategy(ExecutionStrategy):
    """Execute all tools in parallel."""
    
    @property
    def name(self) -> str:
        return "parallel"
    
    async def execute_requests(
        self,
        requests: List[ToolExecutionRequest],
        executor_func: Callable[[ToolExecutionRequest], Awaitable[ToolExecutionResponse]]
    ) -> List[ToolExecutionResponse]:
        """Execute tool requests in parallel."""
        print(f"Executing {len(requests)} tool requests in parallel")
        
        if not requests:
            return []
        
        # Create tasks for all requests
        tasks = []
        for request in requests:
            task = asyncio.create_task(
                executor_func(request),
                name=f"request_{request.tool_call_id}"
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"Error: Parallel execution failed: {e}")
            raise StrategyError(f"Parallel execution failed: {e}")
        
        # Convert exceptions to error responses
        processed_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                # Create error response for failed requests
                processed_responses.append(ToolExecutionResponse(
                    tool_call_id=requests[i].tool_call_id,
                    tool_name=requests[i].tool_name,
                    success=False,
                    error=response,  # Pass Exception directly
                    execution_time=0.0
                ))
            else:
                processed_responses.append(response)
        
        print(f"Parallel execution completed: {len(processed_responses)} responses")
        return processed_responses


class ConcurrentLimitedStrategy(ExecutionStrategy):
    """Execute tools with limited concurrency using a semaphore."""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
    
    @property
    def name(self) -> str:
        return f"concurrent_limited_{self.max_concurrent}"
    
    async def execute_requests(
        self,
        requests: List[ToolExecutionRequest],
        executor_func: Callable[[ToolExecutionRequest], Awaitable[ToolExecutionResponse]]
    ) -> List[ToolExecutionResponse]:
        """Execute tool requests with concurrency limit."""
        print(f"Executing {len(requests)} tool requests with max {self.max_concurrent} concurrent")
        
        if not requests:
            return []
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def execute_with_limit(request: ToolExecutionRequest) -> ToolExecutionResponse:
            async with semaphore:
                print(f"Acquired semaphore for {request.tool_call_id}")
                try:
                    response = await executor_func(request)
                    print(f"Released semaphore for {request.tool_call_id}")
                    return response
                except Exception as e:
                    print(f"Error: Error executing request {request.tool_call_id}: {e}")
                    return ToolExecutionResponse(
                        tool_call_id=request.tool_call_id,
                        tool_name=request.tool_name,
                        success=False,
                        error=str(e),
                        execution_time=0.0
                    )
        
        # Create tasks with semaphore control
        tasks = [
            asyncio.create_task(
                execute_with_limit(request),
                name=f"limited_request_{request.tool_call_id}"
            )
            for request in requests
        ]
        
        # Wait for all tasks to complete
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"Error: Concurrent limited execution failed: {e}")
            raise StrategyError(f"Concurrent limited execution failed: {e}")
        
        # Process responses (they should already be ToolExecutionResponse objects)
        processed_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                # Create error response for failed requests
                processed_responses.append(ToolExecutionResponse(
                    tool_call_id=requests[i].tool_call_id,
                    tool_name=requests[i].tool_name,
                    success=False,
                    error=response,  # Pass Exception directly
                    execution_time=0.0
                ))
            else:
                processed_responses.append(response)
        
        print(f"Concurrent limited execution completed: {len(processed_responses)} responses")
        return processed_responses


class BatchedStrategy(ExecutionStrategy):
    """Execute tools in batches of limited size."""
    
    def __init__(self, batch_size: int = 3):
        self.batch_size = batch_size
    
    @property
    def name(self) -> str:
        return f"batched_{self.batch_size}"
    
    async def execute_requests(
        self,
        requests: List[ToolExecutionRequest],
        executor_func: Callable[[ToolExecutionRequest], Awaitable[ToolExecutionResponse]]
    ) -> List[ToolExecutionResponse]:
        """Execute tool requests in batches."""
        # For now, not implemented - fallback to parallel execution
        raise NotImplementedError("BatchedStrategy.execute_requests not yet implemented. Use ParallelStrategy instead.")


class PriorityStrategy(ExecutionStrategy):
    """Execute tools based on priority order."""
    
    def __init__(self, priority_map: dict = None):
        """
        Initialize with priority mapping.
        Args:
            priority_map: Dict mapping tool names to priority (lower = higher priority)
        """
        self.priority_map = priority_map or {}
    
    @property
    def name(self) -> str:
        return "priority"
    
    async def execute_requests(
        self,
        requests: List[ToolExecutionRequest],
        executor_func: Callable[[ToolExecutionRequest], Awaitable[ToolExecutionResponse]]
    ) -> List[ToolExecutionResponse]:
        """Execute tool requests based on priority."""
        # For now, not implemented - fallback to sequential execution
        raise NotImplementedError("PriorityStrategy.execute_requests not yet implemented. Use SequentialStrategy instead.")