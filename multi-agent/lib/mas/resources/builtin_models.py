from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from mas.core.enums import ResourceVisibility
from mas.core.identity import Identity


def identity_to_key(identity: Identity) -> str:
    """Derive the storage key from an Identity object."""
    return f"{identity.type.value}:{identity.id}"


class BuiltinResourceDescriptor(BaseModel):
    """Built-in-specific metadata for a ``Resource``, owned entirely by
    ``BuiltinResourceService`` and stored in its own
    ``builtin_resource_descriptors`` collection, joined to the base
    ``resources`` collection by ``rid``.

    Existence of a descriptor for a given ``rid`` *is* the "this resource
    is a built-in" signal — there is no separate ``ownership`` field to
    keep in sync with that existence.
    """
    rid: str
    visibility: ResourceVisibility = ResourceVisibility.DRAFT
    parent_builtin_id: Optional[str] = None
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BuiltinUpdateRequest(BaseModel):
    """Boundary DTO for admin update requests on built-in resources.

    Carries the structured fields from the inbound layer into the service;
    using a Pydantic model (rather than a bare dict) ensures validation and
    type safety at the service boundary.
    """
    config: Optional[Dict[str, Any]] = None
    name: Optional[str] = None
    available_to_all: Optional[bool] = None


class BuiltinUserConfig(BaseModel):
    """
    Per-user/team configuration for a specific built-in resource.

    One document per (resource_id, identity_key) pair.
    ``fields`` stores only the user's overrides — field_name to override value.
    Fields absent from this dict fall back to the resource's ``cfg_dict`` at
    resolution time.
    """
    config_id: str = Field(default_factory=lambda: uuid4().hex)
    resource_id: str
    identity_key: str = Field(description="Format: 'user:<id>' or 'team:<id>'")
    fields: Dict[str, Any] = Field(default_factory=dict)
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
