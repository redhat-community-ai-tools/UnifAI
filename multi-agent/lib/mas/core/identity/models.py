"""
Canonical Identity value object — shared kernel.

This is the single source of truth for the ``Identity`` type used across
all bounded contexts.  Other modules must import from here rather than
defining their own copies.

Example::

    from mas.core.identity.models import Identity, IdentityType

    owner = Identity(type=IdentityType.USER, id="alice")
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class IdentityType(str, Enum):
    """Exhaustive set of identity owner types."""

    USER = "user"
    TEAM = "team"


class Identity(BaseModel):
    """Owner identity — either a user or a team."""

    type: IdentityType
    id: str

    model_config = {"frozen": True}
