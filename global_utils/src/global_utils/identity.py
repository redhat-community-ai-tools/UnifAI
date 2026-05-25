"""
Platform-wide Identity model.

An Identity is the minimal, portable reference to "who owns this thing".
It can represent either a single user or a team.  All services should use
this model instead of raw ``user_id`` strings.

This file is under global_utils and not under Identity as global_utils is a package we can use
In the future we would want to have the identity module as a package as well
NOTE this file is for the identity model, and not the identity service.
"""
from enum import Enum

from pydantic import BaseModel


class IdentityType(str, Enum):
    USER = "user"
    TEAM = "team"


class Identity(BaseModel):
    """Lightweight owner reference -- user or team.

    Carries enough metadata so that consuming services can display
    the owner without a round-trip to the directory.
    """
    type: IdentityType
    id: str
    display_name: str = ""

    @property
    def is_user(self) -> bool:
        return self.type == IdentityType.USER

    @property
    def is_team(self) -> bool:
        return self.type == IdentityType.TEAM

    @classmethod
    def user(cls, user_id: str, display_name: str = "") -> "Identity":
        return cls(type=IdentityType.USER, id=user_id,
                   display_name=display_name or user_id)

    @classmethod
    def team(cls, team_id: str, display_name: str = "") -> "Identity":
        return cls(type=IdentityType.TEAM, id=team_id,
                   display_name=display_name or team_id)


# ──────────────────────────────────────────────────────────────────────────────
# Identity resolution from raw string parameters
# ──────────────────────────────────────────────────────────────────────────────

_IDENTITY_TYPE_MAP: dict[str, IdentityType] = {
    "user": IdentityType.USER,
    "team": IdentityType.TEAM,
}
_VALID_IDENTITY_TYPES: frozenset[str] = frozenset(_IDENTITY_TYPE_MAP.keys())


def resolve_identity(
    user_id: str,
    identity_type: str = "user",
    display_name: str = "",
) -> Identity:
    """Build an ``Identity`` from raw string parameters.

    Raises ``ValueError`` if *identity_type* is not a recognised value.
    Has no Flask dependency — safe to call from any service layer.
    """
    if identity_type not in _VALID_IDENTITY_TYPES:
        raise ValueError(
            f"Invalid identityType '{identity_type}'; "
            f"must be one of {sorted(_VALID_IDENTITY_TYPES)}"
        )
    id_type = _IDENTITY_TYPE_MAP[identity_type]
    if id_type == IdentityType.TEAM:
        return Identity.team(team_id=user_id, display_name=display_name)
    return Identity.user(user_id=user_id, display_name=display_name)
