from typing import Any, Dict, Literal, List, Optional
from enum import Enum
from .identifiers import Identifier
from pydantic import Field, HttpUrl
from mas.elements.providers.common.base_config import ProviderBaseConfig
from mas.core.field_hints import (
    ActionHint, HintType, SelectionType,
    SecretHint, AuthHint, HiddenHint, ConditionalHint, PropagateHint, ReadOnlyHint, CardHint, CardContext, combine_hints,
)
from .transport.enums import McpTransportType


class McpAuthMethod(str, Enum):
    """How the user authenticates to the MCP server."""
    ACCESS_TOKEN = "access_token"
    SIGN_IN = "sign_in"


class McpProviderConfig(ProviderBaseConfig):
    """
    Connects to a Model-Context-Protocol service via SSE or Streamable HTTP transport.

    Authentication uses a single ``credential_token`` hidden field as the
    credential mailbox.  Both auth paths (bearer token and sign-in) write
    to it, and ``mcp_url`` validation reads from it.  Switching auth
    method clears the mailbox so credentials don't leak between paths.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    transport_type: McpTransportType = Field(
        default=McpTransportType.STREAMABLE_HTTP,
        description="Transport protocol to use for MCP server communication (sse or streamable http)"
    )
    mcp_url: HttpUrl = Field(
        description="MCP server endpoint URL",
        title="MCP URL",
        json_schema_extra=combine_hints(
            ActionHint(
                action_uid="mcp.validate_connection",
                hint_type=HintType.VALIDATE,
                field_mapping="is_reachable",
                dependencies={
                    "mcp_url": "mcp_url",
                    "credential_token": "credential_token",
                    "server_identifier": "server_identifier",
                    "auth_method": "auth_method",
                    "transport_type": "transport_type",
                    "additional_headers": "additional_headers",
                },
                on_success=ActionHint(
                    action_uid="auth.store_credential",
                    hint_type=HintType.VALIDATE,
                    field_mapping="authenticated",
                    dependencies={
                        "mcp_url": "server_url",
                        "bearer_token": "credential",
                    },
                ),
            ),
            CardHint(contexts=[CardContext.CUSTOM]),
        ),
    )
    auth_method: McpAuthMethod = Field(
        default=McpAuthMethod.ACCESS_TOKEN,
        description="Authentication method for this MCP server",
        json_schema_extra=PropagateHint(to="credential_token", value="").to_hints(),
    )
    server_identifier: str = Field(
        default="",
        description="Auth server issuer (set automatically by connection validation)",
        json_schema_extra=HiddenHint(reason="Set automatically by connection validation").to_hints(),
    )
    scheme_type: str = Field(
        default="",
        description="Auth scheme type (set automatically by connection validation)",
        json_schema_extra=HiddenHint(reason="Set automatically by auth detection").to_hints(),
    )
    credential_token: str = Field(
        default="",
        exclude=True,
        description="Resolved credential for connection validation",
        json_schema_extra=HiddenHint(reason="Populated by auth fields").to_hints(),
    )
    sign_in: Optional[str] = Field(
        default=None,
        exclude=True,
        description="Sign in to authenticate with this MCP server",
        json_schema_extra=combine_hints(
            ConditionalHint(visible_when={"auth_method": "sign_in"}),
            AuthHint(
                action_uid="auth.discovery",
                dependencies={
                    "mcp_url": "mcp_url",
                },
            ),
            ReadOnlyHint(read_only=False),
        ),
    )
    bearer_token: Optional[str] = Field(
        default=None,
        description="",
        # No ActionHint(VALIDATE) here — connection validation lives solely
        # on `mcp_url` (which already depends on `credential_token`, kept in
        # sync via PropagateHint below). A second, independent VALIDATE hint
        # on this field used to fire its own `mcp.validate_connection` call
        # in parallel with `mcp_url`'s — since this field is optional, an
        # empty value short-circuited to "valid" before any token was set,
        # and the two concurrent validations could race and disagree,
        # producing the flickering "Valid"/"Invalid" badge under this field.
        json_schema_extra=combine_hints(
            SecretHint(allow_reveal=True),
            ConditionalHint(visible_when={"auth_method": "access_token"}),
            PropagateHint(to="credential_token"),
            ReadOnlyHint(read_only=False),
        ),
    )
    additional_headers: Dict[str, Any] = Field(
        default_factory=dict,
        description="",
        json_schema_extra=combine_hints(
            ConditionalHint(visible_when={"auth_method": "access_token"}),
            ReadOnlyHint(read_only=False),
        ),
    )
    tool_names: Optional[List[str]] = Field(
        default_factory=list,
        description="List of specific tool names to use from the MCP server",
        title="Tool Names",
        json_schema_extra=combine_hints(
            ActionHint(
                action_uid="mcp.get_tools_names",
                hint_type=HintType.POPULATE,
                selection_type=SelectionType.MANUAL,
                field_mapping="tool_names",
                multi_select=True,
                dependencies={
                    "mcp_url": "mcp_url",
                    "server_identifier": "server_identifier",
                    "transport_type": "transport_type",
                    "additional_headers": "additional_headers",
                }
            ),
            ReadOnlyHint(read_only=False),
            CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM], empty_text="All tools"),
        ),
    )
