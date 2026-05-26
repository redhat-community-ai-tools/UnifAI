from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator

from mas.core.identity import Identity

# Session staging (SessionInputProjector) sets this tag so OAuth (e.g. Google MCP) looks up
# tokens for the acting human while ``identity`` remains the team (or other owner).
CREDENTIAL_USER_ID_TAG = "credential_user_id"


class ExecutionContext(BaseModel):
    """Runtime execution context — who, what scope, when.

    Immutable (frozen) so mutations go through explicit copy methods.
    ``extra="ignore"`` ensures backward compatibility when deserializing
    older DB documents that carried fields no longer present.
    """

    identity: Identity
    scope: str = "public"
    engine_name: str = ""
    engine_handle: Optional[str] = None

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    tags: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _backfill_identity(cls, values: Any) -> Any:
        """Legacy docs stored without identity — synthesize a placeholder."""
        if isinstance(values, dict) and values.get("identity") is None:
            values["identity"] = {
                "type": "user", "id": "unknown",
                "display_name": "unknown",
            }
        return values

    @property
    def identity_id(self) -> str:
        return self.identity.id

    def with_scope(self, scope: str) -> ExecutionContext:
        return self.model_copy(update={"scope": scope})

    def with_credential_user(self, credential_user_id: str = "") -> ExecutionContext:
        """Copy with per-user OAuth key in ``tags`` (used when ``identity`` is a team).

        A team id is never a valid OAuth credential user, so passing the team's
        own id is silently ignored — callers do not need to pre-filter.
        """
        cu = (credential_user_id or "").strip()
        if not cu or (self.identity.is_team and cu == self.identity.id):
            return self
        tags = dict(self.tags or {})
        tags[CREDENTIAL_USER_ID_TAG] = cu
        return self.model_copy(update={"tags": tags})

    def credential_user_id(self) -> str:
        """Return the credential user id for OAuth lookups.

        For individual sessions this is the identity id.  For team sessions
        the per-member credential user is stored in ``tags``; if absent (e.g.
        the session was not submitted via the HTTP layer) the caller will
        receive an empty string and must handle the missing-credential case.
        """
        cu = (self.tags or {}).get(CREDENTIAL_USER_ID_TAG, "")
        if cu:
            return str(cu).strip()
        if self.identity.is_team:
            return ""
        return self.identity.id

    def mark_finished(self) -> ExecutionContext:
        return self.model_copy(update={"finished_at": datetime.now(timezone.utc)})


class ExecutionContextHolder:
    """Mutable reference to an immutable ExecutionContext.

    Created at build time (uninitialised).  Filled at execution time
    (real values).  Elements receive a closure over this object — they
    read current values when they need them.

    Fail-fast: accessing ``context``, ``scope``, or ``identity_id`` before
    the holder is filled raises ``RuntimeError`` instead of returning
    silent defaults.
    """

    __slots__ = ("_ctx",)

    def __init__(self) -> None:
        self._ctx: Optional[ExecutionContext] = None

    @property
    def context(self) -> ExecutionContext:
        if self._ctx is None:
            raise RuntimeError(
                "ExecutionContext not initialised — "
                "ensure lifecycle.begin() runs before element execution"
            )
        return self._ctx

    @context.setter
    def context(self, value: ExecutionContext) -> None:
        self._ctx = value

    @property
    def scope(self) -> str:
        return self.context.scope

    @property
    def identity_id(self) -> str:
        return self.context.identity_id

    @property
    def identity(self) -> Identity:
        return self.context.identity
