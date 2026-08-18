"""
Core phase provider abstraction.

This is the main interface that strategies and nodes depend on.
All phase providers must implement this contract.
"""

import logging

from typing import List, Optional, Any
from abc import ABC, abstractmethod
from global_utils.utils.logging_config import emit
from mas.elements.tools.common.base_tool import BaseTool
from .phase_definition import PhaseSystem, PhaseDefinition
from .phase_protocols import PhaseState

# Import for typing - avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .models import PhaseValidationContext

logger = logging.getLogger(__name__)


class PhaseProvider(ABC):
    """
    Abstract base class for phase management.
    
    This is the core abstraction that strategies depend on.
    
    Key Contract:
    - Strategies call update_phase() and get back a phase name
    - All internal logic (cascade, iteration, limits) is provider's business
    - Strategy knows NOTHING about provider internals
    
    Uses Pydantic models for well-defined, type-safe phase management.
    """
    
    def __init__(self, tools: List[BaseTool]):
        """
        Initialize with available tools.
        
        Args:
            tools: All available tools that can be assigned to phases
        """
        self._tools = tools
        self._phase_system = self._create_phase_system()
    
    @abstractmethod
    def _create_phase_system(self) -> PhaseSystem:
        """
        Create the complete phase system for this provider.
        
        Subclasses must implement this to define their phases using
        clean Pydantic models with actual tool objects.
        
        Returns:
            PhaseSystem with all phases and their configurations
        """
        pass
    
    def get_phase_system(self) -> PhaseSystem:
        """Get the complete phase system definition."""
        return self._phase_system
    
    def get_supported_phases(self) -> List[str]:
        """Get list of phase names supported by this provider."""
        return self._phase_system.get_phase_names()
    
    def get_tools_for_phase(self, phase_name: str) -> List[BaseTool]:
        """Get actual tool objects for the given phase."""
        return self._phase_system.get_tools_for_phase(phase_name)
    
    def get_phase_guidance(self, phase_name: str) -> str:
        """Get guidance text for the given phase."""
        return self._phase_system.get_guidance_for_phase(phase_name)
    
    @abstractmethod
    def _build_validation_context(self, phase_name: str) -> "PhaseValidationContext":
        """
        Build validation context for the given phase.
        
        This is the extension point for providers to add their specific
        context data (e.g., work plan, adjacent nodes, etc.).
        
        Args:
            phase_name: Name of the phase to validate
            
        Returns:
            PhaseValidationContext with provider-specific data
        """
        pass
    
    def get_phase_validation(self, phase_name: str) -> str:
        """
        Get validation guidance for the given phase.
        
        SRP: This method is responsible only for validation concerns.
        
        Args:
            phase_name: Name of the phase to validate
            
        Returns:
            Validation guidance text, empty if no issues found
        """
        phase = self._phase_system.get_phase(phase_name)
        if not phase:
            return ""
            
        try:
            context = self._build_validation_context(phase_name)
            return phase.run_validators(context)
        except Exception as e:
            emit(logger, logging.WARNING, "phase.validate_error",
                 phase=phase_name, error=str(e))
            return ""
    
    def build_phase_prompt(self, phase_name: str) -> str:
        """
        Build complete phase prompt with base guidance and validation.
        
        SRP: This method is responsible only for composing guidance.
        
        Args:
            phase_name: Name of the phase
            
        Returns:
            Complete prompt with base guidance and validation guidance
        """
        base_guidance = self.get_phase_guidance(phase_name)
        validation_guidance = self.get_phase_validation(phase_name)
        
        if validation_guidance:
            return f"{base_guidance}\n\n{validation_guidance}"
        return base_guidance
    
    def get_dynamic_context_messages(self, phase_name: str) -> List["ChatMessage"]:
        """
        Get dynamic context messages that should be refreshed before each LLM call.
        
        This is an optional extension point for providers that have context
        that changes during execution (e.g., work plans, workspace state).
        
        Default implementation returns empty list (no dynamic context).
        Subclasses override this to provide fresh context data.
        
        Design Pattern: Mirrors get_phase_validation() pattern
        - Called before each LLM interaction
        - Provider decides what dynamic data to include
        - Strategy just assembles pieces
        - Fails gracefully (no exceptions)
        
        Args:
            phase_name: Current phase name (for phase-specific context if needed)
            
        Returns:
            List of ChatMessage objects with fresh context, empty list if none
        """
        return []
    
    @abstractmethod
    def get_phase_context(self) -> PhaseState:
        """Get current phase context - must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def decide_next_phase(
        self,
        current_phase: str,
        context: PhaseState,
        observations: List[Any]
    ) -> str:
        """
        Decide the next phase (single-step decision).
        
        This is the core state machine logic.
        May return same phase (stable) or different phase (transition).
        
        Args:
            current_phase: Current phase name
            context: Current phase state
            observations: Recent observations from execution
            
        Returns:
            Next phase name (may be same as current if stable)
        """
        pass
    
    @abstractmethod
    def update_phase(
        self,
        current_phase: str,
        observations: List[Any]
    ) -> str:
        """
        Update phase and return the new phase.
        
        This is the PRIMARY method strategies use.
        Provider handles all internal logic and returns final phase.
        
        Implementation can be:
        - Simple: Just call decide_next_phase() once
        - Complex: Cascade, iteration tracking, limits, etc. (all internal)
        
        Args:
            current_phase: Current phase name
            observations: Recent observations from execution
            
        Returns:
            Final phase name (after any internal processing)
        """
        pass
    
    @abstractmethod
    def can_finish_now(self, current_phase: str) -> bool:
        """
        Determine if the agent can finish execution now.
        
        SOLID PRINCIPLE: Strategy asks provider "can I finish?", provider decides.
        Provider has domain knowledge about work completion, phases, etc.
        Strategy just executes - doesn't know business logic.
        
        This prevents premature AgentFinish when work is incomplete.
        
        Args:
            current_phase: Current phase name
            
        Returns:
            True if agent can finish now, False if more work needed
        """
        pass
    
    # =================================================================
    # CONCRETE METHODS - Shared implementation
    # =================================================================
    
    def get_initial_phase(self) -> str:
        """
        Get the initial/starting phase for this provider.
        
        Default: First phase in the system.
        Subclasses can override for custom initial phase.
        
        Returns:
            Initial phase name
        """
        phases = self.get_supported_phases()
        if not phases:
            raise ValueError("Phase system has no phases")
        return phases[0]
    
    def is_terminal_phase(self, phase_name: str) -> bool:
        """
        Check if a phase is terminal (workflow ends here).
        
        Default: Phase that transitions only to itself.
        Subclasses should override for provider-specific logic.
        
        Args:
            phase_name: Phase name to check
            
        Returns:
            True if terminal, False otherwise
        """
        try:
            context = self.get_phase_context()
            next_phase = self.decide_next_phase(phase_name, context, [])
            return next_phase == phase_name
        except:
            return False
    
    def requires_tools(self, phase_name: str) -> bool:
        """
        Check if phase requires tools to proceed.
        
        Terminal phases typically don't require tools.
        
        Args:
            phase_name: Phase name to check
            
        Returns:
            True if tools required, False otherwise
        """
        # Terminal phases don't require tools
        if self.is_terminal_phase(phase_name):
            return False
        
        # Check if phase has tools
        tools = self.get_tools_for_phase(phase_name)
        return len(tools) > 0
    
    def get_next_phase_in_sequence(self, current_phase: str) -> Optional[str]:
        """
        Get next phase in natural sequential order (for fallback).
        
        This is the "default" progression when no state-based decision applies.
        
        Args:
            current_phase: Current phase name
            
        Returns:
            Next phase name, or None if at end or terminal
        """
        if self.is_terminal_phase(current_phase):
            return None
        
        phases = self.get_supported_phases()
        try:
            idx = phases.index(current_phase)
            if idx < len(phases) - 1:
                return phases[idx + 1]
        except ValueError:
            pass
        
        return None
    
    def validate_transition(self, from_phase: str, to_phase: str) -> bool:
        """
        Validate that a phase transition is allowed.
        
        Default: All transitions allowed.
        Subclasses can override for strict validation.
        
        Args:
            from_phase: Source phase
            to_phase: Target phase
            
        Returns:
            True if transition valid, False otherwise
        """
        return True


# Backward compatibility alias
BasePhaseProvider = PhaseProvider
