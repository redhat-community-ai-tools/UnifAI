from typing import Optional, Literal
from pydantic import Field
from mas.core.field_hints import CardHint, CardContext
from ..common.base_config import BaseLLMConfig
from .identifiers import Identifier


class MockLLMConfig(BaseLLMConfig):
    """
    A "mock" LLM for testing—returns a constant or echo.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    model_name: Optional[str] = Field(
        None,
        description="Ignored by the mock implementation"
    )
    constant_response: Optional[str] = Field(
        None,
        description="If set, always return this string instead of real inference",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
