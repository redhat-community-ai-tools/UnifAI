"""
Claude Agent validate_vertex_connection action.

Validates that a Vertex AI project ID + region + model combination can reach
the Anthropic Claude API. Uses AsyncAnthropicVertex.messages.count_tokens()
as a free probe (no tokens generated) with the environment's ADC.
"""

import time
from typing import Optional, Dict, Any

import anyio
from pydantic import Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.elements.nodes.claude_agent.identifiers import Identifier
from mas.core.enums import ResourceCategory


class ValidateVertexConnectionInput(BaseActionInput):
    """Input for Vertex AI connection validation."""
    vertex_project_id: str = Field(description="GCP Project ID")
    vertex_region: str = Field(
        default="us-east5",
        description="GCP region (e.g., 'us-east5', 'europe-west1')",
    )
    model: str = Field(
        default="claude-sonnet-4-6",
        description="Claude model ID to validate (e.g., 'claude-sonnet-4-6')",
    )


class ValidateVertexConnectionOutput(BaseActionOutput):
    """Output for Vertex AI connection validation."""
    is_reachable: bool = False
    response_time_ms: float = 0.0


class ValidateVertexConnectionAction(BaseAction):
    """
    Validates Vertex AI credentials for Claude Agent SDK sessions.

    Attempts to list available Claude models on Vertex AI using the
    environment's Application Default Credentials (ADC). If the call
    succeeds, the project + region combination is valid and reachable.

    Single Responsibility: Only validates Vertex AI reachability.
    """

    uid = "claude_agent.validate_vertex_connection"
    name = "validate_vertex_connection"
    description = (
        "Validate that the Vertex AI project and region can reach "
        "the Anthropic Claude API"
    )
    action_type = ActionType.VALIDATION
    input_schema = ValidateVertexConnectionInput
    output_schema = ValidateVertexConnectionOutput
    version = "1.0.0"
    tags = {"claude_agent", "vertex_ai", "validation", "gcp"}
    elements = {(ResourceCategory.NODE.value, Identifier.TYPE)}

    async def execute(
        self,
        input_data: ValidateVertexConnectionInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidateVertexConnectionOutput:
        """
        Execute Vertex AI connection validation.

        Uses AsyncAnthropicVertex.models.list() as a lightweight probe.
        Authentication relies on the environment's ADC (service account,
        Workload Identity, or GOOGLE_APPLICATION_CREDENTIALS env var).
        """
        start_time = time.time()

        try:
            from anthropic import AsyncAnthropicVertex

            async def _probe() -> None:
                client = AsyncAnthropicVertex(
                    project_id=input_data.vertex_project_id,
                    region=input_data.vertex_region,
                )
                # count_tokens is free (no tokens generated) and maps to
                # Vertex AI's count-tokens:rawPredict endpoint — validates
                # credentials, project, region, AND model in one call.
                await client.messages.count_tokens(
                    model=input_data.model,
                    messages=[{"role": "user", "content": "."}],
                )

            with anyio.fail_after(15.0):
                await _probe()

            return ValidateVertexConnectionOutput(
                success=True,
                message=(
                    f"Vertex AI reachable: project={input_data.vertex_project_id}, "
                    f"region={input_data.vertex_region}"
                ),
                is_reachable=True,
                response_time_ms=(time.time() - start_time) * 1000,
            )

        except TimeoutError:
            return ValidateVertexConnectionOutput(
                success=False,
                message=(
                    f"Connection timed out after 15s — "
                    f"project={input_data.vertex_project_id}, "
                    f"region={input_data.vertex_region}"
                ),
                is_reachable=False,
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ValidateVertexConnectionOutput(
                success=False,
                message=f"Vertex AI validation failed: {str(e)}",
                is_reachable=False,
                response_time_ms=(time.time() - start_time) * 1000,
            )
