from typing import Literal, Dict, Any
from pydantic import Field, HttpUrl
from mas.core.field_hints import CardHint, CardContext
from ..common.base_config import BaseLLMConfig
from .identifiers import Identifier


class OpenAICompatibleConfig(BaseLLMConfig):
    """
    Configuration for any OpenAI-compatible Chat Completions API.

    Works with vLLM, LocalAI, Ollama, Azure OpenAI, and any server that
    implements the ``/v1/chat/completions`` endpoint.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    temperature: float = Field(
        0.7, ge=0.0, le=1.0,
        description="Sampling temperature",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    max_tokens: int = Field(
        4096,
        ge=1,
        description="Maximum number of tokens to generate",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific kwargs passed through as is",
    )
    forward_user_token: bool = Field(
        False,
        description=(
            "Send the acting user's own sign-in token as the bearer credential instead of "
            "api_key, for gateways that authorize and account per user. Fails closed when "
            "no valid user token is available."
        ),
    )
    default_headers: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Headers added to every request. Values may reference {session_id}, {user}, "
            "{identity}, {identity_type}, {scope}, {node_uid}, {node_name}, {node_type} "
            "and {tag.<key>} (session tags); a header with an unresolved reference is omitted."
        ),
    )
