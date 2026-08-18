"""
Simple, clean phase provider system.

Each provider simply implements the abstract methods to define its own phases.
No over-engineering, no unnecessary abstractions.
"""

import logging

from typing import List, Set, Dict, Any
from abc import ABC, abstractmethod
from global_utils.utils.logging_config import emit
from mas.elements.tools.common.base_tool import BaseTool
from .phase_protocols import PhaseState

# Forward declaration for AgentObservation
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..primitives import AgentObservation

logger = logging.getLogger(__name__)


class PhaseProvider(ABC):
    """
    Simple abstract base for phase providers.
    
    Each provider defines its own phases by implementing these methods.
    No complex registries or definitions needed - just implement the methods.
    """
    
    def __init__(self, tools: List[BaseTool]):
        """
        Initialize with available tools.
        
        Args:
            tools: All available tools for this provider
        """
        self._tools = tools
    
    @abstractmethod
    def get_supported_phases(self) -> List[str]:
        """
        Define what phases this provider supports.
        
        Returns:
            List of phase names in order
        """
        pass
    
    @abstractmethod
    def get_phase_guidance(self, phase: str) -> str:
        """
        Get guidance text for a phase.
        
        Args:
            phase: Phase name
            
        Returns:
            Guidance string for the phase
        """
        pass
    
    @abstractmethod
    def get_phase_tool_categories(self, phase: str) -> Set[str]:
        """
        Get tool categories allowed for a phase.
        
        Args:
            phase: Phase name
            
        Returns:
            Set of tool category names for this phase
        """
        pass
    
    @abstractmethod
    def get_phase_context(self) -> PhaseState:
        """Get current phase context."""
        pass
    
    @abstractmethod
    def decide_next_phase(
        self, 
        current_phase: str, 
        context: PhaseState, 
        observations: List['AgentObservation']
    ) -> str:
        """
        Decide the next phase based on current state.
        
        Args:
            current_phase: Current phase name
            context: Current phase context
            observations: Recent observations
            
        Returns:
            Next phase name
        """
        pass
    
    def get_tools_for_phase(self, phase: str) -> List[BaseTool]:
        """
        Get tools for a phase based on categories.
        
        Default implementation that providers can override if needed.
        """
        try:
            categories = self.get_phase_tool_categories(phase)
            phase_tools = []
            
            for tool in self._tools:
                tool_category = self._get_tool_category(tool)
                if tool_category in categories:
                    phase_tools.append(tool)
            
            return phase_tools
        except Exception as e:
            emit(logger, logging.WARNING, "phase.validate_error",
                 phase=phase, error=str(e), detail="get_tools_for_phase")
            return self._tools.copy()
    
    def _get_tool_category(self, tool: BaseTool) -> str:
        """
        Determine tool category. Can be overridden by subclasses.
        
        Args:
            tool: Tool to categorize
            
        Returns:
            Category name for the tool
        """
        tool_name = tool.__class__.__name__.lower()
        
        if any(keyword in tool_name for keyword in ['workplan', 'plan', 'create', 'update', 'mark']):
            return "workplan"
        elif any(keyword in tool_name for keyword in ['delegate', 'task', 'assign']):
            return "delegation"
        elif any(keyword in tool_name for keyword in ['topology', 'adjacent', 'node']):
            return "topology"
        elif any(keyword in tool_name for keyword in ['summarize', 'summary']):
            return "summarization"
        elif any(keyword in tool_name for keyword in ['message', 'send', 'iem']):
            return "iem"
        else:
            return "domain"


# =============================================================================
# EXAMPLE: Simple Custom Provider
# =============================================================================

class SimpleCustomPhaseProvider(PhaseProvider):
    """
    Example of how easy it is to create a custom phase provider.
    
    Just implement the abstract methods - no complex setup needed.
    Takes only what it needs - no circular dependencies!
    """
    
    def __init__(self, tools: List[BaseTool], node_uid: str = "custom-node"):
        super().__init__(tools)
        self._node_uid = node_uid
    
    def get_supported_phases(self) -> List[str]:
        """Define custom phases."""
        return ["research", "design", "implement", "test", "deploy"]
    
    def get_phase_guidance(self, phase: str) -> str:
        """Define guidance for each phase."""
        guidance_map = {
            "research": "PHASE: RESEARCH - Gather requirements and research solutions.",
            "design": "PHASE: DESIGN - Create system design and architecture.",
            "implement": "PHASE: IMPLEMENT - Write code and build features.",
            "test": "PHASE: TEST - Test functionality and fix issues.",
            "deploy": "PHASE: DEPLOY - Deploy to production and monitor."
        }
        return guidance_map.get(phase, f"PHASE: {phase.upper()} - Execute {phase} tasks.")
    
    def get_phase_tool_categories(self, phase: str) -> Set[str]:
        """Define tool categories for each phase."""
        category_map = {
            "research": {"analysis", "search", "documentation"},
            "design": {"design", "modeling", "planning"},
            "implement": {"coding", "integration", "workplan"},
            "test": {"testing", "validation", "quality"},
            "deploy": {"deployment", "monitoring", "summarization"}
        }
        return category_map.get(phase, {"domain"})
    
    def get_phase_context(self) -> PhaseState:
        """Get simple context."""
        from .phase_protocols import create_phase_state
        return create_phase_state(node_uid=self._node_uid)
    
    def decide_next_phase(
        self, 
        current_phase: str, 
        context: PhaseState, 
        observations: List['AgentObservation']
    ) -> str:
        """Simple phase progression."""
        phases = self.get_supported_phases()
        
        try:
            current_index = phases.index(current_phase)
            if current_index < len(phases) - 1:
                return phases[current_index + 1]
        except ValueError:
            pass
        
        # Stay in current phase or go to first phase
        return current_phase if current_phase in phases else phases[0]


# =============================================================================
# EXAMPLE: Research Workflow Provider
# =============================================================================

class ResearchWorkflowProvider(PhaseProvider):
    """
    Example research workflow - shows how easy custom phases are.
    """
    
    def __init__(self, tools: List[BaseTool], node_uid: str = "research-node"):
        super().__init__(tools)
        self._node_uid = node_uid
    
    def get_supported_phases(self) -> List[str]:
        """Research workflow phases."""
        return [
            "literature_review",
            "hypothesis_formation", 
            "experimentation",
            "analysis",
            "publication"
        ]
    
    def get_phase_guidance(self, phase: str) -> str:
        """Research-specific guidance."""
        guidance = {
            "literature_review": "PHASE: LITERATURE_REVIEW - Search and analyze existing research. Build knowledge base.",
            "hypothesis_formation": "PHASE: HYPOTHESIS_FORMATION - Form testable hypotheses based on literature.",
            "experimentation": "PHASE: EXPERIMENTATION - Conduct experiments to test hypotheses systematically.",
            "analysis": "PHASE: ANALYSIS - Analyze experimental data and draw conclusions.",
            "publication": "PHASE: PUBLICATION - Write and publish research findings."
        }
        return guidance.get(phase, f"PHASE: {phase.upper()}")
    
    def get_phase_tool_categories(self, phase: str) -> Set[str]:
        """Research tool categories."""
        categories = {
            "literature_review": {"search", "analysis", "documentation"},
            "hypothesis_formation": {"analysis", "planning", "hypothesis"},
            "experimentation": {"experiment", "data", "measurement"},
            "analysis": {"analysis", "statistics", "visualization"},
            "publication": {"writing", "formatting", "summarization"}
        }
        return categories.get(phase, {"domain"})
    
    def get_phase_context(self) -> PhaseState:
        """Get research context."""
        from .phase_protocols import create_phase_state
        return create_phase_state(node_uid=self._node_uid)
    
    def decide_next_phase(
        self, 
        current_phase: str, 
        context: PhaseState, 
        observations: List['AgentObservation']
    ) -> str:
        """Research phase progression."""
        phases = self.get_supported_phases()
        
        # Terminal phase
        if current_phase == "publication":
            return "publication"
        
        # Normal progression
        try:
            current_index = phases.index(current_phase)
            if current_index < len(phases) - 1:
                return phases[current_index + 1]
        except ValueError:
            pass
        
        return current_phase
