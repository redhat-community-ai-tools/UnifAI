"""
High-level agent execution utilities.

This module provides simple utilities for common agent execution patterns.
Built on top of the core agent system but provides convenient APIs for
typical use cases.

Design Principles:
- Convenience: Simple APIs for common patterns
- Configurability: Support for different execution modes
- Reusability: Can be used across different node types
- Integration: Works with existing agent system components
"""

import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field

from global_utils.utils.logging_config import emit

from mas.elements.llms.common.chat.message import ChatMessage
from .primitives import AgentStep, StepType
from .execution import AgentIterator
from .constants import EarlyStoppingPolicy, ExecutionDefaults

logger = logging.getLogger(__name__)


@dataclass
class RunnerConfig:
    """Configuration for agent runners."""
    max_time: Optional[float] = None
    early_stopping: str = EarlyStoppingPolicy.FIRST_FINISH.value
    return_intermediate: bool = ExecutionDefaults.RETURN_INTERMEDIATE
    timeout_message: str = ExecutionDefaults.TIMEOUT_MESSAGE
    max_consecutive_errors: int = ExecutionDefaults.MAX_CONSECUTIVE_ERRORS


class AgentRunner:
    """
    High-level runner for agent execution with various stopping conditions.
    
    Provides convenience methods for running agents with different policies
    around timing, error handling, and result collection.
    
    Example:
        runner = AgentRunner(RunnerConfig(
            max_time=30.0,
            early_stopping=EarlyStoppingPolicy.FIRST_FINISH.value
        ))
        
        result = runner.run(iterator)
    """
    
    def __init__(self, config: Optional[RunnerConfig] = None):
        """
        Initialize runner with configuration.
        
        Args:
            config: Runner configuration (uses defaults if None)
        """
        self.config = config or RunnerConfig()
    
    def run(self, iterator: AgentIterator) -> Dict[str, Any]:
        """
        Run agent iterator to completion with configured stopping conditions.
        
        Args:
            iterator: Configured AgentIterator to execute
            
        Returns:
            Dictionary with execution results and metadata
        """
        start_time = time.time()
        finish_data = None
        error_data = None
        consecutive_errors = 0
        
        result = {
            "success": False,
            "output": None,
            "reasoning": "",
            "error": None,
            "execution_time": 0.0,
            "total_steps": 0,
            "observations": [],
            "metadata": {}
        }
        
        try:
            for step in iterator:
                # Update step count
                result["total_steps"] += 1
                
                # Check time limit
                elapsed = time.time() - start_time
                if self.config.max_time and elapsed > self.config.max_time:
                    result["error"] = self.config.timeout_message
                    break
                
                # Handle different step types
                if step.type == StepType.FINISH:
                    finish_data = step.data
                    consecutive_errors = 0  # Reset error count on success
                    
                    if self.config.early_stopping == EarlyStoppingPolicy.FIRST_FINISH.value:
                        break
                        
                elif step.type == StepType.ERROR:
                    error_data = step.data
                    consecutive_errors += 1
                    
                    # Check if we should stop on errors
                    if consecutive_errors >= self.config.max_consecutive_errors:
                        result["error"] = f"Too many consecutive errors ({consecutive_errors})"
                        break
                    
                    if self.config.early_stopping == EarlyStoppingPolicy.FIRST_ERROR.value:
                        break
                        
                else:
                    # Reset error count on non-error steps
                    consecutive_errors = 0
                
                # Store intermediate steps if requested
                if self.config.return_intermediate:
                    if "steps" not in result:
                        result["steps"] = []
                    result["steps"].append(step)
            
            # Set final results
            result["execution_time"] = time.time() - start_time
            
            if finish_data:
                result["success"] = True
                result.update(finish_data.as_dict())
            elif error_data and not result["error"]:
                result["error"] = str(error_data)
            elif not result["error"]:
                result["error"] = "Agent completed without finish or error"
            
            # Add execution metadata
            result["metadata"] = {
                "total_observations": len(iterator.observations),
                "consecutive_errors": consecutive_errors,
                "stopped_early": result["total_steps"] < iterator.strategy.max_steps,
                "timeout": bool(self.config.max_time and result["execution_time"] > self.config.max_time)
            }
            
            # Include observations if requested
            if self.config.return_intermediate:
                result["observations"] = iterator.observations
                
        except Exception as e:
            result["error"] = f"Runner exception: {e}"
            result["execution_time"] = time.time() - start_time
        
        return result
    
    def run_simple(
        self,
        iterator: AgentIterator,
        timeout: Optional[float] = None
    ) -> str:
        """
        Simple interface that just returns the output string.
        
        Args:
            iterator: Configured AgentIterator
            timeout: Optional timeout in seconds
            
        Returns:
            Agent output as string, or error message
        """
        config = RunnerConfig(
            max_time=timeout,
            early_stopping=EarlyStoppingPolicy.FIRST_FINISH.value,
            return_intermediate=False
        )
        
        runner = AgentRunner(config)
        result = runner.run(iterator)
        
        if result["success"]:
            return str(result["output"])
        else:
            return f"Error: {result['error']}"


class StreamingRunner:
    """
    Runner that yields intermediate results during execution.
    
    Useful for real-time UIs or monitoring systems that want to see
    agent progress as it happens.
    """
    
    def __init__(self, config: Optional[RunnerConfig] = None):
        self.config = config or RunnerConfig()
    
    def run_streaming(
        self,
        iterator: AgentIterator,
        on_step: Optional[Callable[[AgentStep], None]] = None
    ) -> Dict[str, Any]:
        """
        Run with streaming callbacks.
        
        Args:
            iterator: Configured AgentIterator
            on_step: Optional callback for each step
            
        Returns:
            Final execution result
        """
        start_time = time.time()
        
        for step in iterator:
            # Call step callback if provided
            if on_step:
                try:
                    on_step(step)
                except Exception as e:
                    emit(logger, logging.WARNING, "agent.callback_error", error=str(e))
            
            # Check time limits
            if self.config.max_time:
                elapsed = time.time() - start_time
                if elapsed > self.config.max_time:
                    break
        
        # Use standard runner for final result
        runner = AgentRunner(self.config)
        # Note: iterator is already consumed, but we can get final state
        return {
            "success": True,  # If we got here, we completed
            "execution_time": time.time() - start_time,
            "total_steps": len(iterator.history),
            "observations": len(iterator.observations),
            "metadata": {"streamed": True}
        }
