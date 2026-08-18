"""
Extensible phase system that supports custom phases.

This module provides a flexible phase system where users can define their own
phases, guidance, and tool mappings without modifying core code.
"""

import logging

from typing import Dict, List, Set, Protocol, Any, Type
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from global_utils.utils.logging_config import emit
from mas.elements.tools.common.base_tool import BaseTool

logger = logging.getLogger(__name__)


# =============================================================================
# EXTENSIBLE PHASE DEFINITIONS
# =============================================================================

class PhaseProtocol(Protocol):
    """
    Protocol that any phase enum must implement.
    
    This allows users to define their own phase enums while maintaining
    compatibility with the phase system.
    """
    
    @property
    def value(self) -> str:
        """Phase identifier string."""
        ...
    
    def __str__(self) -> str:
        """String representation of phase."""
        ...
    
    def __eq__(self, other) -> bool:
        """Equality comparison."""
        ...
    
    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        ...


@dataclass(frozen=True)
class PhaseDefinition:
    """
    Definition of a single phase in a workflow.
    
    This allows users to define custom phases with their own
    characteristics and behavior.
    """
    
    name: str
    description: str
    guidance: str
    tool_categories: Set[str]  # Use strings for flexibility
    keywords: Set[str]
    is_terminal: bool = False
    allowed_transitions: Set[str] = None  # Phase names it can transition to
    
    def __post_init__(self):
        if self.allowed_transitions is None:
            object.__setattr__(self, 'allowed_transitions', set())


class PhaseRegistry:
    """
    Registry for phase definitions that supports custom phases.
    
    This allows users to register their own phases and phase systems
    without modifying core code.
    """
    
    _registries: Dict[str, 'PhaseRegistry'] = {}
    
    def __init__(self, name: str):
        """
        Initialize a phase registry.
        
        Args:
            name: Unique name for this phase registry
        """
        self.name = name
        self._phases: Dict[str, PhaseDefinition] = {}
        self._phase_order: List[str] = []
        PhaseRegistry._registries[name] = self
    
    def register_phase(self, phase_def: PhaseDefinition) -> None:
        """
        Register a phase definition.
        
        Args:
            phase_def: Phase definition to register
        """
        self._phases[phase_def.name] = phase_def
        if phase_def.name not in self._phase_order:
            self._phase_order.append(phase_def.name)
    
    def get_phase(self, name: str) -> PhaseDefinition:
        """Get phase definition by name."""
        if name not in self._phases:
            raise ValueError(f"Phase '{name}' not found in registry '{self.name}'")
        return self._phases[name]
    
    def get_all_phases(self) -> List[PhaseDefinition]:
        """Get all registered phases in order."""
        return [self._phases[name] for name in self._phase_order]
    
    def get_phase_names(self) -> List[str]:
        """Get all phase names in order."""
        return self._phase_order.copy()
    
    def validate_transitions(self) -> bool:
        """
        Validate that all phase transitions reference valid phases.
        
        Returns:
            True if all transitions are valid
        """
        all_names = set(self._phases.keys())
        for phase_def in self._phases.values():
            invalid_transitions = phase_def.allowed_transitions - all_names
            if invalid_transitions:
                raise ValueError(
                    f"Phase '{phase_def.name}' has invalid transitions: {invalid_transitions}"
                )
        return True
    
    @classmethod
    def get_registry(cls, name: str) -> 'PhaseRegistry':
        """Get a registry by name."""
        if name not in cls._registries:
            raise ValueError(f"Registry '{name}' not found")
        return cls._registries[name]
    
    @classmethod
    def create_standard_registry() -> 'PhaseRegistry':
        """Create the standard plan-and-execute phase registry."""
        registry = PhaseRegistry("standard")
        
        # Define standard phases
        planning = PhaseDefinition(
            name="planning",
            description="Create detailed work plan with dependencies",
            guidance="PHASE: PLANNING - Create detailed work plan with dependencies. Break down tasks logically. Don't execute or delegate yet.",
            tool_categories={"workplan", "topology"},
            keywords={"create", "update"},
            allowed_transitions={"planning", "allocation"}
        )
        
        allocation = PhaseDefinition(
            name="allocation", 
            description="Assign work items to appropriate nodes",
            guidance="PHASE: ALLOCATION - Assign work items to appropriate nodes. Use adjacency info to delegate. Don't execute local work yet.",
            tool_categories={"workplan", "topology", "iem", "delegation"},
            keywords={"assign"},
            allowed_transitions={"planning", "allocation", "execution", "monitoring"}
        )
        
        execution = PhaseDefinition(
            name="execution",
            description="Execute local work items only", 
            guidance="PHASE: EXECUTION - Execute local work items only. Don't modify plan structure or delegate new work.",
            tool_categories={"workplan", "domain"},
            keywords=set(),
            allowed_transitions={"execution", "monitoring"}
        )
        
        monitoring = PhaseDefinition(
            name="monitoring",
            description="Interpret responses and decide next steps",
            guidance="PHASE: MONITORING - Interpret responses and decide next steps. Respect retry limits (check item.retry_count vs max_retries). Mark status only when certain about outcome.",
            tool_categories={"workplan", "iem", "delegation", "topology"},
            keywords={"ingest", "complete", "assign", "mark"},
            allowed_transitions={"allocation", "execution", "monitoring", "synthesis"}
        )
        
        synthesis = PhaseDefinition(
            name="synthesis",
            description="Summarize completed work and produce final deliverables",
            guidance="PHASE: SYNTHESIS - Summarize completed work and produce final deliverables. Focus on results and outputs.",
            tool_categories={"workplan", "summarization"},
            keywords={"summarize"},
            is_terminal=True,
            allowed_transitions={"synthesis"}
        )
        
        # Register phases
        for phase in [planning, allocation, execution, monitoring, synthesis]:
            registry.register_phase(phase)
        
        registry.validate_transitions()
        return registry


# =============================================================================
# EXTENSIBLE PHASE PROVIDER BASE
# =============================================================================

class ExtensiblePhaseProvider(ABC):
    """
    Base class for phase providers that support custom phases.
    
    This replaces the hard-coded approach with a flexible system
    that can work with any phase registry.
    """
    
    def __init__(self, tools: List[BaseTool], phase_registry: PhaseRegistry):
        """
        Initialize with tools and phase registry.
        
        Args:
            tools: Available tools
            phase_registry: Registry defining the phases for this provider
        """
        self._tools = tools
        self._phase_registry = phase_registry
        self._tool_categories = self._categorize_tools(tools)
        self._validate_setup()
    
    def get_supported_phases(self) -> List[str]:
        """Get list of phase names supported by this provider."""
        return self._phase_registry.get_phase_names()
    
    def get_phase_guidance(self, phase_name: str) -> str:
        """Get guidance for a phase by name."""
        phase_def = self._phase_registry.get_phase(phase_name)
        return phase_def.guidance
    
    def get_phase_tool_categories(self, phase_name: str) -> Set[str]:
        """Get tool categories for a phase by name."""
        phase_def = self._phase_registry.get_phase(phase_name)
        return phase_def.tool_categories
    
    def get_tools_for_phase(self, phase_name: str) -> List[BaseTool]:
        """Get tools appropriate for a phase."""
        try:
            categories = self.get_phase_tool_categories(phase_name)
            phase_tools = []
            
            for category in categories:
                if category in self._tool_categories:
                    phase_tools.extend(self._tool_categories[category])
            
            return phase_tools
        except Exception as e:
            emit(logger, logging.WARNING, "phase.validate_error",
                 phase=phase_name, error=str(e), detail="get_tools_for_phase")
            return self._tools.copy()
    
    def validate_phase_transition(self, from_phase: str, to_phase: str) -> bool:
        """Validate that a phase transition is allowed."""
        try:
            phase_def = self._phase_registry.get_phase(from_phase)
            return to_phase in phase_def.allowed_transitions
        except ValueError:
            return False
    
    def is_terminal_phase(self, phase_name: str) -> bool:
        """Check if a phase is terminal."""
        try:
            phase_def = self._phase_registry.get_phase(phase_name)
            return phase_def.is_terminal
        except ValueError:
            return False
    
    @abstractmethod
    def get_phase_context(self) -> Any:
        """Get current phase context - must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def decide_next_phase(self, current_phase: str, context: Any, observations: List[Any]) -> str:
        """Decide next phase - must be implemented by subclasses."""
        pass
    
    def _categorize_tools(self, tools: List[BaseTool]) -> Dict[str, List[BaseTool]]:
        """Categorize tools by their category strings."""
        categorized = {}
        
        for tool in tools:
            category = self._get_tool_category(tool)
            if category:
                if category not in categorized:
                    categorized[category] = []
                categorized[category].append(tool)
        
        return categorized
    
    def _get_tool_category(self, tool: BaseTool) -> str:
        """Determine tool category - can be overridden by subclasses."""
        tool_name = tool.__class__.__name__.lower()
        
        # Basic categorization - subclasses can override for custom logic
        if any(keyword in tool_name for keyword in ['workplan', 'plan', 'create', 'update', 'mark']):
            return "workplan"
        elif any(keyword in tool_name for keyword in ['delegate', 'task', 'assign']):
            return "delegation"
        elif any(keyword in tool_name for keyword in ['topology', 'adjacent', 'node']):
            return "topology"
        elif any(keyword in tool_name for keyword in ['summarize', 'summary']):
            return "summarization"
        else:
            return "domain"
    
    def _validate_setup(self) -> None:
        """Validate that the provider is properly set up."""
        try:
            self._phase_registry.validate_transitions()
        except Exception as e:
            emit(logger, logging.WARNING, "phase.validate_error",
                 error=str(e), detail="phase_registry_validation")


# =============================================================================
# EXAMPLE: CUSTOM PHASE SYSTEM
# =============================================================================

def create_custom_research_phases() -> PhaseRegistry:
    """
    Example: Create a custom phase system for research workflows.
    
    This demonstrates how users can define their own phases.
    """
    registry = PhaseRegistry("research")
    
    # Define custom research phases
    literature_review = PhaseDefinition(
        name="literature_review",
        description="Review existing literature and research",
        guidance="PHASE: LITERATURE_REVIEW - Search and analyze existing research. Build knowledge base. Don't start experiments yet.",
        tool_categories={"search", "analysis", "knowledge"},
        keywords={"search", "review", "analyze"},
        allowed_transitions={"literature_review", "hypothesis_formation"}
    )
    
    hypothesis_formation = PhaseDefinition(
        name="hypothesis_formation", 
        description="Form testable hypotheses based on literature",
        guidance="PHASE: HYPOTHESIS_FORMATION - Create testable hypotheses. Define success criteria. Plan experiments.",
        tool_categories={"analysis", "planning", "hypothesis"},
        keywords={"hypothesis", "plan", "criteria"},
        allowed_transitions={"literature_review", "hypothesis_formation", "experimentation"}
    )
    
    experimentation = PhaseDefinition(
        name="experimentation",
        description="Conduct experiments to test hypotheses",
        guidance="PHASE: EXPERIMENTATION - Execute planned experiments. Collect data systematically. Document results.",
        tool_categories={"experiment", "data", "measurement"},
        keywords={"experiment", "measure", "collect"},
        allowed_transitions={"experimentation", "analysis"}
    )
    
    analysis = PhaseDefinition(
        name="analysis",
        description="Analyze experimental results",
        guidance="PHASE: ANALYSIS - Analyze collected data. Test hypotheses. Draw conclusions.",
        tool_categories={"analysis", "statistics", "visualization"},
        keywords={"analyze", "statistics", "visualize"},
        allowed_transitions={"experimentation", "analysis", "publication"}
    )
    
    publication = PhaseDefinition(
        name="publication",
        description="Prepare and publish research findings",
        guidance="PHASE: PUBLICATION - Write research paper. Create visualizations. Prepare for publication.",
        tool_categories={"writing", "visualization", "formatting"},
        keywords={"write", "format", "publish"},
        is_terminal=True,
        allowed_transitions={"publication"}
    )
    
    # Register all phases
    for phase in [literature_review, hypothesis_formation, experimentation, analysis, publication]:
        registry.register_phase(phase)
    
    registry.validate_transitions()
    return registry


# =============================================================================
# FACTORY FOR CREATING PHASE SYSTEMS
# =============================================================================

class PhaseSystemFactory:
    """Factory for creating different phase systems."""
    
    @staticmethod
    def create_standard_system() -> PhaseRegistry:
        """Create standard plan-and-execute phase system."""
        return PhaseRegistry.create_standard_registry()
    
    @staticmethod
    def create_research_system() -> PhaseRegistry:
        """Create research workflow phase system."""
        return create_custom_research_phases()
    
    @staticmethod
    def create_custom_system(name: str, phases: List[PhaseDefinition]) -> PhaseRegistry:
        """
        Create a custom phase system.
        
        Args:
            name: Name for the phase registry
            phases: List of phase definitions
            
        Returns:
            Configured phase registry
        """
        registry = PhaseRegistry(name)
        for phase in phases:
            registry.register_phase(phase)
        registry.validate_transitions()
        return registry
