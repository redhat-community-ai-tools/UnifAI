"""
Action: Get reasoning levels for a specific OpenAI model.

Given a model name (or prefix), returns the supported reasoning-effort
levels.  The frontend calls this action whenever the ``model_name``
selection changes to populate the ``reasoning_effort`` dropdown.

Matching uses the same longest-prefix rule as the capabilities map, so
``"gpt-5.6-sol"`` resolves correctly even when the capabilities dict
only has the full key ``"gpt-5.6-sol"``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from mas.actions.common.action_models import ActionType, BaseActionInput, BaseActionOutput
from mas.actions.common.base_action import BaseAction
from mas.core.enums import ResourceCategory
from mas.elements.llms.openai.model_capabilities import (
    get_capabilities_map,
    get_model_capabilities,
)
from mas.elements.llms.openai.identifiers import Identifier


class GetOpenAIReasoningLevelsInput(BaseActionInput):
    """Input: the model name to look up."""
    model_name: str = Field(
        description="Full model ID or prefix, e.g. 'gpt-5.6-sol' or 'gpt-5'.",
    )


class GetOpenAIReasoningLevelsOutput(BaseActionOutput):
    """Supported reasoning levels for the model."""
    model_name: str = ""
    reasoning_levels: List[str] = []
    model_found: bool = False


class GetOpenAIReasoningLevelsAction(BaseAction):
    uid = "openai.get_reasoning_levels"
    name = "get_reasoning_levels"
    description = (
        "Return the supported reasoning-effort levels "
        "for a given OpenAI model name."
    )
    action_type = ActionType.DISCOVERY
    input_schema = GetOpenAIReasoningLevelsInput
    output_schema = GetOpenAIReasoningLevelsOutput
    version = "1.0.0"
    tags = {"openai", "llm", "discovery", "reasoning"}
    elements = {(ResourceCategory.LLM.value, Identifier.TYPE)}

    def execute(
        self,
        input_data: GetOpenAIReasoningLevelsInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> GetOpenAIReasoningLevelsOutput:
        try:
            model_name = input_data.model_name.strip()
            # Fetch once so the cap lookup shares the cached map.
            caps = get_capabilities_map()
            cap = get_model_capabilities(model_name, capabilities=caps)

            if cap is None:
                return GetOpenAIReasoningLevelsOutput(
                    success=True,
                    message=f"Model '{model_name}' not found in capabilities config",
                    model_name=model_name,
                    reasoning_levels=[],
                    model_found=False,
                )

            levels = cap.get("reasoning", [])
            return GetOpenAIReasoningLevelsOutput(
                success=True,
                message=f"Found {len(levels)} reasoning levels for '{model_name}'",
                model_name=model_name,
                reasoning_levels=levels,
                model_found=True,
            )
        except Exception as e:
            return GetOpenAIReasoningLevelsOutput(
                success=False,
                message=f"Failed to retrieve reasoning levels: {e}",
                model_name=getattr(input_data, "model_name", ""),
                reasoning_levels=[],
                model_found=False,
            )
