"""
Claude Agent Node Configuration
"""

from mas.elements.nodes.common.base_config import NodeBaseConfig
from pydantic import Field
from typing import Optional, Literal, List, Dict
from .identifiers import Identifier
from mas.core.ref.models import RetrieverRef, ProviderRef, SandboxRef, ToolRef
from mas.core.field_hints import ActionHint, HintType, HiddenHint


class ClaudeAgentNodeConfig(NodeBaseConfig):
    """
    Claude Agent Node - runs autonomous Claude Agent SDK sessions.

    Configures the Claude Agent SDK with model, permissions,
    tools, skills, and Vertex AI authentication.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    # --- Authentication (Vertex AI) ---

    vertex_project_id: str = Field(
        description="GCP Project ID for Vertex AI (e.g., 'my-project-123')",
        json_schema_extra=ActionHint(
            action_uid="claude_agent.validate_vertex_connection",
            hint_type=HintType.VALIDATE,
            field_mapping="is_reachable",
            dependencies={
                "vertex_project_id": "vertex_project_id",
                "vertex_region": "vertex_region",
                "model": "model",
            }
        ).to_hints()
    )

    vertex_region: str = Field(
        default="us-east5",
        description="GCP region for Vertex AI (e.g., 'us-east5', 'europe-west1')"
    )

    # --- Model Configuration ---

    model: str = Field(
        default="claude-sonnet-4-6",
        description="Claude model to use (e.g., claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5)"
    )

    # --- Agent Behavior ---

    system_prompt: str = Field(
        default="",
        description="Custom system prompt for the Claude agent session"
    )

    max_turns: Optional[int] = Field(
        default=200,
        description="Maximum agentic turns (tool-use round trips). Prevents runaway execution."
    )

    permission_mode: str = Field(
        default="bypassPermissions",
        description="Permission mode: 'bypassPermissions' (fully autonomous), "
                    "'acceptEdits' (auto-accept edits), 'plan' (read-only)"
    )

    allowed_tools: List[str] = Field(
        default_factory=lambda: [
            "Read", "Write", "Edit", "Bash",
            "Glob", "Grep", "WebSearch", "WebFetch",
        ],
        description="Tools to auto-approve without permission checks"
    )

    disallowed_tools: List[str] = Field(
        default_factory=list,
        description="Tools to explicitly deny"
    )

    # --- Skills ---

    skills_repos: Dict[str, str] = Field(
        default_factory=dict,
        description="Skill sources — each key is the skill path within the repo and "
                    "the value is the git repo URL "
                    '(e.g., {"skills/docx": "https://github.com/org/repo"})'
    )


    # --- Advanced ---

    cwd: Optional[str] = Field(
        default=None,
        description="Working directory for the Claude agent session (defaults to temp directory)",
        json_schema_extra=HiddenHint(
            reason="Advanced: override working directory"
        ).to_hints()
    )

    env_vars: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional environment variables to pass to the SDK session",
        json_schema_extra=HiddenHint(
            reason="Advanced: custom environment variables"
        ).to_hints()
    )

    # --- Integration ---

    tools: Optional[List[ToolRef]] = Field(
        default_factory=list,
        description="List of tool keys"
    )

    providers: Optional[List[ProviderRef]] = Field(
        default_factory=list,
        description="List of MCP Provider Refs"
    )

    retriever: Optional[RetrieverRef] = Field(
        None,
        description="Retriever for context augmentation (optional)"
    )

    sandbox: Optional[SandboxRef] = Field(
        None,
        description="Sandbox execution environment (optional)"
    )
