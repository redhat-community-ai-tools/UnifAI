"""
elements/nodes/custom_agent/validator.py

Validator for CustomAgentNode - checks all dependencies are valid.
"""

from typing import List, Dict

from core.ref.models import Ref
from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ElementValidationResult,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from elements.nodes.custom_agent.config import CustomAgentNodeConfig


class CustomAgentNodeValidator(BaseElementValidator):
    """
    Validates CustomAgentNode configuration and its dependencies.
    
    Custom agent is valid if ALL its refs are valid:
    - LLM dependency (required)
    - Retriever dependency (optional)
    - Tools dependencies (optional)
    - Providers dependencies (optional, list)
    """

    def validate(
        self,
        config: CustomAgentNodeConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate custom agent node config and its dependencies.
        
        Returns ValidatorReport (service adds metadata).
        """
        messages: List[ValidationMessage] = []
        checked_dependencies: Dict[str, ElementValidationResult] = {}
        all_deps_valid = True

        # Check LLM dependency (required)
        if config.llm:
            llm_rid = self._extract_rid(config.llm)
            if not self._check_dependency(
                context, llm_rid, "llm", messages, checked_dependencies
            ):
                all_deps_valid = False

        # Check tools dependencies (optional, list)
        for idx, tool_ref in enumerate(config.tools or []):
            tool_rid = self._extract_rid(tool_ref)
            if not self._check_dependency(
                context, tool_rid, f"tools[{idx}]", messages, checked_dependencies
            ):
                all_deps_valid = False

        # Check retriever dependency (optional)
        if config.retriever:
            retriever_rid = self._extract_rid(config.retriever)
            if not self._check_dependency(
                context, retriever_rid, "retriever", messages, checked_dependencies
            ):
                all_deps_valid = False

        # Check providers dependencies (optional, list)
        for idx, provider_ref in enumerate(config.providers or []):
            provider_rid = self._extract_rid(provider_ref)
            if not self._check_dependency(
                context, provider_rid, f"providers[{idx}]", messages, checked_dependencies
            ):
                all_deps_valid = False

        # Add summary message
        if all_deps_valid:
            dep_count = len(checked_dependencies)
            if dep_count > 0:
                messages.append(self._info(
                    "ALL_DEPENDENCIES_VALID",
                    f"All {dep_count} dependencies are valid",
                ))
            else:
                # Check if we have any dependencies at all
                total_deps = sum([
                    1 if config.llm else 0,
                    len(config.tools or []),
                    1 if config.retriever else 0,
                    len(config.providers or []),
                ])
                if total_deps == 0:
                    messages.append(self._info(
                        "NO_DEPENDENCIES",
                        "No dependencies to validate",
                    ))
                else:
                    messages.append(self._info(
                        "DEPENDENCIES_NOT_RESOLVED",
                        f"{total_deps} dependencies configured but not resolved for validation",
                    ))

        return self._build_report(
            messages=messages,
            checked_dependencies=checked_dependencies,
        )

    @staticmethod
    def _extract_rid(ref_obj) -> str:
        """Extract rid string from Ref or string."""
        if isinstance(ref_obj, Ref):
            return ref_obj.ref
        return str(ref_obj)

