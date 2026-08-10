from typing import Any
from pydantic import BaseModel, Field
from enum import Enum


class HintType(Enum):
    """Simple hint types"""
    POPULATE = "populate"
    VALIDATE = "validate" 
    HIDDEN = "hidden"
    SECRET = "secret"
    FILE_UPLOAD = "file_upload"


class SelectionType(Enum):
    """Selection type for action hints"""
    AUTOMATIC = "automatic"
    MANUAL = "manual"


class CardContext(str, Enum):
    """Card ownership context(s) a field may be scoped to."""
    BUILTIN = "builtin"
    CUSTOM = "custom"


class ActionHint(BaseModel):
    """
    Hint that references an action for field population or validation.

    ``on_success`` allows declarative chaining: when the primary action
    succeeds, the UI fires the chained action with its own dependency
    mapping.  Neither action knows about the other — the hint is the
    orchestrator, the UI is the executor.
    """
    action_uid: str = Field(
        ..., 
        description="Name of the action to invoke"
    )
    display_name: str | None = Field(
        None,
        description="Display name for the field in the UI"
    )
    hint_type: HintType = Field(
        ..., 
        description="Type of hint (populate, validate)"
    )
    field_mapping: str | None = Field(
        None,
        description="Target field in action output for population hints"
    )
    display_field: str | None = Field(
        None,
        description="Dot-notation path to display value (e.g., 'name' or 'name.x'). UI stores full object and uses this to display."
    )
    value_field: str | None = Field(
        None,
        description="Dot-notation path to stored value (e.g., 'documents.id')"
    )
    multi_select: bool = Field(
        default=False,
        description="Whether this field supports multiple selections"
    )
    selection_type: SelectionType = Field(
        default=None,
        description="Selection type: automatic (auto-populate) or manual (user triggers)"
    )
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="Field dependencies for action input (config_field_name -> action_input_field)"
    )
    constants: dict[str, Any] = Field(
        default_factory=dict,
        description="Static values always sent to the action (action_input_field -> value). "
                    "Unlike dependencies which read from form fields, constants are fixed.",
    )
    pagination: bool = Field(
        default=False,
        description="Whether the action supports pagination (has next_cursor, has_more)"
    )
    search: bool = Field(
        default=False,
        description="Whether the action supports search filtering (has search_regex param)"
    )
    on_success: "ActionHint | None" = Field(
        default=None,
        description="Action to fire after this action succeeds. "
                    "The chained action receives its own dependencies from the form. "
                    "Skipped when any required dependency value is empty.",
    )

    def to_hints(self) -> dict[str, Any]:
        """Return the proper structure for json_schema_extra hints"""
        return {
            "hints": {
                "action": self.model_dump()
            }
        }


ActionHint.model_rebuild()


class ApiHint(BaseModel):
    """
    Hint that references an API endpoint directly for field population or validation.
    Use when action system is not needed or endpoint already exists.
    """
    endpoint: str = Field(
        ..., 
        description="API endpoint path (e.g., '/api/resources/resource.validate')"
    )
    method: str = Field(
        default="POST",
        description="HTTP method (GET, POST, etc.)"
    )
    hint_type: HintType = Field(
        ..., 
        description="Type of hint (populate, validate)"
    )
    field_mapping: str | None = Field(
        None,
        description="Target field in response for validation hints"
    )
    display_field: str | None = Field(
        None,
        description="Dot-notation path to display value (e.g., 'name' or 'items.name'). UI stores full object and uses this to display."
    )
    value_field: str | None = Field(
        None,
        description="Dot-notation path to stored value (e.g., 'items.id')"
    )
    multi_select: bool = Field(
        default=False,
        description="Whether this field supports multiple selections"
    )
    selection_type: SelectionType = Field(
        default=None,
        description="Selection type: automatic (auto-trigger) or manual (user triggers)"
    )
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="Field dependencies (config_field_name -> request_field_name)"
    )
    pagination: bool = Field(
        default=False,
        description="Whether the endpoint supports pagination"
    )
    search: bool = Field(
        default=False,
        description="Whether the endpoint supports search filtering"
    )

    def to_hints(self) -> dict[str, Any]:
        """Return the proper structure for json_schema_extra hints"""
        return {
            "hints": {
                "api": self.model_dump()
            }
        }


class HiddenHint(BaseModel):
    """
    Simple hint to hide a field from the UI.
    """
    hint_type: HintType = Field(default=HintType.HIDDEN)
    reason: str | None = Field(
        None,
        description="Optional reason why field is hidden"
    )

    def to_hints(self) -> dict[str, Any]:
        """Return the proper structure for json_schema_extra hints"""
        return {
            "hints": {
                "hidden": self.model_dump()
            }
        }


class SecretHint(BaseModel):
    """
    Hint to mark a field as containing sensitive/secret data.
    UI should render this as a password field (masked) with show/hide toggle.
    """
    hint_type: HintType = Field(default=HintType.SECRET)
    reason: str | None = Field(
        None,
        description="Optional reason why field contains secret data"
    )
    mask_char: str = Field(
        default="•",
        description="Character to use for masking (default: bullet)"
    )
    allow_reveal: bool = Field(
        default=False,
        description="Whether to show eye icon to reveal secret temporarily"
    )

    def to_hints(self) -> dict[str, Any]:
        """Return the proper structure for json_schema_extra hints"""
        return {
            "hints": {
                "secret": self.model_dump()
            }
        }


class AuthHint(BaseModel):
    """
    Hint that marks a field as an interactive authentication trigger.

    The UI renders this as a Sign In / auth status component instead
    of a normal input.  It calls the specified action to check status
    and initiate the OAuth flow when needed.

    Example::

        json_schema_extra=combine_hints(
            ConditionalHint(visible_when={"auth_method": "sign_in"}),
            AuthHint(action_uid="auth.discovery",
                     dependencies={"mcp_url": "mcp_url"}),
        )
    """
    action_uid: str = Field(
        ...,
        description="Action to call for auth status check / login initiation",
    )
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="Config field → action input field mapping",
    )

    def to_hints(self) -> dict[str, Any]:
        return {
            "hints": {
                "auth": self.model_dump()
            }
        }


class FileUploadHint(BaseModel):
    """Hint that tells the UI to render a file-picker for this field.

    The user selects a file via the OS picker, the UI uploads it to
    ``upload_endpoint`` for format validation, and the returned content
    string is stored in the form field. Combine with ``SecretHint`` to
    also mask the stored value.

    Example::

        json_schema_extra=combine_hints(
            FileUploadHint(accept=".pem,.crt,.key"),
            SecretHint(reason="Certificate content"),
        )
    """
    hint_type: HintType = Field(default=HintType.FILE_UPLOAD)
    accept: str = Field(
        default=".pem,.crt,.key",
        description="Comma-separated file extensions for the OS picker",
    )
    max_size_bytes: int = Field(
        default=16384,
        description="Maximum file size in bytes",
    )
    upload_endpoint: str = Field(
        default="/resources/resource.upload-file",
        description="Backend endpoint for upload and format validation",
    )
    validate_format: str = Field(
        default="pem",
        description="Format to validate on the backend (e.g. 'pem')",
    )

    def to_hints(self) -> dict[str, Any]:
        return {
            "hints": {
                "file_upload": self.model_dump()
            }
        }


class ConditionalHint(BaseModel):
    """
    Hint for conditional field visibility.

    The UI should only render this field when every condition in
    ``visible_when`` is satisfied (i.e. the named sibling field has the
    specified value).

    Values can be plain scalars (exact match) or operator objects:

    * ``"access_token"``  — field must equal ``"access_token"``
    * ``{"in": ["a", "b"]}`` — field must be one of the listed values
    * ``{"not_in": ["a", "b"]}`` — field must NOT be one of the listed values

    Examples::

        ConditionalHint(visible_when={"auth_method": "access_token"})
        ConditionalHint(visible_when={"auth_method": {"not_in": ["none", "access_token"]}})
    """
    visible_when: dict[str, Any] = Field(
        ...,
        description="Map of {field_name: required_value_or_operator}. "
                    "All must match for the field to be visible. "
                    "Values can be scalars (exact match) or operator objects like {\"not_in\": [...]}.",
    )

    def to_hints(self) -> dict[str, Any]:
        return {
            "hints": {
                "conditional": self.model_dump()
            }
        }


class PropagateHint(BaseModel):
    """
    When this field changes, propagate to another field.

    If ``value`` is omitted the field's own new value is copied.
    If ``value`` is provided that fixed value is written instead
    (useful for clearing a target on change).

    Example::

        PropagateHint(to="credential_token")            # mirror value
        PropagateHint(to="credential_token", value="")   # clear on change
    """
    to: str = Field(
        ...,
        description="Target field name to propagate to",
    )
    value: Any | None = Field(
        default=None,
        description="Fixed value to write. If None, copies the source field's value.",
    )

    def to_hints(self) -> dict[str, Any]:
        return {
            "hints": {
                "propagate": self.model_dump()
            }
        }


class ReadOnlyHint(BaseModel):
    """
    Hint marking a field's configurability for built-in resources.

    Baked into the pydantic config schema on each field:
    - ``read_only=True``  → field is locked for end-users on built-in elements.
    - ``read_only=False`` → field is user-configurable (per-user overlay).

    Fields without this hint default to read-only when served via
    ``get_builtin_schema()``.  For non-built-in resources the hint is
    ignored and all fields remain editable.
    """
    read_only: bool = Field(
        default=True,
        description="When True, the field cannot be edited by users on built-in resources"
    )

    def to_hints(self) -> dict[str, Any]:
        return {
            "hints": {
                "read_only": self.model_dump()
            }
        }


class CardHint(BaseModel):
    """
    Hint marking a field as displayable on an element's inventory card.

    Opt-in only: fields without this hint never appear on a card, regardless
    of element type. ``contexts`` scopes display to built-in and/or custom
    (user-created) elements independently, so the same field can be surfaced
    differently depending on ownership — e.g. an MCP server's ``mcp_url`` is
    useful to show on a custom (user-configured) card but redundant on a
    built-in one.

    A field marked ``SecretHint`` is never rendered on a card even if it also
    carries this hint — that exclusion is enforced by card-rendering
    consumers, not by this hint itself.

    ``empty_text`` covers fields whose "unset" state still has a meaningful
    display value — e.g. an MCP provider's ``tool_names`` being empty means
    "all tools from the server", not "nothing to show". Without it, empty
    values are simply omitted from the card (the default, existing
    behavior).

    Example::

        json_schema_extra=combine_hints(
            CardHint(contexts=[CardContext.CUSTOM]),
        )

        json_schema_extra=combine_hints(
            CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM], empty_text="All tools"),
        )
    """
    contexts: list[CardContext] = Field(
        ...,
        description="Which card ownership context(s) this field should be shown on.",
    )
    empty_text: str | None = Field(
        default=None,
        description="Fallback text shown on the card when the field's value is empty/unset, "
                    "instead of omitting the field entirely (e.g. 'All tools', 'All documents').",
    )

    def to_hints(self) -> dict[str, Any]:
        return {
            "hints": {
                "card": self.model_dump(exclude_none=True)
            }
        }


def combine_hints(*hints: ActionHint | ApiHint | HiddenHint | SecretHint | AuthHint | ConditionalHint | PropagateHint | FileUploadHint | ReadOnlyHint | CardHint) -> dict[str, Any]:
    """
    Combine multiple hints into a single json_schema_extra structure.
    
    Args:
        *hints: Variable number of hint objects
        
    Returns:
        Combined hints structure for json_schema_extra
        
    Example:
        json_schema_extra=combine_hints(
            ActionHint(...),
            ApiHint(...),
            HiddenHint(...),
            SecretHint(...)
        )
    """
    combined = {"hints": {}}
    
    for hint in hints:
        hint_data = hint.to_hints()
        combined["hints"].update(hint_data["hints"])
    
    return combined
