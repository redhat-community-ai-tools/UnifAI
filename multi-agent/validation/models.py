"""
validation/models.py

Models for validation orchestration (service-level).
Element-level models live in elements/common/validator.py
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pydantic import BaseModel

from core.enums import ResourceCategory
from elements.common.validator import ElementValidationResult


@dataclass
class ConfigMeta:
    """
    Metadata about a config to be validated by the service.
    This is what callers prepare and pass to ValidationService.
    """
    rid: str
    category: ResourceCategory
    element_type: str
    config: BaseModel
    name: Optional[str] = None
    dependency_rids: List[str] = field(default_factory=list)


@dataclass
class BlueprintValidationResult:
    """Result of validating an entire blueprint."""
    blueprint_id: str
    is_valid: bool
    element_results: Dict[str, ElementValidationResult] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "blueprint_id": self.blueprint_id,
            "is_valid": self.is_valid,
            "element_results": {
                rid: r.to_dict() for rid, r in self.element_results.items()
            },
        }

