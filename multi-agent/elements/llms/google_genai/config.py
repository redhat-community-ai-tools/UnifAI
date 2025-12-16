from typing import Literal, Dict, Any, Optional
from pydantic import Field, Extra
from pydantic import BaseModel
from core.field_hints import SecretHint
from .identifiers import Identifier


class GoogleGenAIConfig(BaseModel):
    """
    Configuration for Google Generative AI (Gemini) API.
    Uses langchain-google-genai's ChatGoogleGenerativeAI.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    model_name: str = Field(
        default="gemini-2.0-flash",
        description="The Gemini model ID to use (e.g., gemini-2.0-flash, gemini-2.5-pro)"
    )

    api_key: str = Field(
        default="",
        description="Google API key for Generative AI",
        json_schema_extra=SecretHint(reason="API credentials should be masked").to_hints()
    )

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0 to 2.0)"
    )

    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum number of tokens to generate (None for model default)"
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

