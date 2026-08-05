from typing import Literal
from pydantic import Field
from mas.core.field_hints import CardHint, CardContext
from ..common.base_config import BaseConditionConfig
from .identifiers import Identifier


class ThresholdConditionConfig(BaseConditionConfig):
    """
    Configuration for a threshold condition:

      - input_key: the key in `state` to compare
      - threshold: numeric cutoff
      - operator: comparison operator
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    input_key: str = Field(
        ..., description="State key to fetch the value",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    threshold: float = Field(
        ..., description="Threshold to compare against",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    operator: Literal[">", "<", ">=", "<=", "==", "!="] = Field(
        ">", description="Comparison operator",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
