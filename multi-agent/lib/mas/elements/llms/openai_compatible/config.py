from typing import Literal, Dict, Any, Optional
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
    max_retries: int = Field(
        2, ge=0, le=5,
        description=(
            "Automatic retries on connection errors and 5xx responses. "
            "HTTP 429 is never retried: it is reported to the user at once."
        ),
    )
    timeout_seconds: float = Field(
        120.0, gt=0.0,
        description="Request timeout in seconds",
    )
    metadata_lookup_url: Optional[str] = Field(
        None,
        description=(
            "Optional URL template containing '{response_id}' (the completion id "
            "returned by the endpoint) and/or '{request_id}' (the id sent in "
            "request_id_header). When set, the "
            "backend fetches an explanation of how a response was produced "
            "(e.g. which model served it and why) with the acting user's "
            "identity and attaches it to the response metadata. Best effort: "
            "failures are ignored."
        ),
    )
    request_id_header: str = Field(
        "",
        description=(
            "Optional header name. When set, a fresh request id (uuid4 hex) is sent under "
            "this header on every call, and can be used as '{request_id}' in "
            "metadata_lookup_url for endpoints that publish explanations under the "
            "caller-supplied id rather than the completion id. Empty = not sent."
        ),
    )
    metadata_lookup_timeout: float = Field(
        2.0, gt=0.0, le=30.0,
        description="Timeout in seconds for the metadata_lookup_url request",
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
