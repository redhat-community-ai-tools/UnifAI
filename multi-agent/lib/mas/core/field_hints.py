from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class HintType(Enum):
    """Simple hint types"""
    POPULATE = "populate"
    VALIDATE = "validate" 
    HIDDEN = "hidden"
    SECRET = "secret"


class SelectionType(Enum):
    """Selection type for action hints"""
    AUTOMATIC = "automatic"
    MANUAL = "manual"


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
    display_name: Optional[str] = Field(
        None,
        description="Display name for the field in the UI"
    )
    hint_type: HintType = Field(
        ..., 
        description="Type of hint (populate, validate)"
    )
    field_mapping: Optional[str] = Field(
        None,
        description="Target field in action output for population hints"
    )
    display_field: Optional[str] = Field(
        None,
        description="Dot-notation path to display value (e.g., 'name' or 'name.x'). UI stores full object and uses this to display."
    )
    value_field: Optional[str] = Field(
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
    dependencies: Dict[str, str] = Field(
        default_factory=dict,
        description="Field dependencies for action input (config_field_name -> action_input_field)"
    )
    pagination: bool = Field(
        default=False,
        description="Whether the action supports pagination (has next_cursor, has_more)"
    )
    search: bool = Field(
        default=False,
        description="Whether the action supports search filtering (has search_regex param)"
    )
    on_success: Optional["ActionHint"] = Field(
        default=None,
        description="Action to fire after this action succeeds. "
                    "The chained action receives its own dependencies from the form. "
                    "Skipped when any required dependency value is empty.",
    )

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override to return clean dict for json_schema_extra"""
        return super().model_dump(**kwargs)
    
    def to_hints(self) -> Dict[str, Any]:
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
    field_mapping: Optional[str] = Field(
        None,
        description="Target field in response for validation hints"
    )
    display_field: Optional[str] = Field(
        None,
        description="Dot-notation path to display value (e.g., 'name' or 'items.name'). UI stores full object and uses this to display."
    )
    value_field: Optional[str] = Field(
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
    dependencies: Dict[str, str] = Field(
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

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override to return clean dict for json_schema_extra"""
        return super().model_dump(**kwargs)
    
    def to_hints(self) -> Dict[str, Any]:
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
    reason: Optional[str] = Field(
        None,
        description="Optional reason why field is hidden"
    )

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override to return clean dict for json_schema_extra"""
        return super().model_dump(**kwargs)
    
    def to_hints(self) -> Dict[str, Any]:
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
    reason: Optional[str] = Field(
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

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override to return clean dict for json_schema_extra"""
        return super().model_dump(**kwargs)
    
    def to_hints(self) -> Dict[str, Any]:
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
    dependencies: Dict[str, str] = Field(
        default_factory=dict,
        description="Config field → action input field mapping",
    )

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        return super().model_dump(**kwargs)

    def to_hints(self) -> Dict[str, Any]:
        return {
            "hints": {
                "auth": self.model_dump()
            }
        }


class ConditionalHint(BaseModel):
    """
    Hint for conditional field visibility.

    The UI should only render this field when every condition in
    ``visible_when`` is satisfied (i.e. the named sibling field has the
    specified value).

    Example::

        json_schema_extra=combine_hints(
            SecretHint(),
            ConditionalHint(visible_when={"auth_method": "access_token"}),
        )
    """
    visible_when: Dict[str, Any] = Field(
        ...,
        description="Map of {field_name: required_value}. All must match for the field to be visible.",
    )

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        return super().model_dump(**kwargs)

    def to_hints(self) -> Dict[str, Any]:
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
    value: Optional[Any] = Field(
        default=None,
        description="Fixed value to write. If None, copies the source field's value.",
    )

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        return super().model_dump(**kwargs)

    def to_hints(self) -> Dict[str, Any]:
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

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        return super().model_dump(**kwargs)

    def to_hints(self) -> Dict[str, Any]:
        return {
            "hints": {
                "read_only": self.model_dump()
            }
        }


def combine_hints(*hints: Union[ActionHint, ApiHint, HiddenHint, SecretHint, AuthHint, ConditionalHint, PropagateHint, ReadOnlyHint]) -> Dict[str, Any]:
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
