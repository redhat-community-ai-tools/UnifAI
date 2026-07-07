"""
Validator for Claude Agent Node - checks configuration completeness.
"""

from typing import List, Dict

from mas.elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ElementValidationResult,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from mas.elements.nodes.claude_agent.config import ClaudeAgentNodeConfig
from mas.elements.nodes.claude_agent.identifiers import EffortLevel
from mas.core.ref.models import Ref


class ClaudeAgentNodeValidator(BaseElementValidator):
    """
    Validates Claude Agent Node configuration.

    Checks:
    - Vertex AI project ID is present
    - Model string is valid
    - Effort level is valid
    - Permission mode is recognized
    - Max turns bounds
    - Retriever dependency (if configured)

    Note: Vertex AI credential reachability is validated in real-time
    via the claude_agent.validate_vertex_connection action (ActionHint).
    """

    VALID_EFFORT_LEVELS = {e.value for e in EffortLevel}

    VALID_PERMISSION_MODES = {
        "default", "acceptEdits", "plan", "dontAsk", "bypassPermissions",
    }

    def validate(
        self,
        config: ClaudeAgentNodeConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        messages: List[ValidationMessage] = []
        checked_dependencies: Dict[str, ElementValidationResult] = {}

        self._check_vertex_project(config, messages)
        self._check_model(config, messages)
        self._check_effort(config, messages)
        self._check_permission_mode(config, messages)
        self._check_max_turns(config, messages)
        self._check_skills_repos(config, messages)

        if config.retriever:
            retriever_rid = self._extract_rid(config.retriever)
            self._check_dependency(
                context, retriever_rid, "retriever", messages, checked_dependencies
            )

        return self._build_report(
            messages=messages,
            checked_dependencies=checked_dependencies,
        )

    def _check_vertex_project(
        self,
        config: ClaudeAgentNodeConfig,
        messages: List[ValidationMessage],
    ) -> None:
        if not config.vertex_project_id or not config.vertex_project_id.strip():
            messages.append(self._error(
                ValidationCode.MISSING_REQUIRED_FIELD.value,
                "Vertex AI Project ID is required",
                field="vertex_project_id",
            ))
        else:
            messages.append(self._info(
                "VERTEX_PROJECT_SET",
                f"Vertex AI project: {config.vertex_project_id} "
                f"(region: {config.vertex_region})",
                field="vertex_project_id",
            ))

    def _check_model(
        self,
        config: ClaudeAgentNodeConfig,
        messages: List[ValidationMessage],
    ) -> None:
        if not config.model or not config.model.strip():
            messages.append(self._error(
                ValidationCode.MISSING_REQUIRED_FIELD.value,
                "Model must be specified",
                field="model",
            ))
        elif not config.model.startswith("claude"):
            messages.append(self._warning(
                "UNUSUAL_MODEL_NAME",
                f"Model '{config.model}' doesn't look like a standard Claude model ID",
                field="model",
            ))

    def _check_effort(
        self,
        config: ClaudeAgentNodeConfig,
        messages: List[ValidationMessage],
    ) -> None:
        if config.effort not in self.VALID_EFFORT_LEVELS:
            messages.append(self._error(
                "INVALID_EFFORT_LEVEL",
                f"Unknown effort level: {config.effort}. "
                f"Valid: {sorted(self.VALID_EFFORT_LEVELS)}",
                field="effort",
            ))

    def _check_permission_mode(
        self,
        config: ClaudeAgentNodeConfig,
        messages: List[ValidationMessage],
    ) -> None:
        if config.permission_mode not in self.VALID_PERMISSION_MODES:
            messages.append(self._error(
                "INVALID_PERMISSION_MODE",
                f"Unknown permission mode: {config.permission_mode}. "
                f"Valid: {sorted(self.VALID_PERMISSION_MODES)}",
                field="permission_mode",
            ))

    def _check_max_turns(
        self,
        config: ClaudeAgentNodeConfig,
        messages: List[ValidationMessage],
    ) -> None:
        if config.max_turns is not None and config.max_turns < 1:
            messages.append(self._error(
                "INVALID_MAX_TURNS",
                "max_turns must be at least 1",
                field="max_turns",
            ))

    def _check_skills_repos(
        self,
        config: ClaudeAgentNodeConfig,
        messages: List[ValidationMessage],
    ) -> None:
        for skill_path, repo_url in config.skills_repos.items():
            if not skill_path or not skill_path.strip():
                messages.append(self._error(
                    "MISSING_SKILL_PATH",
                    "skills_repos: skill_path key must not be empty",
                    field="skills_repos",
                ))
            elif ".." in skill_path.split("/"):
                messages.append(self._error(
                    "INVALID_SKILL_PATH",
                    f"skills_repos[{skill_path}]: skill_path must not contain '..' segments",
                    field="skills_repos",
                ))
            if not repo_url or not repo_url.strip():
                messages.append(self._error(
                    "MISSING_SKILL_REPO_URL",
                    f"skills_repos[{skill_path}]: repo URL value is required",
                    field="skills_repos",
                ))

    @staticmethod
    def _extract_rid(ref_obj) -> str:
        if isinstance(ref_obj, Ref):
            return ref_obj.ref
        return str(ref_obj)
