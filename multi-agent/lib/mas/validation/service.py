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

from mas.catalog.element_registry import ElementRegistry
from mas.core.element_meta import ElementConfigMeta
from mas.elements.common.validator import (
    ElementValidator,
    ElementValidationResult,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationSeverity,
    ValidationCode,
)


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
        config_meta: ElementConfigMeta,
        context: ValidationContext,
    ) -> ElementValidationResult:
        """
        Validate a single config.

        Looks up the validator from ElementRegistry and calls it.
        Builds ElementValidationResult from ValidatorReport + metadata.
        If no validator is defined, returns success with INFO message.

        If ``config_meta.validation_override_error`` is set, the real
        validator is skipped entirely and this fails immediately with that
        message — e.g. a built-in resource whose caller has no per-identity
        overlay for a required secret field. This keeps that veto generic
        (a plain flag on the metadata) rather than importing any
        Resources/built-in-specific logic here.
        """
        if config_meta.validation_override_error:
            return ElementValidationResult(
                is_valid=False,
                element_rid=config_meta.rid,
                element_type=config_meta.type_key,
                name=config_meta.name,
                messages=[
                    ValidationMessage(
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.MISSING_REQUIRED_FIELD.value,
                        message=config_meta.validation_override_error,
                    )
                ],
            )

        spec = self._registry.get_spec(
            config_meta.category,
            config_meta.type_key
        )

        validator_cls: Optional[Type[ElementValidator]] = getattr(
            spec, "validator_cls", None
        )

        if validator_cls is None:
            return ElementValidationResult(
                is_valid=True,
                element_rid=config_meta.rid,
                element_type=config_meta.type_key,
                name=config_meta.name,
                messages=[
                    ValidationMessage(
                        severity=ValidationSeverity.INFO,
                        code=ValidationCode.NO_VALIDATOR.value,
                        message="No validator defined; schema validation passed",
                    )
                ],
            )

        validator = validator_cls()
        report = validator.validate(config_meta.config, context)

        return self._build_result(config_meta, report)

    def _build_result(
        self,
        config_meta: ElementConfigMeta,
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
            element_type=config_meta.type_key,
            name=config_meta.name,
            messages=report.messages,
            dependency_results=report.checked_dependencies,
        )

    def validate_ordered(
        self,
        configs: List[ElementConfigMeta],
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
            context = base_context.with_dependency_results(results)
            result = self.validate(config_meta, context)
            results[config_meta.rid] = result

        return results
