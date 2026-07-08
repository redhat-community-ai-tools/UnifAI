"""
Execution handlers for different agent execution modes.

This module implements the Strategy pattern to handle different execution modes
(AUTO, GUIDED) in a clean, SOLID-compliant way. Each handler is responsible for
a specific execution policy while the iterator focuses purely on iteration.

Design Principles:
- Strategy Pattern: Different execution behaviors as separate classes
- Single Responsibility: Each handler has one execution policy
- Open/Closed: New modes = new handlers, no existing code changes
- Dependency Inversion: Iterator depends on ExecutionHandler abstraction
"""

import time
from abc import ABC, abstractmethod
from typing import List, Iterator, Optional, Callable, Dict, Any
from enum import Enum

from ..primitives import (
    AgentAction, 
    AgentObservation, 
    AgentStep, 
    StepType,
    ActionStatus
)
from .executor import AgentActionExecutor


class ExecutionMode(Enum):
    """Different modes of agent execution."""
    AUTO = "auto"          # Automatically execute all actions
    GUIDED = "guided"      # Ask for confirmation before execution
    HITL = "hitl"          # Gate WRITE tools through human approval


class ExecutionHandler(ABC):
    """
    Abstract base class for execution handlers.
    
    Each handler implements a specific execution policy for how actions
    should be processed. This allows the iterator to focus purely on
    iteration while delegating execution policy to specialized handlers.
    """
    
    def __init__(self, action_executor: AgentActionExecutor):
        """
        Initialize execution handler.
        
        Args:
            action_executor: The action executor for running tools
        """
        self.action_executor = action_executor
        self.observations: List[AgentObservation] = []
    
    @abstractmethod
    def handle_actions(self, actions: List[AgentAction]) -> Iterator[AgentStep]:
        """
        Handle a batch of actions according to execution policy.
        
        Args:
            actions: List of actions to handle
            
        Yields:
            AgentStep objects representing the execution results
        """
        pass
    
    @abstractmethod
    def is_ready_for_next_iteration(self) -> bool:
        """
        Check if handler is ready for the next iteration.
        
        Returns:
            True if ready to process more actions, False otherwise
        """
        pass
    
    def get_observations(self) -> List[AgentObservation]:
        """Get all observations collected by this handler."""
        return list(self.observations)


class AutoExecutionHandler(ExecutionHandler):
    """
    Automatic execution handler.
    
    Executes all actions immediately in batch and yields observation steps
    individually. This matches the standard LLM conversation format where
    multiple tool calls get multiple tool responses.
    """
    
    def handle_actions(self, actions: List[AgentAction]) -> Iterator[AgentStep]:
        """
        Execute all actions immediately and yield observations individually.
        
        Args:
            actions: Actions to execute
            
        Yields:
            Individual observation steps for each action
        """
        if not actions:
            return
        
        
        # Execute all actions together (efficient batch execution)
        batch_observations = self.action_executor.execute_batch(actions)
        
        # Store observations
        self.observations.extend(batch_observations)
        
        # Yield each observation as individual step (matches LLM conversation format)
        for obs in batch_observations:
            obs_step = AgentStep(
                StepType.OBSERVATION,
                obs,
                metadata={
                    "action_id": obs.action_id,
                    "execution_time": obs.execution_time,
                    "success": obs.success,
                    "handler": "auto"
                }
            )
            yield obs_step
    
    def is_ready_for_next_iteration(self) -> bool:
        """Auto handler is always ready for next iteration."""
        return True


class GuidedExecutionHandler(ExecutionHandler):
    """
    Guided execution handler.
    
    Queues actions for confirmation and provides methods for manual control.
    Actions are only executed when explicitly confirmed.
    """
    
    def __init__(self, action_executor: AgentActionExecutor):
        super().__init__(action_executor)
        self.pending_actions: List[AgentAction] = []
        self.confirmed_actions: Dict[str, bool] = {}
    
    def handle_actions(self, actions: List[AgentAction]) -> Iterator[AgentStep]:
        """
        Queue actions for confirmation.
        
        Args:
            actions: Actions to queue for confirmation
            
        Yields:
            Action steps that need confirmation
        """
        
        for action in actions:
            self.pending_actions.append(action)
            
            # Yield action step for confirmation
            action_step = AgentStep(
                StepType.ACTION,
                action,
                metadata={
                    "action_id": action.id,
                    "requires_confirmation": True,
                    "handler": "guided"
                }
            )
            yield action_step
    
    def confirm_action(self, action_id: str, execute: bool = True) -> Optional[AgentStep]:
        """
        Confirm and optionally execute a pending action.
        
        Args:
            action_id: ID of action to confirm
            execute: Whether to execute the action immediately
            
        Returns:
            Observation step if executed, None otherwise
        """
        # Find the action
        action = None
        for pending_action in self.pending_actions:
            if pending_action.id == action_id:
                action = pending_action
                break
        
        if not action:
            return None
        
        # Mark as confirmed
        self.confirmed_actions[action_id] = execute
        
        if execute:
            
            # Execute single action
            obs = self.action_executor.execute(action)
            self.observations.append(obs)
            
            # Remove from pending
            self.pending_actions.remove(action)
            
            # Return observation step
            return AgentStep(
                StepType.OBSERVATION,
                obs,
                metadata={
                    "action_id": obs.action_id,
                    "execution_time": obs.execution_time,
                    "success": obs.success,
                    "handler": "guided",
                    "confirmed": True
                }
            )
        else:
            # Remove from pending without executing
            self.pending_actions.remove(action)
            return None
    
    def get_pending_actions(self) -> List[AgentAction]:
        """Get list of actions pending confirmation."""
        return list(self.pending_actions)
    
    def is_ready_for_next_iteration(self) -> bool:
        """Guided handler is ready when no actions are pending."""
        return len(self.pending_actions) == 0


