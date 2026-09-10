from typing import Literal, Optional, Dict, Any
from pydantic import Field
from mas.core.field_hints import (
    ActionHint, HintType, SelectionType,
    CardHint, CardContext, PropagateHint, combine_hints,
)
from ..common.base_config import BaseLLMConfig
from .identifiers import Identifier


class OpenAIConfig(BaseLLMConfig):
    """
    Configuration for the official OpenAI Responses API (GPT-5+, o-series).

    Temperature is omitted — reasoning models manage sampling internally.
    Use ``reasoning_effort`` to control the quality / latency trade-off.

    For older OpenAI models or any OpenAI-compatible server (vLLM, LocalAI, etc.),
    use the ``openai_compatible`` provider which retains temperature.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    # Override base model_name to add the populate-from-action hint.
    # The action fetches the model list live from the admin MODEL_CAPABILITIES config.
    model_name: str = Field(
        description="The OpenAI model ID to use for completions",
        json_schema_extra=combine_hints(
            CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]),
            ActionHint(
                action_uid="openai.get_models",
                hint_type=HintType.POPULATE,
                field_mapping="models",
                selection_type=SelectionType.MANUAL,
                multi_select=False,
            ),
            # Clear reasoning_effort whenever the model changes so a stale
            # level from the previous model isn't silently submitted.
            PropagateHint(to="reasoning_effort", value=""),
        ),
    )

    max_tokens: int = Field(
        4096,
        ge=1,
        description="Maximum number of output tokens to generate",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )

    reasoning_effort: Optional[str] = Field(
        None,
        description=(
            "Reasoning effort level for the model. "
            "Available options are fetched from the MODEL_CAPABILITIES admin "
            "configuration based on the selected model. "
            "Leave empty to use the model's default."
        ),
        json_schema_extra=combine_hints(
            CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]),
            ActionHint(
                action_uid="openai.get_reasoning_levels",
                hint_type=HintType.POPULATE,
                field_mapping="reasoning_levels",
                selection_type=SelectionType.MANUAL,
                multi_select=False,
                # Populated after model_name is chosen.
                dependencies={"model_name": "model_name"},
            ),
        ),
    )

    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific kwargs passed through as is"
    )
