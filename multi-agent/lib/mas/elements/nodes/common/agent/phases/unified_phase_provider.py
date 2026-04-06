"""
Core phase provider interface.

This is the contract that strategies depend on. All phase providers
must implement the abstract methods; optional methods have no-op defaults
so the strategy NEVER needs hasattr checks.
"""

from typing import List, Optional, Any
from abc import ABC, abstractmethod
from mas.elements.tools.common.base_tool import BaseTool
from .phase_protocols import PhaseState

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mas.elements.llms.common.chat.message import ChatMessage


class PhaseProvider(ABC):
    """
    Complete contract between Strategy and phase management.

    Every method the strategy calls is defined here — either abstract
    (subclass must implement) or with a no-op default.
    The strategy NEVER uses hasattr; every call goes through this interface.
    """

    # ==================================================================
    # REQUIRED — subclasses MUST implement
    # ==================================================================

    @abstractmethod
    def get_supported_phases(self) -> List[str]:
        """Return ordered list of phase names."""
        ...

    @abstractmethod
    def get_tools_for_phase(self, phase_name: str) -> List[BaseTool]:
        """Return tools available in the given phase."""
        ...

    @abstractmethod
    def update_phase(self, current_phase: str) -> str:
        """
        Determine the next phase from the current one.

        All internal logic (cascade, iteration limits, state-based routing)
        is the provider's responsibility. Strategy is opaque to internals.
        """
        ...

    @abstractmethod
    def can_finish_now(self, current_phase: str) -> bool:
        """
        Whether the strategy should stop iterating.

        True when the cycle is complete (terminal phase reached,
        or waiting for external events with no actionable work).
        """
        ...

    @abstractmethod
    def get_phase_context(self) -> PhaseState:
        """Get current phase context for decision making."""
        ...

    # ==================================================================
    # OPTIONAL — no-op defaults, override as needed
    # ==================================================================

    def get_initial_phase(self) -> str:
        """First phase in the system."""
        return self.get_supported_phases()[0]

    def get_terminal_phase(self) -> str:
        """Terminal (final) phase name."""
        return self.get_supported_phases()[-1]

    def is_terminal_phase(self, phase_name: str) -> bool:
        return phase_name == self.get_terminal_phase()

    def begin_iteration(self) -> None:
        """Called at the start of each think() cycle."""
        pass

    def end_iteration(self) -> None:
        """Called at the end of each think() cycle."""
        pass

    def set_phase_changed(self, changed: bool) -> None:
        """Signal whether the current iteration is a phase entry."""
        pass

    def get_dynamic_context_messages(self, phase_name: str) -> List["ChatMessage"]:
        """Dynamic context refreshed before each LLM call."""
        return []

    def get_phase_static_context(self, phase_name: str) -> List["ChatMessage"]:
        """Static context sent only on phase entry."""
        return []

    def build_focused_prompt(self, phase: str, phase_changed: bool) -> str:
        """Situation-aware focused prompt for the current phase."""
        return ""

    def build_phase_prompt(self, phase_name: str) -> str:
        """Complete system prompt section for a phase (guidance + validation)."""
        return self.get_phase_guidance(phase_name)

    def get_phase_guidance(self, phase_name: str) -> str:
        """Raw guidance text for a phase."""
        return ""

    def get_phase_validation(self, phase_name: str) -> str:
        """Validation guidance text for a phase."""
        return ""


# Backward compatibility alias
BasePhaseProvider = PhaseProvider
