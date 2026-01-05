"""Validator for OrchestratorNode - checks LLM dependency is valid."""

from typing import List, Dict

from core.ref.models import Ref
from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ElementValidationResult,
    ValidationContext,
    ValidationMessage,
)
from elements.nodes.orchestrator.config import OrchestratorNodeConfig


class OrchestratorNodeValidator(BaseElementValidator):
    """
    Validates OrchestratorNode configuration and its dependencies.
    
    Orchestrator is valid if its LLM dependency is valid.
    """

    def validate(
            self,
            config: OrchestratorNodeConfig,
            context: ValidationContext,
    ) -> ValidatorReport:
        """Validate orchestrator node config and its dependencies."""
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

        # Add summary message
        if all_deps_valid:
            dep_count = len(checked_dependencies)
            if dep_count > 0:
                messages.append(self._info(
                    "ALL_DEPENDENCIES_VALID",
                    f"All {dep_count} dependencies are valid",
                ))
            else:
                total_deps = sum([
                    1 if config.llm else 0,
                    len(config.tools or []),
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
