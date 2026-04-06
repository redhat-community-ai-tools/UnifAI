"""
Phase state machine for the orchestrator.

Thin dispatcher: cascade loop + iteration limits.
ALL routing decisions are delegated to Phase.decide_next().
"""

import logging
from typing import Any, Optional

from .registry import OrchestratorPhaseRegistry
from .models import PhaseIterationLimits, PhaseIterationState

logger = logging.getLogger(__name__)


class PhaseMachine:
    """
    Pure cascade loop + iteration-limit enforcement.

    Delegates every routing decision to the Phase object itself
    via phase.decide_next(status) and phase.on_limit_exceeded(status).
    """

    def __init__(
        self,
        registry: OrchestratorPhaseRegistry,
        limits: Optional[PhaseIterationLimits] = None,
        max_cascade: int = 10,
    ):
        self._registry = registry
        self._limits = limits or PhaseIterationLimits()
        self._state = PhaseIterationState()
        self._max_cascade = max_cascade

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_phase(self, current: str, status: Any) -> str:
        """Increment, cascade to a stable phase, reset on transition."""
        self._state = self._state.increment(current)
        final = self._cascade(current, status)
        if final != current:
            self._state = self._state.reset(current)
        return final

    # ------------------------------------------------------------------
    # Core cascade
    # ------------------------------------------------------------------

    def _cascade(self, start: str, status: Any) -> str:
        visited = {start}
        current = start
        for _ in range(self._max_cascade):
            nxt = self._decide(current, status)
            if nxt == current:
                return current
            if nxt in visited:
                logger.warning(
                    "Cycle detected in cascade (%s -> %s), forcing terminal",
                    current, nxt,
                )
                return self._registry.terminal().name
            visited.add(nxt)
            current = nxt
        logger.warning("Max cascade transitions reached from %s", start)
        return current

    def _decide(self, current: str, status: Any) -> str:
        phase = self._registry.get(current)
        if not phase or not status:
            return self._registry.initial().name
        if self._is_exceeded(current):
            logger.warning("Phase limit exceeded: %s", current)
            return phase.on_limit_exceeded(status)
        return phase.decide_next(status)

    def _is_exceeded(self, phase_name: str) -> bool:
        return self._state.is_exceeded(phase_name, self._limits)
