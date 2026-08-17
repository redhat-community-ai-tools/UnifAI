from typing import Any, Dict, List, Mapping, Optional
from pydantic import BaseModel, ConfigDict


class SessionListFilter(BaseModel):
    """Allowlisted, validated filter for session listing.

    This is the single source of truth for what a client may filter the
    session list by. It crosses every layer (Flask endpoint → service →
    manager → repository port → Mongo adapter) as a typed model rather than
    a raw ``dict`` so that:

    - **only declared fields are filterable** — ``extra="forbid"`` rejects
      unknown keys instead of silently forwarding them into the ``$match``;
    - **values are plain scalars** — a client cannot smuggle MongoDB query
      operators (e.g. ``{"$ne": null}``, ``{"$regex": "..."}``) into the
      match document, since a dict value fails ``str`` validation.

    Extend this model (not an ad-hoc dict) to allow additional filterable
    fields.
    """

    model_config = ConfigDict(extra="forbid")

    blueprint_id: Optional[str] = None

    def to_query(self) -> Dict[str, Any]:
        """Render as a MongoDB ``$match`` fragment.

        Only fields the caller actually set are emitted, so an empty filter
        renders to ``{}`` (matches everything within the identity scope).
        """
        return self.model_dump(exclude_none=True)


class SessionListItem(BaseModel):
    session_id: str
    metadata: Dict[str, Any]
    started_at: str
    last_active_at: str = ""
    blueprint_id: str
    blueprint_exists: bool = True
    status: str = ""

    @classmethod
    def from_doc(cls, doc: Mapping[str, Any], blueprint_exists: bool = True, public_usage_scope: bool = False, blueprint_metadata: Dict[str, Any] = None) -> "SessionListItem":
        rc = doc.get("run_context", {})
        return cls(
            session_id=doc.get("run_id", "") or rc.get("run_id", ""),
            metadata={
                **(blueprint_metadata or {}),
                **doc.get("metadata", {}),
                "public_usage_scope": public_usage_scope,
            },
            started_at=rc.get("started_at") or "",
            last_active_at=rc.get("last_active_at") or "",
            blueprint_id=doc.get("blueprint_id", ""),
            blueprint_exists=blueprint_exists,
            status=doc.get("status", ""),
        )


class PaginationMeta(BaseModel):
    """Pagination envelope metadata for a paginated session listing."""

    total: int
    limit: int
    offset: int
    has_more: bool


class PaginatedSessions(BaseModel):
    """Typed paginated response for ``/session.user.list``.

    Replaces the ad-hoc ``{"sessions": [...], "pagination": {...}}`` dict
    that was previously assembled inline at the Flask boundary.
    """

    sessions: List[SessionListItem]
    pagination: PaginationMeta
