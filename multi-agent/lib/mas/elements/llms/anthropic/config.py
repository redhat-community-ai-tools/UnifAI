from typing import Literal, Dict, Any, Optional
from pydantic import Field, Extra
from pydantic import BaseModel
from mas.core.field_hints import SecretHint
from .identifiers import Identifier


class AnthropicConfig(BaseModel):
    """Configuration for the Anthropic (Claude) Messages API."""
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    model_name: str = Field(
        default="claude-sonnet-4-5",
        description="The Claude model ID to use (e.g., claude-opus-4-1, claude-sonnet-4-5, claude-haiku-4-5)"
    )

    api_key: str = Field(
        default="",
        description="Anthropic API key",
        json_schema_extra=SecretHint(reason="API credentials should be masked").to_hints()
    )

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Sampling temperature (0.0 to 1.0)"
    )

    max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Maximum number of tokens to generate (required by the Anthropic API)"
    )

    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Top-p (nucleus) sampling parameter"
    )

    top_k: Optional[int] = Field(
        default=None,
        description="Top-k sampling parameter"
    )

    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific kwargs passed through as is"
    )

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
