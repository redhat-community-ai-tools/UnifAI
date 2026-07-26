from pydantic import BaseModel, Field, Extra, HttpUrl
from mas.core.field_hints import SecretHint, ReadOnlyHint, CardHint, combine_hints


class BaseLLMConfig(BaseModel):
    """
    Common fields for any LLM provider.
    Pure configuration schema - no UI metadata.
    
    Subclasses must define a matching Literal type field for discrimination.
    UI metadata is now handled by ElementSpec classes.
    """
    model_name: str = Field(
        description="The OpenAI model ID to use for completions",
        json_schema_extra=CardHint(contexts=["builtin", "custom"]).to_hints(),
    )
    api_key: str = Field(
        "EMPTY",
        description="API key or token for OpenAI",
        json_schema_extra=combine_hints(
            SecretHint(reason="API credentials should be masked"),
            ReadOnlyHint(read_only=False),
        ),
    )
    base_url: HttpUrl = Field(
        description="Base URL for the OpenAI API",
        title="Base URL",
        json_schema_extra=CardHint(contexts=["custom"]).to_hints(),
    )
    verify_ssl: bool = Field(
        True,
        description="Verify SSL certificates. Set to False for self-signed certs."
    )

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
