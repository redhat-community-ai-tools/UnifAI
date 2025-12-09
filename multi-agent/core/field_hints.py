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
    Simple hint that references an action for field population or validation.
    """
    action_uid: str = Field(
        ..., 
        description="Name of the action to invoke"
    )
    hint_type: HintType = Field(
        ..., 
        description="Type of hint (populate, validate)"
    )
    field_mapping: Optional[str] = Field(
        None,
        description="Target field in action output for population hints"
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


def combine_hints(*hints: Union[ActionHint, HiddenHint, SecretHint]) -> Dict[str, Any]:
    """
    Combine multiple hints into a single json_schema_extra structure.
    
    Args:
        *hints: Variable number of hint objects
        
    Returns:
        Combined hints structure for json_schema_extra
        
    Example:
        json_schema_extra=combine_hints(
            ActionHint(...),
            HiddenHint(...),
            SecretHint(...)
        )
    """
    combined = {"hints": {}}
    
    for hint in hints:
        hint_data = hint.to_hints()
        combined["hints"].update(hint_data["hints"])
    
    return combined