"""
Validator for DeepAgentNode — checks all dependency references.

Mirrors ``CustomAgentNodeValidator`` since both nodes share the same
dependency shape (LLM + optional retriever, tools, MCP providers).
"""

from typing import Dict, List

from mas.core.ref.models import Ref
from mas.elements.common.validator import (
    BaseElementValidator,
    ElementValidationResult,
    ValidationContext,
    ValidationMessage,
    ValidatorReport,
)
from .config import DeepAgentNodeConfig


class DeepAgentNodeValidator(BaseElementValidator):
    """Validates ``DeepAgentNodeConfig`` and its dependency references."""

    def validate(
        self,
        config: DeepAgentNodeConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        messages: List[ValidationMessage] = []
        checked: Dict[str, ElementValidationResult] = {}
        all_valid = True

        if config.llm:
            if not self._check_dependency(
                context, self._rid(config.llm), "llm", messages, checked,
            ):
                all_valid = False

        for idx, tool_ref in enumerate(config.tools or []):
            if not self._check_dependency(
                context, self._rid(tool_ref), f"tools[{idx}]", messages, checked,
            ):
                all_valid = False

        if config.retriever:
            if not self._check_dependency(
                context, self._rid(config.retriever), "retriever", messages, checked,
            ):
                all_valid = False

        for idx, provider_ref in enumerate(config.providers or []):
            if not self._check_dependency(
                context, self._rid(provider_ref), f"providers[{idx}]", messages, checked,
            ):
                all_valid = False

        if all_valid and checked:
            messages.append(self._info(
                "ALL_DEPENDENCIES_VALID",
                f"All {len(checked)} dependencies are valid",
            ))

        return self._build_report(messages=messages, checked_dependencies=checked)

    @staticmethod
    def _rid(ref_obj) -> str:
        if isinstance(ref_obj, Ref):
            return ref_obj.ref
        return str(ref_obj)
