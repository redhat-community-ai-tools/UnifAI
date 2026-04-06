"""
Plan and Execute agent strategy.

Phased approach:
1. Plans work and delegates REMOTE items
2. Executes LOCAL work items
3. Monitors progress and responses
4. Synthesizes results

Each phase exposes different tools to enforce clean separation of concerns.
Strategy is PHASE-AGNOSTIC — all phase knowledge lives in the PhaseProvider.
"""

import logging
from typing import List, Dict, Any, Optional, Callable

from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.tools.common.base_tool import BaseTool
from ..primitives import AgentStep, StepType, AgentFinish, AgentObservation
from ..parsers import OutputParser, ParseError
from .base import AgentStrategy
from ..constants import StrategyDefaults, StrategyType, SystemPrompts
from ..phases.unified_phase_provider import PhaseProvider

logger = logging.getLogger(__name__)


class PlanAndExecuteStrategy(AgentStrategy):
    """
    Plan and Execute strategy — SOLID compliant.

    Delegates ALL phase logic to PhaseProvider:
    - No hardcoded phase names
    - No hasattr checks — every method defined on the interface
    - No knowledge of provider internals (cascade, iteration, limits)

    Strategy responsibilities:
    - Execution flow (think → act → observe loop)
    - Tool execution coordination
    - LLM interaction
    - Step creation
    """

    def __init__(
        self,
        *,
        llm_chat: Callable[[List[ChatMessage], List[BaseTool]], ChatMessage],
        tools: List[BaseTool],
        parser: OutputParser,
        max_steps: int = StrategyDefaults.MAX_STEPS,
        system_message: Optional[str] = None,
        phase_provider: Optional[PhaseProvider] = None,
        **kwargs,
    ):
        super().__init__(
            llm_chat=llm_chat,
            tools=tools,
            parser=parser,
            max_steps=max_steps,
            system_message=system_message,
        )

        if not phase_provider:
            raise ValueError("PlanAndExecuteStrategy requires a phase_provider")
        self._phase_provider = phase_provider

        self._current_phase = self._phase_provider.get_initial_phase()
        self._phase_iterations = 0
        self._phase_changed = False

    @property
    def strategy_name(self) -> str:
        return StrategyType.PLAN_AND_EXECUTE.value

    # ------------------------------------------------------------------
    # Tool resolution
    # ------------------------------------------------------------------

    def get_tools_for_phase(self, phase: str, context: Dict[str, Any] = None) -> List[BaseTool]:
        try:
            return self._phase_provider.get_tools_for_phase(phase)
        except Exception:
            return list(self.all_tools.values())

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def think(self, messages: List[ChatMessage]) -> List[AgentStep]:
        if self._step_count == 0:
            logger.debug(
                "\n%s\nLLM INTERACTION #1 - BEGINNING ORCHESTRATION CYCLE\n"
                "Starting Phase: %s\n%s\n",
                "=" * 80, self._current_phase.upper(), "=" * 80,
            )
        else:
            logger.debug("Phase: %s", self._current_phase)

        try:
            self._phase_provider.begin_iteration()

            old_phase = self._current_phase
            self._update_phase()

            self._phase_changed = old_phase != self._current_phase
            if self._phase_changed:
                logger.debug("Phase transition: %s -> %s", old_phase, self._current_phase)
                self._phase_provider.begin_iteration()

            self._phase_provider.set_phase_changed(self._phase_changed)

            context = self.build_context(messages)
            tools = self.get_tools_for_phase(self._current_phase)

            logger.debug("[STRATEGY] Thinking in phase %s", self._current_phase)
            response = self.llm_chat(context, tools)
            result = self.parser.parse(response)

            steps = [AgentStep(StepType.PLANNING, response, metadata={
                "phase": self._current_phase,
                "iteration": self._phase_iterations,
            })]

            if isinstance(result, list):
                for action in result:
                    steps.append(AgentStep(
                        StepType.ACTION, action,
                        metadata={"phase": self._current_phase},
                    ))
            elif isinstance(result, AgentFinish):
                if self._phase_provider.can_finish_now(self._current_phase):
                    steps.append(AgentStep(StepType.FINISH, result))
                else:
                    old = self._current_phase
                    self._update_phase()
                    if self._current_phase == old:
                        terminal = self._phase_provider.get_terminal_phase()
                        logger.debug(
                            "Stuck in %s — forcing terminal phase %s",
                            old, terminal,
                        )
                        self._current_phase = terminal
                    self._phase_changed = True
                    return self.think(messages)

            self._error_count = 0
            self.increment_step_count()
            self._phase_iterations += 1

            self._phase_provider.end_iteration()

            return steps

        except ParseError as e:
            logger.warning("[STRATEGY] Parse error in phase %s: %s", self._current_phase, e)
            from ..constants import ErrorMessages
            messages.append(ChatMessage(
                role=Role.SYSTEM,
                content=ErrorMessages.get_parse_error_guidance(e),
            ))
            return [AgentStep(
                StepType.ERROR, e,
                metadata={"phase": self._current_phase, "error_type": "parse_error"},
            )]

        except Exception as e:
            import traceback
            logger.error(
                "[STRATEGY] Fatal error in phase %s: %s\nTraceback:\n%s",
                self._current_phase, e, traceback.format_exc(),
            )
            messages.append(ChatMessage(
                role=Role.SYSTEM,
                content=f"System error: {e}. Please try a different approach.",
            ))
            return [AgentStep(
                StepType.ERROR, e,
                metadata={"phase": self._current_phase, "error_type": "strategy_error"},
            )]

    # ------------------------------------------------------------------
    # Context assembly
    # ------------------------------------------------------------------

    def build_context(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """
        Build context with optimal message ordering for LLM attention.

        Order:
        1. System instructions (role + phase guidance)
        2. Phase-specific static context (e.g., adjacent nodes)
        3. Conversation history (chronological, filtered)
        4. Current state (dynamic work plan + cycle context)
        5. Focused prompt (contextual based on trigger/phase/state)
        """
        context = []

        # [1] SYSTEM: Core role + phase guidance
        system_content = self._build_phase_prompt()
        context.append(ChatMessage(role=Role.SYSTEM, content=system_content))

        # [2] SYSTEM: Phase-specific static context
        if self._phase_changed:
            static_context = self._phase_provider.get_phase_static_context(self._current_phase)
            if static_context:
                context.extend(static_context)

        # [3] USER: Conversation history (filtered on phase transition)
        static_messages = self._filter_static_messages(messages, filter_tools=self._phase_changed)
        if static_messages:
            context.extend(static_messages)

        # [4] USER: Current state (dynamic work plan + cycle context)
        dynamic_context = self._phase_provider.get_dynamic_context_messages(self._current_phase)
        context.extend(dynamic_context)

        # [5] USER: Focused prompt
        focused_prompt = self._phase_provider.build_focused_prompt(
            phase=self._current_phase,
            phase_changed=self._phase_changed,
        )
        if focused_prompt:
            context.append(ChatMessage(role=Role.USER, content=focused_prompt))

        return context

    # ------------------------------------------------------------------
    # Message filtering — tag-based
    # ------------------------------------------------------------------

    def _filter_static_messages(
        self, messages: List[ChatMessage], filter_tools: bool = True,
    ) -> List[ChatMessage]:
        """
        Filter messages for the LLM context.

        Uses tag-based filtering (additional_kwargs.dynamic_context) to
        skip dynamic context messages that will be refreshed.
        No fragile string-prefix matching.
        """
        static = []
        for msg in messages:
            # Skip tagged dynamic context (will be refreshed)
            if msg.additional_kwargs and msg.additional_kwargs.get("dynamic_context"):
                continue

            # Legacy fallback: skip old-format dynamic context messages
            content = msg.content or ""
            if content.startswith("Current Context:") or content.startswith("Current Work Plan:"):
                continue

            if filter_tools:
                if msg.role == Role.TOOL:
                    continue
                if msg.role == Role.ASSISTANT and msg.tool_calls:
                    continue

            static.append(msg)

        return static

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    def _update_phase(self) -> None:
        old_phase = self._current_phase
        self._current_phase = self._phase_provider.update_phase(self._current_phase)
        if self._current_phase != old_phase:
            self._phase_iterations = 0

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_phase_prompt(self) -> str:
        base_prompt = self.system_message or SystemPrompts.PLAN_AND_EXECUTE
        try:
            phase_guidance = self._phase_provider.build_phase_prompt(self._current_phase)
            if phase_guidance:
                return f"{base_prompt}\n\n{phase_guidance}"
        except Exception:
            try:
                fallback = self._phase_provider.get_phase_guidance(self._current_phase)
                if fallback:
                    return f"{base_prompt}\n\n{fallback}"
            except Exception:
                pass
        return base_prompt

    # ------------------------------------------------------------------
    # should_continue
    # ------------------------------------------------------------------

    def should_continue(self, history: List[AgentStep]) -> bool:
        if history and history[-1].is_terminal:
            return False
        if self._step_count >= self.max_steps:
            return False
        if self._phase_provider.can_finish_now(self._current_phase):
            return False
        return True
