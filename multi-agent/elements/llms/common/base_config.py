from pydantic import BaseModel, Field, Extra, HttpUrl
from core.field_hints import SecretHint


class BaseLLMConfig(BaseModel):
    """
    Common fields for any LLM provider.
    Pure configuration schema - no UI metadata.
    
    Subclasses must define a matching Literal type field for discrimination.
    UI metadata is now handled by ElementSpec classes.
    """
    model_name: str = Field(
        description="The OpenAI model ID to use for completions"
    )
    api_key: str = Field(
        "EMPTY",
        description="API key or token for OpenAI",
        json_schema_extra=SecretHint(reason="API credentials should be masked").to_hints()
    )
    base_url: HttpUrl = Field(
        description="Base URL for the OpenAI API"
    )

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
