"""
Action: Get available OpenAI model names.

Returns the list of model-name prefixes configured in the
``openai_model_capabilities`` admin config section.  The frontend uses
this list to render ``model_name`` as a dropdown instead of a free-text
field when creating or editing an OpenAI LLM resource.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mas.actions.common.action_models import ActionType, BaseActionInput, BaseActionOutput
from mas.actions.common.base_action import BaseAction
from mas.core.enums import ResourceCategory
from mas.core.identity.ports import AdminConfigReaderPort
from mas.actions.llms.openai.capabilities import load_capabilities
from mas.elements.llms.openai.identifiers import Identifier


class GetOpenAIModelsInput(BaseActionInput):
    """No input required — returns all configured model names."""
    pass


class GetOpenAIModelsOutput(BaseActionOutput):
    """List of model-name prefixes available in the admin config."""
    models: List[str] = []
    total_count: int = 0


class GetOpenAIModelsAction(BaseAction):
    uid = "openai.get_models"
    name = "get_models"
    description = (
        "Retrieve the list of OpenAI model names configured in the "
        "admin MODEL_CAPABILITIES settings."
    )
    action_type = ActionType.DISCOVERY
    input_schema = GetOpenAIModelsInput
    output_schema = GetOpenAIModelsOutput
    version = "1.0.0"
    tags = {"openai", "llm", "discovery", "models"}
    elements = {(ResourceCategory.LLM.value, Identifier.TYPE)}

    def __init__(self, admin_config_reader: AdminConfigReaderPort) -> None:
        self._reader = admin_config_reader

    def execute(
        self,
        input_data: GetOpenAIModelsInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> GetOpenAIModelsOutput:
        try:
            caps = load_capabilities(self._reader)
            models = sorted(caps.keys())
            return GetOpenAIModelsOutput(
                success=True,
                message=f"Found {len(models)} configured models",
                models=models,
                total_count=len(models),
            )
        except Exception as e:
            return GetOpenAIModelsOutput(
                success=False,
                message=f"Failed to retrieve models: {e}",
                models=[],
                total_count=0,
            )
