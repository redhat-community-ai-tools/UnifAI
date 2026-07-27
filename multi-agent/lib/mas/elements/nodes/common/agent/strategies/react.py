"""
ReAct (Reasoning + Acting) agent strategy.

This module implements the ReAct pattern where agents interleave reasoning
and action in a loop:
1. Observe current state
2. Think about what to do next (reasoning)
3. Take action or provide final answer
4. Observe results and repeat

The ReAct strategy is effective for many tasks because it allows the agent
to reason about each step and adapt based on observations.

Reference:
    "ReAct: Synergizing Reasoning and Acting in Language Models"
    https://arxiv.org/abs/2210.03629
"""

import time
from typing import List, Tuple, Callable, Optional, Dict, Any
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.tools.common.base_tool import BaseTool
from ..primitives import AgentAction, AgentObservation, AgentFinish, AgentStep, StepType, SystemError
from ..parsers import OutputParser, ParseError, ParseErrorType
from .base import AgentStrategy
from ..constants import StrategyDefaults, SystemPrompts, StrategyType


class ReActStrategy(AgentStrategy):
    """
    ReAct strategy implementation.
    
    Implements the Reasoning + Acting pattern where the agent:
    1. Analyzes the current situation
    2. Reasons about what action to take
    3. Takes action using available tools
    4. Observes results
    5. Repeats until task is complete
    
    Features:
    - Interleaved reasoning and acting
    - Error handling with reflection
    - Configurable system prompts
    - Step-by-step execution tracking
    
    Example:
        strategy = ReActStrategy(
            llm_chat=node._chat,
            parser=ToolCallParser(),
            max_steps=10,
            system_prompt_template=custom_template
        )
    """

    def __init__(
            self,
            *,
            llm_chat: Callable[[List[ChatMessage], List[BaseTool]], ChatMessage],
            tools: List[BaseTool],
            parser: OutputParser,
            max_steps: int = StrategyDefaults.MAX_STEPS,
            system_prompt_template: Optional[str] = None,
            min_reasoning_length: int = StrategyDefaults.MIN_REASONING_LENGTH,
            system_message: Optional[str] = None
    ):
        """
        Initialize ReAct strategy.
        
        Args:
            llm_chat: Function to call LLM with messages and tools
            tools: All available tools for this strategy
            parser: Output parser for LLM responses
            max_steps: Maximum reasoning steps before stopping
            system_prompt_template: Custom system prompt (optional)
            min_reasoning_length: Minimum characters expected in reasoning
            system_message: System message from node (takes priority)
        """
        super().__init__(
            llm_chat=llm_chat,
            tools=tools,
            parser=parser,
            max_steps=max_steps,
            system_message=system_message
        )
        self.min_reasoning_length = min_reasoning_length
        self.system_prompt_template = system_prompt_template or SystemPrompts.REACT_DEFAULT

    @property
    def strategy_name(self) -> str:
        """Return the name of this strategy."""
        return StrategyType.REACT.value

    def get_tools_for_phase(self, phase: str, context: Dict[str, Any] = None) -> List[BaseTool]:
        """
        ReAct uses all tools in all phases.
        
        Args:
            phase: Current phase (always StrategyType.REACT.value for this strategy)
            context: Optional context (unused)
            
        Returns:
            All available tools
        """
        return list(self.all_tools.values())

    def think(
            self,
            messages: List[ChatMessage]
    ) -> List[AgentStep]:
        """
        ReAct thinking with error handling.
        
        Process:
        1. Build context from conversation history
        2. Get LLM response and parse
        3. On success: return steps
        4. On error: append feedback to messages and return error step
        
        Args:
            messages: Mutable conversation history. Strategy may modify this list
                     (e.g., adding error feedback).
            
        Returns:
            List of steps (planning + action/finish, or error)
        """
        try:
            # Build context
            context = self.build_context(messages)
            tools = self.get_tools_for_phase(StrategyType.REACT.value)

            # Get LLM response
            start_time = time.time()
            response = self.llm_chat(context, tools)
            reasoning_time = time.time() - start_time

            # Parse response
            result = self.parser.parse(response)
            
            # Validate reasoning only for final answers (AgentFinish)
            # Tool calls (List[AgentAction]) don't need reasoning validation
            if isinstance(result, AgentFinish):
                self._validate_reasoning(response)

            # Success - reset error count
            self._error_count = 0

            # Return appropriate steps
            steps = self._create_success_steps(response, result, reasoning_time)

        except ParseError as e:
            # Add error feedback to messages
            from ..constants import ErrorMessages
            error_feedback = ChatMessage(
                role=Role.SYSTEM,
                content=ErrorMessages.get_parse_error_guidance(e)
            )
            messages.append(error_feedback)
            
            steps = [self._create_error_step(e, "parse_error")]

        except Exception as e:
            import traceback
            traceback.print_exc()
            
            error_feedback = ChatMessage(
                role=Role.SYSTEM,
                content=f"System error: {e}. Try a different approach."
            )
            messages.append(error_feedback)
            
            steps = [self._create_error_step(e, "strategy_error")]

        self.increment_step_count()
        return steps

    def should_continue(self, history: List[AgentStep]) -> bool:
        """
        Check if ReAct strategy should continue.
        
        Stopping conditions:
        - Maximum steps reached
        - Terminal step encountered (finish/unrecoverable error)
        - Too many consecutive errors
        
        Args:
            history: Complete execution history
            
        Returns:
            True if execution should continue
        """
        # Check for terminal steps
        if history and history[-1].is_terminal:
            return False

        # Check step limit
        if self._step_count >= self.max_steps:
            return False

        # Check for too many consecutive errors
        consecutive_errors = 0
        for step in reversed(history):
            if step.is_error():
                consecutive_errors += 1
            else:
                break

        if consecutive_errors >= 3:  # Configurable threshold
            return False

        return True

    def build_context(
            self,
            messages: List[ChatMessage]
    ) -> List[ChatMessage]:
        """
        Build context for ReAct strategy.
        
        Messages already include TOOL messages in correct order (added by iterator).
        
        Args:
            messages: Complete conversation history including USER, ASSISTANT,
                     TOOL, and SYSTEM messages
            
        Returns:
            Complete context for LLM
        """
        context = self._build_base_context(messages)
        # Messages already include TOOL messages - no need to re-process
        return context

    def _validate_reasoning(self, response: ChatMessage) -> None:
        """
        Validate the quality of reasoning in final answers.
        
        Checks that the LLM provided sufficient reasoning when giving
        a final answer (AgentFinish). Tool calls don't need this validation
        since their reasoning is implicit in tool selection and arguments.
        
        Args:
            response: LLM response containing final answer to validate
            
        Raises:
            ParseError: If reasoning is insufficient for final answer
        """
        content = response.content or ""

        # Check minimum length
        if len(content) < self.min_reasoning_length:
            raise ParseError(
                f"Reasoning too short ({len(content)} chars, min {self.min_reasoning_length})",
                ParseErrorType.VALIDATION_ERROR,
                content,
                recoverable=True
            )

        # Could add more sophisticated reasoning quality checks here
        # - Presence of reasoning keywords
        # - Analysis of current situation
        # - Clear action justification

    def _build_base_context(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """Build base context with system message."""
        context = list(messages)

        system_content = self.system_message or self.system_prompt_template
        if context and context[0].role == Role.SYSTEM:
            context[0] = ChatMessage(role=Role.SYSTEM, content=system_content)
        else:
            context.insert(0, ChatMessage(role=Role.SYSTEM, content=system_content))

        return context


    def _create_success_steps(self, response: ChatMessage, result, reasoning_time: float) -> List[AgentStep]:
        """Create steps for successful execution."""
        
        steps = [
            AgentStep(
                type=StepType.PLANNING,
                data=response,
                metadata={
                    "strategy": StrategyType.REACT.value,
                    "step_count": self._step_count,
                    "reasoning_time": reasoning_time,
                    "reasoning_content": response.content
                }
            )
        ]

        if isinstance(result, list):
            action_steps = [
                AgentStep(
                    type=StepType.ACTION,
                    data=action,
                    metadata={
                        "strategy": StrategyType.REACT.value,
                        "reasoning": response.content or "",
                        "step_count": self._step_count
                    }
                )
                for action in result
            ]
            steps.extend(action_steps)
        else:
            steps.append(AgentStep(
                type=StepType.FINISH,
                data=result,
                metadata={
                    "strategy": StrategyType.REACT.value,
                    "reasoning": response.content or "",
                    "step_count": self._step_count
                }
            ))

        return steps

    def _create_error_step(self, error: Exception, error_type: str) -> AgentStep:
        """Create clean error step."""
        return AgentStep(
            type=StepType.ERROR,
            data=error,
            metadata={
                "strategy": StrategyType.REACT.value,
                "error_type": error_type,
                "step_count": self._step_count,
                "recoverable": getattr(error, 'recoverable', error_type == "parse_error")
            }
        )
