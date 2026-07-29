"""
A2A Provider Configuration

Authentication uses the same hint-driven OAuth flow as MCP providers:

- ``auth_method`` dropdown is populated dynamically from the auth server
  registry via ``auth.list_servers`` (options include static entries like
  "none" and "access_token" alongside registered SSO servers).
- Selecting a registry server shows a **Sign In** button that triggers
  ``auth.discovery``, which builds an OAuth authorization URL and opens
  a popup for the user to authenticate.
- Selecting ``access_token`` shows a manual bearer-token input instead.
- New auth servers can be added purely through configuration.
"""

from typing import Any, Dict, Literal, Optional
from pydantic import Field, HttpUrl
from mas.elements.providers.common.base_config import ProviderBaseConfig
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.core.field_hints import (
    ActionHint, HintType, SelectionType,
    SecretHint, AuthHint, HiddenHint, ConditionalHint, PropagateHint, CardHint, CardContext, combine_hints,
)
from a2a.types import AgentCard
from .identifiers import Identifier


class A2AProviderConfig(ProviderBaseConfig):
    """
    A2A Provider — connects to a remote A2A-protocol agent.

    Authentication is optional.  When required, the user selects an auth
    server from the dropdown and completes a standard OAuth sign-in flow
    (identical to MCP).  A manual bearer-token path is also available.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE

    base_url: HttpUrl = Field(
        description="Base URL of the A2A agent (e.g., http://localhost:10000)",
        title="Base URL",
        json_schema_extra=combine_hints(
            ActionHint(
                action_uid="a2a.validate_connection",
                hint_type=HintType.VALIDATE,
                field_mapping="is_reachable",
                dependencies={
                    "base_url": "base_url",
                    "credential_token": "credential_token",
                    "bearer_token": "bearer_token",
                    "server_identifier": "server_identifier",
                    "auth_method": "auth_method",
                    "additional_headers": "additional_headers",
                },
            ),
            CardHint(contexts=[CardContext.CUSTOM]),
        ),
    )

    agent_card: Optional[AgentCard] = Field(
        default=None,
        description="Pre-fetched agent card (optional, will be fetched if not provided)",
        json_schema_extra=HiddenHint(reason="Fetched automatically from base_url").to_hints(),
    )

    # Open set: StaticAuthMethod values plus registry server identifiers.
    auth_method: str = Field(
        default=StaticAuthMethod.NONE.value,
        description="Authentication method for this A2A agent",
        json_schema_extra=combine_hints(
            PropagateHint(to="server_identifier"),
            PropagateHint(to="credential_token", value=""),
            ActionHint(
                action_uid="auth.list_servers",
                hint_type=HintType.POPULATE,
                selection_type=SelectionType.MANUAL,
                field_mapping="servers",
                display_field="label",
                value_field="value",
                constants={"category": "a2a"},
            ),
        ),
    )

    # ── SSO sign-in (visible when auth_method is a registry server) ───

    sign_in: Optional[str] = Field(
        default=None,
        exclude=True,
        description="Sign in to authenticate with this A2A agent",
        json_schema_extra=combine_hints(
            ConditionalHint(visible_when={
                "auth_method": {
                    "not_in": [
                        StaticAuthMethod.NONE.value,
                        StaticAuthMethod.ACCESS_TOKEN.value,
                    ],
                },
            }),
            AuthHint(
                action_uid="auth.discovery",
                dependencies={
                    "auth_method": "server_identifier",
                },
            ),
        ),
    )

    # ── Access token path ─────────────────────────────────────────────

    bearer_token: Optional[str] = Field(
        default=None,
        description="Bearer token for authentication",
        json_schema_extra=combine_hints(
            SecretHint(allow_reveal=True),
            ConditionalHint(visible_when={
                "auth_method": StaticAuthMethod.ACCESS_TOKEN.value,
            }),
            PropagateHint(to="credential_token"),
        ),
    )

    # ── Hidden plumbing ───────────────────────────────────────────────

    server_identifier: str = Field(
        default="",
        description="Auth server identifier (set automatically from auth_method selection)",
        json_schema_extra=HiddenHint(reason="Set automatically from auth_method").to_hints(),
    )

    scheme_type: str = Field(
        default="",
        description="Auth scheme type (set automatically by auth detection)",
        json_schema_extra=HiddenHint(reason="Set automatically by auth detection").to_hints(),
    )

    credential_token: str = Field(
        default="",
        exclude=True,
        description="Resolved credential for authenticated requests",
        json_schema_extra=HiddenHint(reason="Populated by auth fields").to_hints(),
    )

    # ── Optional extras ───────────────────────────────────────────────

    additional_headers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional HTTP headers to include in A2A requests",
    )
