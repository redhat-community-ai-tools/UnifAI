from typing import Literal
from pydantic import Field
from mas.elements.conditions.common.base_config import BaseConditionConfig
from mas.core.field_hints import CardHint, CardContext
from .identifiers import Identifier


class RouterBooleanConditionConfig(BaseConditionConfig):
    """
    Configuration for the router boolean condition that returns a configured boolean value.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    boolean_value: bool = Field(
        True,
        description="The boolean value to return (true or false)",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )