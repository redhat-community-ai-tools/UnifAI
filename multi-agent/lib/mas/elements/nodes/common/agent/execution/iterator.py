"""
AgentIterator focused purely on iteration (SOLID compliant).

This module provides an AgentIterator that follows SOLID principles:
- Single Responsibility: Only handles iteration logic
- Open/Closed: Extensible via ExecutionHandler strategy
- Dependency Inversion: Depends on ExecutionHandler abstraction

The iterator delegates execution policy to ExecutionHandler implementations,
keeping the iterator focused on its core responsibility: step-by-step control.
"""

from typing import Iterator, Optional, List, Callable, Dict, Any

from ..primitives import (
    AgentAction,
    AgentObservation,
    AgentStep,
    StepType,
    ActionStatus,
    AgentFinish
)
from ..strategies.base import AgentStrategy
from mas.elements.llms.common.chat.message import ChatMessage, Role
from .handlers import ExecutionHandler, GuidedExecutionHandler


class AgentIterator:
    """
    Iterator for step-by-step agent execution.
    
    Focuses purely on iteration logic while delegating execution policy
    to ExecutionHandler implementations. This follows SOLID principles:
    
    - Single Responsibility: Only handles iteration
    - Open/Closed: New execution modes via new handlers
    - Dependency Inversion: Depends on ExecutionHandler abstraction
    
    The iterator coordinates between:
    - Strategy: Provides next steps to take
    - ExecutionHandler: Handles action execution policy
    - History: Maintains execution state
    
    Example:
        # Create handler for execution policy
        handler = ExecutionHandlerFactory.create(
            ExecutionMode.AUTO, 
            action_executor
        )
        
        # Create iterator with clean dependencies
        iterator = AgentIterator(
            strategy=react_strategy,
            execution_handler=handler,
            stream=stream_callback
        )
        
        # Iterate through execution steps
        for step in iterator:
            if step.type == StepType.FINISH:
                print("Agent finished:", step.data.output)
                break
    """

    def __init__(
            self,
            *,
            strategy: AgentStrategy,
            execution_handler: ExecutionHandler,
            stream: Optional[Callable[[Dict[str, Any]], None]] = None,
            on_action: Optional[Callable[[AgentAction], bool]] = None,
    ):
        """
        Initialize clean agent iterator.
        
        Args:
            strategy: Agent strategy for decision-making
            execution_handler: Handler for execution policy (auto/guided/etc)
            stream: Optional streaming callback for events
            on_action: Optional callback to approve/reject actions
        """
        self.strategy = strategy
        self.execution_handler = execution_handler
        self.stream = stream or (lambda x: None)
        self.on_action = on_action

        # Execution state (iterator's core responsibility)
        self.messages: List[ChatMessage] = []
        self.history: List[AgentStep] = []
        self._finished = False
        self._iteration_count = 0

        # Queue for steps waiting to be yielded
        self._step_queue: List[AgentStep] = []

    def __iter__(self) -> Iterator[AgentStep]:
        """Return iterator interface."""
        return self

    def __next__(self) -> AgentStep:
        """
        Get next step in agent execution.
        
        Core iteration logic:
        1. Check for queued steps from previous iteration
        2. Check if execution is finished
        3. Get next steps from strategy
        4. Process each step based on type
        5. Delegate action handling to execution handler
        6. Return next step to caller
        
        Returns:
            Next AgentStep in execution
            
        Raises:
            StopIteration: When execution is complete
        """
        self._iteration_count += 1

        # First, check if we have queued steps from previous processing
        if self._step_queue:
            step = self._step_queue.pop(0)
            return step

        # Check if we've reached the end
        if self._finished:
            raise StopIteration

        # Check if execution handler is ready for next iteration
        if not self.execution_handler.is_ready_for_next_iteration():
            # For guided mode, this means we're waiting for action confirmations
            # We should not proceed to get new steps from strategy
            raise StopIteration

        # Check if strategy wants to continue
        if not self.strategy.should_continue(self.history):
            self._finished = True
            raise StopIteration

        try:
            # Get next steps from strategy
            steps = self.strategy.think(self.messages)
            print(f"⚡ [AGENT] Processing {len(steps)} steps: {[step.type.value for step in steps]}")

            # Update conversation messages with assistant responses
            self._update_conversation_messages(steps)

            # Process each step
            actions_to_handle = []

            for step in steps:

                # Add to history and emit event
                self.history.append(step)
                self._emit_step_event(step)

                if step.type == StepType.ACTION:
                    # Validate action with callback
                    action = step.data
                    if self.on_action and not self.on_action(action):
                        print(f"❌ [AGENT] Action {action.tool} rejected by policy")
                        # Create rejection step and queue it
                        rejection_step = self._create_rejection_step(action, "Rejected by policy")
                        self._step_queue.append(rejection_step)
                        continue

                    # Collect action for batch handling
                    actions_to_handle.append(action)

                elif step.type == StepType.FINISH:
                    print(f"✅ [AGENT] Execution finished")
                    self._finished = True
                    # Queue FINISH step for consistent ordering
                    self._step_queue.append(step)

                elif step.type == StepType.ERROR:
                    print(f"❌ [AGENT] Error step encountered")
                    # Queue ERROR step for consistent ordering
                    self._step_queue.append(step)

                elif step.type == StepType.PLANNING:
                    # Queue planning step for yielding
                    self._step_queue.append(step)

            # Handle collected actions via execution handler
            if actions_to_handle:
                print(f"🔧 [TOOLS] Executing {len(actions_to_handle)} actions")

                # Delegate to execution handler (Strategy pattern)
                for result_step in self.execution_handler.handle_actions(actions_to_handle):
                    # Add handler results to history and queue for yielding
                    self.history.append(result_step)
                    self._emit_step_event(result_step)
                    self._step_queue.append(result_step)
                    
                    # Append TOOL message to conversation immediately for correct ordering
                    if result_step.type == StepType.OBSERVATION:
                        from mas.elements.llms.common.chat.message import ChatMessage, Role
                        obs = result_step.data  # AgentObservation
                        tool_message = ChatMessage(
                            role=Role.TOOL,
                            content=str(obs.output) if obs.success else f"Error: {obs.error}",
                            tool_call_id=obs.action_id
                        )
                        self.messages.append(tool_message)

            # Return next queued step if available
            if self._step_queue:
                step = self._step_queue.pop(0)
                return step

            # If no steps to return, continue to next iteration
            return self.__next__()

        except Exception as e:
            error_step = AgentStep(
                StepType.ERROR,
                e,
                metadata={"error_type": type(e).__name__, "iteration": self._iteration_count}
            )
            self.history.append(error_step)
            self._emit_step_event(error_step)
            return error_step

    def _update_conversation_messages(self, steps: List[AgentStep]) -> None:
        """Update conversation messages with assistant responses."""
        for step in steps:
            if step.type == StepType.PLANNING and isinstance(step.data, ChatMessage):
                if step.data.role == Role.ASSISTANT:
                    self.messages.append(step.data)

    def _emit_step_event(self, step: AgentStep) -> None:
        """Emit step event via stream callback."""
        # try:
        #     event = {
        #         "type": f"agent_{step.type.value}",
        #         "data": self._serialize_step_data(step.data),
        #         "timestamp": step.timestamp,
        #         "metadata": step.metadata or {}
        #     }
        #     self.stream(event)
        # except Exception as e:
        #     pass
        pass

    def _serialize_step_data(self, data: Any) -> Dict[str, Any]:
        """Serialize step data for streaming."""
        if isinstance(data, ChatMessage):
            return {
                "role": data.role.value,
                "content": data.content,
                "tool_calls": [
                    {
                        "name": tc.name,
                        "args": tc.args,
                        "tool_call_id": tc.tool_call_id
                    }
                    for tc in (data.tool_calls or [])
                ]
            }
        elif isinstance(data, AgentAction):
            return {
                "tool": data.tool,
                "tool_input": data.tool_input,
                "action_id": data.id
            }
        elif isinstance(data, AgentObservation):
            return {
                "tool": data.tool,
                "output": data.output,
                "success": data.success,
                "execution_time": data.execution_time,
                "error": str(data.error) if data.error else None
            }
        elif isinstance(data, AgentFinish):
            return {
                "output": data.output,
                "reasoning": data.reasoning
            }
        else:
            return {"data": str(data)}

    def _create_rejection_step(self, action: AgentAction, reason: str) -> AgentStep:
        """Create a step representing action rejection."""
        rejection_obs = AgentObservation(
            action_id=action.id,
            tool=action.tool,
            output=None,
            success=False,
            error=Exception(reason),
            execution_time=0.0
        )

        # Add to execution handler's observations for proper tracking
        self.execution_handler.observations.append(rejection_obs)

        return AgentStep(
            StepType.OBSERVATION,
            rejection_obs,
            metadata={"rejected": True, "reason": reason}
        )

    # Properties for backward compatibility and access to state
    @property
    def observations(self) -> List[AgentObservation]:
        """Get all observations from execution handler."""
        return self.execution_handler.get_observations()

    @property
    def finished(self) -> bool:
        """Check if iteration is finished."""
        return self._finished

    # Compatibility methods for guided mode testing
    def get_pending_actions(self) -> List[AgentAction]:
        """Get list of actions pending confirmation (GUIDED mode only)."""

        if isinstance(self.execution_handler, GuidedExecutionHandler):
            return self.execution_handler.get_pending_actions()
        else:
            return []

    def confirm_action(self, action_id: str, execute: bool = True) -> Optional[AgentStep]:
        """
        Confirm and optionally execute a pending action (GUIDED mode only).
        
        Args:
            action_id: ID of action to confirm
            execute: Whether to execute the action immediately
            
        Returns:
            Observation step if executed, None otherwise
        """
        if isinstance(self.execution_handler, GuidedExecutionHandler):
            return self.execution_handler.confirm_action(action_id, execute)
        else:
            return None

    @property
    def pending_actions(self) -> List[AgentAction]:
        """Get pending actions (compatibility property)."""
        return self.get_pending_actions()
