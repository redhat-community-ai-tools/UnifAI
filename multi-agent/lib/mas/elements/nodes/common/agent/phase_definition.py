"""
Clean Pydantic models for phase definitions.

Provides structured, type-safe phase configuration with validation support.
"""

import logging

from typing import List, Optional, Protocol, Any
from pydantic import BaseModel, Field
from global_utils.utils.logging_config import emit
from mas.elements.tools.common.base_tool import BaseTool

# Import for typing - avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .phases.models import PhaseValidationContext

logger = logging.getLogger(__name__)


class PhaseValidator(Protocol):
    """
    Protocol for phase-specific validators.
    
    Validators implement single responsibility: they validate one aspect
    of a phase's state and return guidance text if issues are found.
    """
    
    def validate(self, context: "PhaseValidationContext") -> str:
        """
        Validate phase state and return guidance text.
        
        Args:
            context: Typed validation context with phase state and related data
            
        Returns:
            Guidance text if issues found, empty string if validation passes
        """
        ...


class PhaseDefinition(BaseModel):
    """
    Clean definition of a single execution phase.
    
    Contains all phase-specific configuration in one place, including validators.
    """
    name: str = Field(..., description="Phase name (e.g., 'planning', 'execution')")
    description: str = Field(..., description="What this phase does")
    tools: List[BaseTool] = Field(default_factory=list, description="Actual tool objects for this phase")
    guidance: str = Field(..., description="LLM guidance for this phase")
    validators: List[Any] = Field(default_factory=list, description="Validators for this phase")
    
    class Config:
        arbitrary_types_allowed = True  # Allow BaseTool objects and validators
    
    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to this phase."""
        if tool not in self.tools:
            self.tools.append(tool)
    
    def add_tools(self, tools: List[BaseTool]) -> None:
        """Add multiple tools to this phase."""
        for tool in tools:
            self.add_tool(tool)
    
    def add_validator(self, validator: PhaseValidator) -> None:
        """Add a validator to this phase."""
        # Runtime type check since Pydantic can't validate Protocol types
        if not hasattr(validator, 'validate') or not callable(getattr(validator, 'validate')):
            raise ValueError(f"Validator must implement PhaseValidator protocol with validate() method")
        self.validators.append(validator)
    
    def run_validators(self, context: "PhaseValidationContext") -> str:
        """
        Run all validators for this phase and return combined guidance.
        
        Args:
            context: Validation context with phase state and related data
            
        Returns:
            Combined guidance text from all validators, empty if no issues
        """
        guidance_parts: List[str] = []
        
        for validator in self.validators:
            try:
                guidance = validator.validate(context)
                if guidance:
                    guidance_parts.append(guidance)
            except Exception as e:
                emit(logger, logging.WARNING, "phase.validate_error",
                     phase=self.name, error=str(e), detail="validator")
                # Continue with other validators
        
        return "\n\n".join(guidance_parts) if guidance_parts else ""
    
    def get_tool_names(self) -> List[str]:
        """Get list of tool names for debugging/logging."""
        return [tool.name for tool in self.tools]


class PhaseSystem(BaseModel):
    """
    Complete phase system definition.
    
    Contains all phases and their configurations for a specific provider.
    """
    name: str = Field(..., description="Name of this phase system (e.g., 'orchestrator')")
    description: str = Field(..., description="What this phase system does")
    phases: List[PhaseDefinition] = Field(default_factory=list, description="All phases in execution order")
    
    def add_phase(self, phase: PhaseDefinition) -> None:
        """Add a phase to this system."""
        self.phases.append(phase)
    
    def get_phase(self, name: str) -> Optional[PhaseDefinition]:
        """Get a phase by name."""
        for phase in self.phases:
            if phase.name == name:
                return phase
        return None
    
    def get_phase_names(self) -> List[str]:
        """Get list of all phase names in order."""
        return [phase.name for phase in self.phases]
    
    def get_tools_for_phase(self, phase_name: str) -> List[BaseTool]:
        """Get actual tool objects for a specific phase."""
        phase = self.get_phase(phase_name)
        return phase.tools if phase else []
    
    def get_guidance_for_phase(self, phase_name: str) -> str:
        """Get guidance text for a specific phase."""
        phase = self.get_phase(phase_name)
        return phase.guidance if phase else ""
