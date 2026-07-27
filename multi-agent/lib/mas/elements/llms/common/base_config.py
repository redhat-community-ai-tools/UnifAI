from pydantic import BaseModel, Field, Extra, HttpUrl
from mas.core.field_hints import SecretHint, CardHint, CardContext


class BaseLLMConfig(BaseModel):
    """
    Common fields for any LLM provider.
    Pure configuration schema - no UI metadata.
    
    Subclasses must define a matching Literal type field for discrimination.
    UI metadata is now handled by ElementSpec classes.
    """
    model_name: str = Field(
        description="The OpenAI model ID to use for completions",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    api_key: str = Field(
        "EMPTY",
        description="API key or token for OpenAI",
        # No ReadOnlyHint(read_only=False) here — the API key is set once by
        # whoever creates the LLM resource and is never overridden per-user
        # on built-ins (no "Configure" affordance on the built-in card).
        json_schema_extra=SecretHint(reason="API credentials should be masked").to_hints(),
    )
    base_url: HttpUrl = Field(
        description="Base URL for the OpenAI API",
        title="Base URL",
        json_schema_extra=CardHint(contexts=[CardContext.CUSTOM]).to_hints(),
    )
    verify_ssl: bool = Field(
        True,
        description="Verify SSL certificates. Set to False for self-signed certs."
    )

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
