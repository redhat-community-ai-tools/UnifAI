"""
Flexible phase provider that supports custom phases.

This module provides a truly extensible phase provider system that can work
with any custom phase definitions without requiring code changes.
"""

import logging

from typing import List, Dict, Set, Any, Union
from abc import ABC, abstractmethod
from global_utils.utils.logging_config import emit
from mas.elements.tools.common.base_tool import BaseTool
from .extensible_phases import ExtensiblePhaseProvider, PhaseRegistry, PhaseSystemFactory
from .phase_protocols import PhaseState

# Forward declaration for AgentObservation
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..primitives import AgentObservation

logger = logging.getLogger(__name__)


class FlexiblePhaseProvider(ExtensiblePhaseProvider):
    """
    Flexible phase provider that works with any phase system.
    
    This provider can be configured with different phase registries
    to support completely custom workflows without code changes.
    
    Key Features:
    - Works with any PhaseRegistry
    - Supports custom phases, transitions, and tool mappings
    - Maintains SOLID principles
    - Easy to extend and customize
    """
    
    def __init__(
        self, 
        tools: List[BaseTool], 
        phase_registry: PhaseRegistry,
        node_uid: str = "flexible-node"
    ):
        """
        Initialize flexible phase provider.
        
        Args:
            tools: Available tools
            phase_registry: Registry defining the phases
            node_uid: Node identifier
        """
        super().__init__(tools, phase_registry)
        self._node_uid = node_uid
    
    def get_phase_context(self) -> PhaseState:
        """Get basic phase context."""
        from .phase_protocols import create_phase_state
        return create_phase_state(node_uid=self._node_uid)
    
    def decide_next_phase(
        self, 
        current_phase: str, 
        context: Any, 
        observations: List['AgentObservation']
    ) -> str:
        """
        Simple phase progression for flexible provider.
        
        Default implementation follows phase order in registry.
        Can be overridden for custom transition logic.
        """
        phase_names = self.get_supported_phases()
        
        # If terminal phase, stay there
        if self.is_terminal_phase(current_phase):
            return current_phase
        
        # Simple progression through phases
        try:
            current_index = phase_names.index(current_phase)
            if current_index < len(phase_names) - 1:
                next_phase = phase_names[current_index + 1]
                if self.validate_phase_transition(current_phase, next_phase):
                    return next_phase
        except (ValueError, IndexError):
            pass
        
        # Stay in current phase if no valid transition
        return current_phase


class WorkflowPhaseProvider(FlexiblePhaseProvider):
    """
    Workflow-aware phase provider with context-based transitions.
    
    This provider makes transition decisions based on work context
    and can be used with any phase system that provides work status.
    """
    
    def __init__(
        self,
        tools: List[BaseTool],
        phase_registry: PhaseRegistry, 
        context_provider: Any,
        node_uid: str = "workflow-node"
    ):
        """
        Initialize workflow phase provider.
        
        Args:
            tools: Available tools
            phase_registry: Registry defining phases
            context_provider: Provider for work context (e.g., WorkPlanService)
            node_uid: Node identifier
        """
        super().__init__(tools, phase_registry, node_uid)
        self._context_provider = context_provider
    
    def get_phase_context(self) -> Any:
        """Get rich context from context provider."""
        try:
            return self._context_provider.get_context()
        except Exception as e:
            emit(logger, logging.WARNING, "phase.validate_error",
                 error=str(e), detail="get_workflow_context")
            return super().get_phase_context()
    
    def decide_next_phase(
        self,
        current_phase: str,
        context: Any,
        observations: List['AgentObservation']
    ) -> str:
        """
        Context-aware phase transitions.
        
        Makes decisions based on work status and context.
        Falls back to simple progression if context unavailable.
        """
        try:
            # Try to use context for smart transitions
            if hasattr(context, 'work_plan_status') and context.work_plan_status:
                return self._decide_based_on_work_status(current_phase, context.work_plan_status)
        except Exception as e:
            emit(logger, logging.WARNING, "phase.transition",
                 current_phase=current_phase, error=str(e),
                 detail="context_based_transition")
        
        # Fallback to simple progression
        return super().decide_next_phase(current_phase, context, observations)
    
    def _decide_based_on_work_status(self, current_phase: str, work_status: Any) -> str:
        """
        Decide next phase based on work plan status.
        
        This method can be customized for different workflow types.
        """
        # Example logic - can be customized per workflow
        if hasattr(work_status, 'is_complete') and work_status.is_complete:
            # Find terminal phase
            for phase_name in self.get_supported_phases():
                if self.is_terminal_phase(phase_name):
                    return phase_name
        
        # Continue with current phase if no clear transition
        return current_phase


# =============================================================================
# FACTORY FOR CREATING FLEXIBLE PROVIDERS
# =============================================================================

class FlexiblePhaseProviderFactory:
    """Factory for creating flexible phase providers with different configurations."""
    
    @staticmethod
    def create_standard_provider(
        tools: List[BaseTool], 
        node_uid: str = "standard-node"
    ) -> FlexiblePhaseProvider:
        """Create provider with standard plan-and-execute phases."""
        registry = PhaseSystemFactory.create_standard_system()
        return FlexiblePhaseProvider(tools, registry, node_uid)
    
    @staticmethod
    def create_research_provider(
        tools: List[BaseTool],
        node_uid: str = "research-node"
    ) -> FlexiblePhaseProvider:
        """Create provider with research workflow phases."""
        registry = PhaseSystemFactory.create_research_system()
        return FlexiblePhaseProvider(tools, registry, node_uid)
    
    @staticmethod
    def create_custom_provider(
        tools: List[BaseTool],
        phase_registry: PhaseRegistry,
        node_uid: str = "custom-node"
    ) -> FlexiblePhaseProvider:
        """Create provider with custom phase registry."""
        return FlexiblePhaseProvider(tools, phase_registry, node_uid)
    
    @staticmethod
    def create_workflow_provider(
        tools: List[BaseTool],
        phase_registry: PhaseRegistry,
        context_provider: Any,
        node_uid: str = "workflow-node"
    ) -> WorkflowPhaseProvider:
        """Create workflow-aware provider with context-based transitions."""
        return WorkflowPhaseProvider(tools, phase_registry, context_provider, node_uid)


# =============================================================================
# ADAPTER FOR BACKWARD COMPATIBILITY
# =============================================================================

class LegacyPhaseAdapter:
    """
    Adapter to make flexible providers work with existing strategy code.
    
    This allows gradual migration from the old hard-coded system
    to the new flexible system.
    """
    
    def __init__(self, flexible_provider: FlexiblePhaseProvider):
        """
        Initialize adapter with flexible provider.
        
        Args:
            flexible_provider: The flexible provider to adapt
        """
        self._provider = flexible_provider
        self._phase_mapping = self._create_phase_mapping()
    
    def _create_phase_mapping(self) -> Dict[str, Any]:
        """Create mapping from phase names to legacy enum values."""
        # This would map custom phase names to legacy ExecutionPhase enum values
        # For now, return identity mapping
        return {name: name for name in self._provider.get_supported_phases()}
    
    def get_phase_context(self) -> Any:
        """Get phase context (adapted)."""
        return self._provider.get_phase_context()
    
    def get_tools_for_phase(self, phase: Any) -> List[BaseTool]:
        """Get tools for phase (adapted)."""
        phase_name = str(phase) if hasattr(phase, 'value') else str(phase)
        return self._provider.get_tools_for_phase(phase_name)
    
    def get_phase_guidance(self, phase: Any) -> str:
        """Get phase guidance (adapted)."""
        phase_name = str(phase) if hasattr(phase, 'value') else str(phase)
        return self._provider.get_phase_guidance(phase_name)
    
    def decide_next_phase(self, current_phase: Any, phase_state: Any, observations: List[Any]) -> Any:
        """Decide next phase (adapted)."""
        current_name = str(current_phase) if hasattr(current_phase, 'value') else str(current_phase)
        next_name = self._provider.decide_next_phase(current_name, phase_state, observations)
        
        # Return the same type as input (for compatibility)
        if hasattr(current_phase, 'value'):
            # Try to find matching enum value
            for phase_name in self._provider.get_supported_phases():
                if phase_name == next_name:
                    return current_phase.__class__(next_name)
        
        return next_name
