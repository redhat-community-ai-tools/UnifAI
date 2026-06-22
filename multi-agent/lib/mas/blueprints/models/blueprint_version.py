"""
Domain model for an immutable Blueprint version snapshot.

Design notes
------------
* ``BlueprintVersionDocument`` is a plain Python dataclass (not Pydantic)
  because snapshots are write-once / never mutated after creation.
* ``__post_init__`` deep-copies the incoming ``spec_dict_snapshot`` so the
  stored value is independent of the caller's dict reference.
* ``to_summary()`` deliberately omits the snapshot to keep list responses
  lightweight; ``to_detail()`` includes it for single-version fetches.

GENIE-1336
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class BlueprintVersionDocument:
    """
    Immutable point-in-time snapshot of a blueprint's ``spec_dict``.

    Fields
    ------
    blueprint_id
        Parent blueprint identifier.
    version
        Monotonically increasing version number (≥ 1).  Matches the
        ``version`` on the parent ``BlueprintDocument`` at the time the
        snapshot was taken.
    spec_dict_snapshot
        Deep copy of the blueprint's ``spec_dict`` at this version.
    created_by
        User identifier who triggered the write that created this snapshot.
    created_at
        UTC timestamp of when the snapshot was recorded.
    change_summary
        Optional human-readable description of what changed (≤ 500 chars).
    _id
        MongoDB ObjectId as string, assigned after persistence.
    """

    blueprint_id: str
    version: int
    spec_dict_snapshot: dict[str, Any]
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    change_summary: str | None = None
    _id: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # Deep-copy to ensure stored snapshot is isolated from caller's dict.
        object.__setattr__(
            self,
            "spec_dict_snapshot",
            copy.deepcopy(self.spec_dict_snapshot),
        )

        # --- Validation -------------------------------------------------------
        if self.version < 1:
            raise ValueError(f"version must be ≥ 1; got {self.version!r}")
        if not self.blueprint_id:
            raise ValueError("blueprint_id must be a non-empty string")
        if self.change_summary is not None and len(self.change_summary) > 500:
            object.__setattr__(self, "change_summary", self.change_summary[:500])

    # ------------------------------------------------------------------
    # Projections
    # ------------------------------------------------------------------

    def to_summary(self) -> dict[str, Any]:
        """
        Lightweight projection suitable for list responses.

        Deliberately excludes ``spec_dict_snapshot`` to keep payloads small.
        """
        return {
            "blueprint_id": self.blueprint_id,
            "version": self.version,
            "created_by": self.created_by,
            "created_at": _iso(self.created_at),
            "change_summary": self.change_summary,
        }

    def to_detail(self) -> dict[str, Any]:
        """
        Full projection for single-version fetch endpoints.

        Extends ``to_summary()`` with the ``spec_dict_snapshot`` payload.
        """
        return {
            **self.to_summary(),
            "spec_dict_snapshot": copy.deepcopy(self.spec_dict_snapshot),
        }



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    """Return an ISO-8601 string with UTC timezone suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
