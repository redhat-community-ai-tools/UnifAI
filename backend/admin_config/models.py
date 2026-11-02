"""
Admin Config Template models.

Defines the structure for admin-configurable settings:
  Template  ->  Category  ->  Section  ->  Field

The template is the static definition (field types, labels, defaults).
Stored values live in MongoDB keyed by section key.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
#  Field-level models
# ──────────────────────────────────────────────────────────────────────────────

class FieldDefinition(BaseModel):
    """Single configurable field inside a section."""
    key: str
    label: str
    field_type: Literal["string_list", "string", "boolean", "number", "json"]
    description: str = ""
    default: Any = None
    placeholder: str = ""


class SectionDefinition(BaseModel):
    """
    A logical group of fields.

    Each section maps to one document in the admin_config MongoDB collection.

    When values change, the optional ``on_update_*`` fields describe a
    side-effect that should be dispatched:
      - on_update_action: human-readable action name (also returned to UI)
      - on_update_target: service key (resolved to a base URL at runtime)
      - on_update_endpoint: path on that service to POST to
    """
    key: str
    title: str
    description: str = ""
    fields: List[FieldDefinition]
    on_update_action: Optional[str] = None
    on_update_target: Optional[str] = None
    on_update_endpoint: Optional[str] = None


class CategoryDefinition(BaseModel):
    """Top-level grouping shown as a tab / accordion in the UI."""
    key: str
    title: str
    description: str = ""
    sections: List[SectionDefinition]


class AdminConfigTemplate(BaseModel):
    """
    Root template that drives the entire admin configuration page.

    The UI receives this merged with stored values on GET.
    """
    categories: List[CategoryDefinition]


# ──────────────────────────────────────────────────────────────────────────────
#  Stored value model (what lives in MongoDB)
# ──────────────────────────────────────────────────────────────────────────────

class AdminConfigEntry(BaseModel):
    """One persisted config entry keyed by section key."""
    key: str
    value: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────────────────────
#  Merged response model (template + stored values)
# ──────────────────────────────────────────────────────────────────────────────

class FieldValue(BaseModel):
    """A field definition enriched with its current stored value."""
    key: str
    label: str
    field_type: str
    description: str = ""
    default: Any = None
    placeholder: str = ""
    value: Any = None


class SectionValue(BaseModel):
    """Section with merged field values."""
    key: str
    title: str
    description: str = ""
    fields: List[FieldValue]
    on_update_action: Optional[str] = None
    updated_at: Optional[datetime] = None


class CategoryValue(BaseModel):
    """Category with merged section values."""
    key: str
    title: str
    description: str = ""
    sections: List[SectionValue]


class AdminConfigResponse(BaseModel):
    """Full merged response returned to the UI on GET."""
    categories: List[CategoryValue]
