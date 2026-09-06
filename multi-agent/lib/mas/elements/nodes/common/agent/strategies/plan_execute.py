"""
Plan and Execute agent strategy.

This strategy implements a phased approach where the agent:
1. Plans work by creating/updating a WorkPlan
2. Allocates work items to local/remote execution
3. Executes local work items
4. Monitors progress and responses
5. Synthesizes results

Each phase exposes different tools to enforce clean separation of concerns.
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.tools.common.base_tool import BaseTool
from ..primitives import AgentStep, StepType, AgentFinish, AgentObservation
from ..parsers import OutputParser, ParseError
from .base import AgentStrategy
from ..constants import (
    StrategyDefaults, StrategyType, SystemPrompts, ExecutionPhase
)
from ..phases.phase_protocols import PhaseState, WorkPlanStatus
from ..phases.unified_phase_provider import PhaseProvider  # Uses PhaseProvider abstraction

logger = logging.getLogger(__name__)


class PlanAndExecuteStrategy(AgentStrategy):
    """
    Plan and Execute strategy - SOLID compliant.
    
    Delegates ALL phase logic to PhaseProvider:
    - No hardcoded phase names
    - No knowledge of provider internals (cascade, iteration, limits)
    - No interpretation of provider implementation details
    
    Strategy responsibilities:
    - Execution flow (think → act → observe loop)
    - Tool execution coordination
    - LLM interaction
    - Step creation
    
    Provider responsibilities:
    - Phase definitions and transitions
    - Cascade logic (if any)
    - Iteration tracking (if any)
    - All phase-specific logic
    """
    
    def __init__(
        self,
        *,
        llm_chat: Callable[[List[ChatMessage], List[BaseTool]], ChatMessage],
        tools: List[BaseTool],
        parser: OutputParser,
        max_steps: int = StrategyDefaults.MAX_STEPS,
        system_message: Optional[str] = None,
        max_planning_iterations: int = 3,
        max_allocation_iterations: int = 3,
        phase_provider: Optional[PhaseProvider] = None
    ):
        """
        Initialize Plan and Execute strategy.
        
        Args:
            llm_chat: Function to call LLM with messages and tools
            tools: All available tools for this strategy (fallback)
            parser: Output parser for LLM responses
            max_steps: Maximum total steps before stopping
            system_message: System message from node (takes priority)
            max_planning_iterations: Max iterations in planning phase
            max_allocation_iterations: Max iterations in allocation phase
            phase_provider: Unified provider for all phase-related concerns
        """
        super().__init__(
            llm_chat=llm_chat,
            tools=tools,
            parser=parser,
            max_steps=max_steps,
            system_message=system_message
        )
        
        self.max_planning_iterations = max_planning_iterations
        self.max_allocation_iterations = max_allocation_iterations
        self._phase_iterations = 0
        self._no_progress_count = 0
        
        # Store phase provider (required)
        if not phase_provider:
            raise ValueError("PlanAndExecuteStrategy requires a phase_provider")
        self._phase_provider = phase_provider
        
        # Get initial phase from provider (NOT hardcoded)
        self._current_phase = self._phase_provider.get_initial_phase()
        
        # Track phase transitions for filtering logic
        self._previous_phase = None  # Track last phase for comparison
        self._phase_changed = False  # Flag indicating phase transition
    
    @property
    def strategy_name(self) -> str:
        """Return the name of this strategy."""
        return StrategyType.PLAN_AND_EXECUTE.value
    
    def get_tools_for_phase(self, phase: str, context: Dict[str, Any] = None) -> List[BaseTool]:
        """
        Get tools to expose for current phase.
        
        The strategy is agnostic to tool types - it delegates to the
        phase tool provider injected by the node.
        
        Args:
            phase: Current execution phase (string for base class compatibility)
            context: Optional context (unused, for future extensibility)
            
        Returns:
            List of tools appropriate for this phase
        """
        # Use phase provider to get tools (phase provider handles string/enum conversion)
        try:
            tools = self._phase_provider.get_tools_for_phase(phase)
            return tools
        except Exception as e:
            # Fallback to all tools
            pass
        
        # Fallback to all tools if no provider or invalid phase
        all_tools = list(self.all_tools.values())
        return all_tools
    
    def think(
        self,
        messages: List[ChatMessage]
    ) -> List[AgentStep]:
        """
        Generate next steps based on current phase and state.
        
        Implements phase transitions and appropriate tool exposure.
        Each phase may iterate multiple times before transitioning.
        
        Args:
            messages: Mutable conversation history. Strategy may modify this list
                     (e.g., clearing on phase transitions, adding error feedback).
            
        Returns:
            List of steps to execute
        """
        if self._step_count == 0:
            logger.info("llm.interaction_start", extra={"phase": self._current_phase, "interaction_number": 1, "detail": "beginning_orchestration_cycle"})
        else:
            logger.debug("agent.step", extra={"phase": self._current_phase, "action": "think"})
        
        try:
            # Store current phase before update
            old_phase = self._current_phase
            
            # Determine current phase based on context
            self._update_phase()
            
            # Detect phase transition
            self._phase_changed = (old_phase != self._current_phase)
            
            # Phase transition detected
            if self._phase_changed:
                logger.debug("phase.transition", extra={"from_phase": old_phase, "to_phase": self._current_phase})
                # Note: Messages will be filtered to clean slate in build_context()
            
            # Build phase-specific context
            context = self.build_context(messages)
            
            # Get phase-appropriate tools
            tools = self.get_tools_for_phase(self._current_phase)
            
            # Get LLM response
            logger.debug("llm.interaction_start", extra={"phase": self._current_phase, "action": "think"})
            response = self.llm_chat(context, tools)
            
            # Parse response
            result = self.parser.parse(response)
            
            # Create steps
            steps = [AgentStep(StepType.PLANNING, response, metadata={
                "phase": self._current_phase,
                "iteration": self._phase_iterations
            })]
            
            # Handle parsed result
            if isinstance(result, list):
                # Tool calls - create action steps
                for action in result:
                    steps.append(AgentStep(
                        StepType.ACTION,
                        action,
                        metadata={"phase": self._current_phase}
                    ))
            elif isinstance(result, AgentFinish):
                # Agent wants to finish - ask provider if we can
                can_finish = self._phase_provider.can_finish_now(self._current_phase)
                
                if not can_finish:
                    # Provider says can't finish - continue (will trigger phase update)
                    # Recursive call will run _update_phase() which cascades to next phase
                    return self.think(messages)
                else:
                    # Provider allows finish
                    steps.append(AgentStep(StepType.FINISH, result))
            
            # Success - reset error count
            self._error_count = 0
            self.increment_step_count()
            self._phase_iterations += 1
            
            return steps
            
        except ParseError as e:
            # Add error feedback to messages for next iteration
            logger.warning("llm.parse_error", extra={"phase": self._current_phase, "error": str(e)})
            
            from ..constants import ErrorMessages
            error_feedback = ChatMessage(
                role=Role.SYSTEM,
                content=ErrorMessages.get_parse_error_guidance(e)
            )
            messages.append(error_feedback)
            
            # Return ERROR step - iterator will retry automatically
            return [AgentStep(
                StepType.ERROR,
                e,
                metadata={
                    "phase": self._current_phase,
                    "error_type": "parse_error"
                }
            )]
        
        except Exception as e:
            # Fatal strategy error
            import traceback
            logger.error("agent.step", extra={"phase": self._current_phase, "error_type": "strategy_error", "error": str(e), "traceback": traceback.format_exc()})
            
            error_feedback = ChatMessage(
                role=Role.SYSTEM,
                content=f"System error: {e}. Please try a different approach."
            )
            messages.append(error_feedback)
            
            return [AgentStep(
                StepType.ERROR,
                e,
                metadata={
                    "phase": self._current_phase,
                    "error_type": "strategy_error"
                }
            )]
    
    def build_context(
        self,
        messages: List[ChatMessage]
    ) -> List[ChatMessage]:
        """
        Build context with optimal message ordering for LLM performance.
        
        Strategy is PHASE-AGNOSTIC - delegates all phase-specific decisions
        to the PhaseProvider.
        
        Filtering logic:
        - If phase changed: Filter to clean slate (USER messages only)
        - If same phase: Keep all messages (including TOOL calls for continuity)
        
        Order optimized for LLM attention patterns:
        1. System instructions (role + phase guidance)
        2. Phase-specific static context (e.g., adjacent nodes)
        3. Conversation history (chronological, filtered)
        4. Current state (dynamic work plan + cycle context)
        5. Focused prompt (contextual based on trigger/phase/state)
        
        Args:
            messages: Complete conversation history including USER, ASSISTANT,
                     TOOL, and SYSTEM messages
            
        Returns:
            Complete context for LLM
        """
        context = []
        
        # [1] SYSTEM: Core role + phase guidance
        system_content = self._build_phase_prompt()
        if self.system_message:
            system_content = f"{self.system_message}\n\n{system_content}"
        
        context.append(ChatMessage(role=Role.SYSTEM, content=system_content))
        
        # [2] SYSTEM: Phase-specific static context (adjacent nodes, etc.)
        # Provider decides what static context is needed for this phase
        static_context = self._get_phase_static_context()
        if static_context:
            context.extend(static_context)
        
        # [3] USER: Conversation history (filtered based on phase transition)
        static_messages = self._filter_static_messages(messages, filter_tools=self._phase_changed)
        if static_messages:
            context.extend(static_messages)
        
        # [4] USER: Current state (dynamic work plan + cycle context)
        if hasattr(self._phase_provider, 'get_dynamic_context_messages'):
            dynamic_context = self._phase_provider.get_dynamic_context_messages(
                self._current_phase
            )
            context.extend(dynamic_context)
        
        # [5] USER: Focused prompt (contextual based on situation)
        # Provider knows what the LLM should focus on for THIS phase iteration
        focused_prompt = self._get_focused_prompt()
        if focused_prompt:
            context.append(ChatMessage(
                role=Role.USER,
                content=focused_prompt
            ))
        
        return context
    
    def _get_phase_static_context(self) -> List[ChatMessage]:
        """
        Get phase-specific static context from provider.
        
        Strategy doesn't know what context each phase needs.
        Provider decides (e.g., adjacent nodes for ALLOCATION/MONITORING).
        
        Returns:
            List of SYSTEM messages with static reference material
        """
        if hasattr(self._phase_provider, 'get_phase_static_context'):
            return self._phase_provider.get_phase_static_context(self._current_phase)
        return []
    
    def _get_focused_prompt(self) -> Optional[str]:
        """
        Get focused prompt from provider.
        
        Provider knows the current situation (trigger, phase, state)
        and can build appropriate prompt.
        
        Returns:
            Focused prompt string or None
        """
        if hasattr(self._phase_provider, 'build_focused_prompt'):
            return self._phase_provider.build_focused_prompt(
                phase=self._current_phase,
                phase_changed=self._phase_changed
            )
        return None
    
    def _filter_static_messages(
        self, 
        messages: List[ChatMessage],
        filter_tools: bool = True
    ) -> List[ChatMessage]:
        """
        Filter messages to only include truly static ones.
        
        Filtering behavior controlled by filter_tools parameter:
        
        When filter_tools=True (phase transition):
            Filters out:
            1. Workspace/workplan messages (replaced by dynamic context)
            2. TOOL messages (tool execution results from previous phase)
            3. ASSISTANT messages with tool_calls (internal planning from previous phase)
            
            Keeps:
            - USER messages (public conversation)
            - ASSISTANT messages without tool_calls (final text responses)
            - SYSTEM messages (if any in history)
        
        When filter_tools=False (same phase continuation):
            Only filters workspace/workplan messages (replaced by dynamic context)
            Keeps all other messages including TOOL calls for continuity
        
        Args:
            messages: Original messages from orchestrator
            filter_tools: Whether to filter tool messages (True on phase transition)
            
        Returns:
            Filtered list of static messages
        """
        if not hasattr(self._phase_provider, 'get_dynamic_context_messages'):
            # No dynamic context support, return all messages
            return list(messages)
        
        static = []
        for msg in messages:
            content = msg.content or ""
            
            # Always skip workspace/workplan messages (will be refreshed)
            if content.startswith("Current Context:") or content.startswith("Current Work Plan:"):
                continue
            
            # Conditional: Only filter tools on phase transitions
            if filter_tools:
                # Skip TOOL messages (tool execution results from previous phase)
                if msg.role == Role.TOOL:
                    continue
                
                # Skip ASSISTANT messages with tool_calls (internal tool planning from previous phase)
                if msg.role == Role.ASSISTANT and msg.tool_calls:
                    continue
            
            # Keep this message
            static.append(msg)
        
        return static
    
    def should_continue(self, history: List[AgentStep]) -> bool:
        """
        Check if strategy should continue execution.
        
        Stops when:
        - Maximum steps reached
        - Terminal step encountered
        - No progress for multiple iterations
        - Provider says we can finish (e.g., waiting for responses, work complete)
        
        Args:
            history: Execution history
            
        Returns:
            True if should continue
        """
        # Check for terminal steps
        if history and history[-1].is_terminal:
            return False
        
        # Check step limit
        if self._step_count >= self.max_steps:
            return False
        
        # Check for no progress
        if self._no_progress_count > 3:
            return False
        
        # Ask provider if we can finish (handles all orchestrator-specific logic)
        # This covers:
        # - Work complete (all items DONE/FAILED)
        # - Waiting for responses with no actionable work
        # - Terminal phases (SYNTHESIS)
        if self._phase_provider.can_finish_now(self._current_phase):
            return False
        
        return True
    
    def _update_phase(self) -> None:
        """
        Update phase using provider.
        
        Provider is completely opaque - strategy doesn't know:
        - If cascade happens
        - How many transitions occur
        - If iteration limits are checked
        - Any other internal logic
        
        Just: "I'm in phase X" → Provider → "Now in phase Y"
        """
        old_phase = self._current_phase
        
        # Provider returns new phase (all logic internal)
        self._current_phase = self._phase_provider.update_phase(
            current_phase=self._current_phase,
            observations=[]  # Not used by provider
        )
        
        # Only reset iteration count if phase actually changed
        if self._current_phase != old_phase:
            self._phase_iterations = 0
    
    def _should_transition_phase(self, observations: List[AgentObservation]) -> bool:
        """
        Determine if we should transition to the next phase.
        
        Now uses work plan state instead of blind iteration counting.
        Phase transitions are handled by _update_phase() based on actual state.
        """
        # Phase transitions are now handled by _update_phase() 
        # based on work plan state, not iteration counting
        return False
    
    def _clear_phase_messages(self, messages: List[ChatMessage]) -> None:
        """
        Clear phase-specific messages.
        
        Strategy logic: Keep USER messages (original request context),
        clear ASSISTANT/TOOL/error-SYSTEM (previous phase execution).
        
        Args:
            messages: Mutable conversation history to modify
        """
        # Filter what to keep - only USER messages
        user_messages = [msg for msg in messages if msg.role == Role.USER]
        
        # Modify the list in place (affects iterator.messages)
        messages.clear()
        messages.extend(user_messages)
        
        logger.debug("phase.transition", extra={"detail": "cleared_phase_messages", "kept_user_messages": len(user_messages)})
    
    
    def _build_phase_prompt(self) -> str:
        """
        Build phase-specific system prompt with validation guidance.
        
        Uses the new build_phase_prompt method from BasePhaseProvider
        to include both base guidance and validation feedback.
        """
        base_prompt = self.system_message or SystemPrompts.PLAN_AND_EXECUTE
        
        # Get enhanced phase guidance (includes validation)
        try:
            phase_guidance = self._phase_provider.build_phase_prompt(self._current_phase)
            if phase_guidance:
                return f"{base_prompt}\n\n{phase_guidance}"
        except Exception as e:
            # Fallback to basic guidance
            try:
                fallback_guidance = self._phase_provider.get_phase_guidance(self._current_phase)
                if fallback_guidance:
                    return f"{base_prompt}\n\n{fallback_guidance}"
            except Exception as e2:
                pass
        
        return base_prompt
