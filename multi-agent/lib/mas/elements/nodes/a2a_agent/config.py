"""
A2A Agent Node Configuration

Authentication uses the same hint-driven OAuth flow as MCP providers:

- ``auth_method`` dropdown is populated dynamically from the auth server
  registry via ``auth.list_servers`` (options include static entries like
  "none" and "access_token" alongside registered SSO servers). Like MCP's
  ``auth_method``, this is an admin-only decision baked into the resource's
  base config — it carries no ``ReadOnlyHint(read_only=False)``, so it's
  locked on built-in overlays. Each caller then satisfies *that one* method
  with their own credentials via ``sign_in``/``bearer_token``.
- Selecting a registry server shows a **Sign In** button that triggers
  ``auth.discovery``, which builds an OAuth authorization URL and opens
  a popup for the user to authenticate.
- On successful callback the token is persisted in the credential store
  and resolved at runtime via ``auth_service.bind()``.
- New auth servers can be added purely through configuration — no code
  changes required.
"""

from mas.elements.nodes.common.base_config import NodeBaseConfig
from pydantic import Field, HttpUrl
from typing import Optional, Literal
from a2a.types import AgentCard
from .identifiers import Identifier
from mas.core.ref.models import RetrieverRef
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.core.field_hints import (
    ActionHint, HintType, SelectionType,
    SecretHint, AuthHint, HiddenHint, ConditionalHint, PropagateHint, ReadOnlyHint, CardHint, CardContext, combine_hints,
)


class A2AAgentNodeConfig(NodeBaseConfig):
    """
    A2A Agent Node — delegates work to a remote agent via the A2A protocol.

    Authentication is optional and is an admin decision (``auth_method``):
    "none" (no auth needed), "access_token" (each caller supplies their own
    bearer token), or a registered SSO server (each caller signs in via a
    standard OAuth flow, identical to MCP). ``sign_in``/``bearer_token`` are
    the only fields callers configure themselves.
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
                },
            ),
            CardHint(contexts=[CardContext.CUSTOM]),
        ),
    )

    # Open set: StaticAuthMethod values plus registry server identifiers.
    # Admin-controlled (no ReadOnlyHint) — same as McpProviderConfig.auth_method:
    # this decides *how* every caller of a shared built-in agent authenticates,
    # not something each individual user picks for themselves on their overlay.
    auth_method: str = Field(
        default=StaticAuthMethod.NONE.value,
        description="Authentication method",
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
            ReadOnlyHint(read_only=False),
        ),
    )

    bearer_token: Optional[str] = Field(
        default=None,
        description="Bearer token for authentication",
        json_schema_extra=combine_hints(
            SecretHint(allow_reveal=True),
            ConditionalHint(visible_when={
                "auth_method": StaticAuthMethod.ACCESS_TOKEN.value,
            }),
            PropagateHint(to="credential_token"),
            ReadOnlyHint(read_only=False),
        ),
    )

    server_identifier: str = Field(
        default="",
        json_schema_extra=HiddenHint(reason="Set automatically from auth_method selection").to_hints(),
    )

    scheme_type: str = Field(
        default="",
        json_schema_extra=HiddenHint(reason="Set automatically by auth detection").to_hints(),
    )

    credential_token: str = Field(
        default="",
        exclude=True,
        json_schema_extra=HiddenHint(reason="Populated by auth fields").to_hints(),
    )

    agent_card: Optional[AgentCard] = Field(
        default=None,
        description="Pre-fetched agent card (optional, will be fetched if not provided)",
        json_schema_extra=ActionHint(
            action_uid="a2a.get_agent_card",
            hint_type=HintType.POPULATE,
            selection_type=SelectionType.AUTOMATIC,
            field_mapping="agent_card",
            dependencies={"base_url": "base_url"},
        ).to_hints(),
    )

    retriever: Optional[RetrieverRef] = Field(
        None,
        description="Retriever for context augmentation (optional)",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
