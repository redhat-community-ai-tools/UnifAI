"""
validation/service.py

ElementValidationService - orchestrates validation.

Responsibilities:
- Look up validators from ElementRegistry
- Call validators with proper context
- Build ElementValidationResult from ValidatorReport + metadata
- Accumulate results for ordered validation

Does NOT:
- Know about Resources or Blueprints
- Fetch data from database
- Resolve references
"""

from typing import Dict, List, Optional, Type

from catalog.element_registry import ElementRegistry
from core.enums import ResourceCategory
from elements.common.validator import (
    ElementValidator,
    ElementValidationResult,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationSeverity,
    ValidationCode,
)
from validation.models import ConfigMeta


class ElementValidationService:
    """
    Pure validation service.
    
    Receives configs, returns results.
    Only dependency is ElementRegistry (to find validators).
    All methods are synchronous.
    
    Validators return ValidatorReport (what they found).
    Service builds ElementValidationResult (report + metadata).
    """

    def __init__(self, element_registry: ElementRegistry):
        self._registry = element_registry

    def validate(
        self,
        config_meta: ConfigMeta,
        context: ValidationContext,
    ) -> ElementValidationResult:
        """
        Validate a single config.
        
        Looks up the validator from ElementRegistry and calls it.
        Builds ElementValidationResult from ValidatorReport + metadata.
        If no validator is defined, returns success with INFO message.
        """
        # Get spec from registry
        spec = self._registry.get_spec(
            config_meta.category, 
            config_meta.element_type
        )
        
        # Check if validator exists (runtime lookup, not import)
        validator_cls: Optional[Type[ElementValidator]] = getattr(
            spec, "validator_cls", None
        )
        
        if validator_cls is None:
            # No validator defined - schema validation already passed
            return ElementValidationResult(
                is_valid=True,
                element_rid=config_meta.rid,
                element_type=config_meta.element_type,
                name=config_meta.name,
                messages=[
                    ValidationMessage(
                        severity=ValidationSeverity.INFO,
                        code=ValidationCode.NO_VALIDATOR.value,
                        message="No validator defined; schema validation passed",
                    )
                ],
            )
        
        # Instantiate and call validator - returns ValidatorReport
        validator = validator_cls()
        report = validator.validate(config_meta.config, context)
        
        # Build ElementValidationResult from report + metadata
        return self._build_result(config_meta, report)

    def _build_result(
        self,
        config_meta: ConfigMeta,
        report: ValidatorReport,
    ) -> ElementValidationResult:
        """
        Build ElementValidationResult from ValidatorReport + metadata.
        
        The service knows the element metadata (rid, type, name).
        The validator only knows what it found (messages, checked deps).
        """
        return ElementValidationResult(
            is_valid=report.is_valid,
            element_rid=config_meta.rid,
            element_type=config_meta.element_type,
            name=config_meta.name,
            messages=report.messages,
            dependency_results=report.checked_dependencies,
        )

    def validate_ordered(
        self,
        configs: List[ConfigMeta],
        base_context: ValidationContext,
    ) -> Dict[str, ElementValidationResult]:
        """
        Validate multiple configs in the given order.
        
        Caller is responsible for providing configs in dependency order
        (dependencies before dependents).
        
        Results accumulate in context so later validators can see
        earlier results.
        """
        results: Dict[str, ElementValidationResult] = {}
        
        for config_meta in configs:
            # Update context with accumulated results
            context = base_context.with_dependency_results(results)
            
            # Validate this config
            result = self.validate(config_meta, context)
            
            # Store result
            results[config_meta.rid] = result
        
        return results

