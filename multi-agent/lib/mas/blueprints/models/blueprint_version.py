"""
Blueprint version snapshot model — GENIE-1336.

Every time a blueprint is updated the *previous* state is captured here as
an immutable snapshot.  The collection is append-only: documents are never
modified or deleted in normal operation.

This module is pure-domain: zero external / infrastructure imports.
"""

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class BlueprintVersionDocument:
    """Immutable snapshot of a blueprint's ``spec_dict`` at a specific version.

    Stored in the ``blueprint_versions`` MongoDB collection.

    Attributes:
        blueprint_id: References the parent blueprint's ``blueprint_id``.
            Stored as a plain string (not a DBRef) for query performance.
        version: Version number this snapshot represents. Matches the
            ``version`` field on the parent blueprint at the time the
            snapshot was created.
        spec_dict_snapshot: Deep copy of the blueprint ``spec_dict`` at
            the time of the snapshot.  Never a diff — always a complete copy.
        created_by: ``user_id`` or service-account that triggered the update.
        created_at: UTC timestamp of snapshot creation.
        change_summary: Optional human-readable description (≤ 500 chars).
        _id: MongoDB ObjectId string, populated after insertion.
    """

    blueprint_id: str
    version: int
    spec_dict_snapshot: dict
    created_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    change_summary: Optional[str] = None
    _id: Optional[str] = None  # Set by repository after insert

    def __post_init__(self) -> None:
        # Enforce immutability: deep-copy so callers cannot mutate the snapshot.
        object.__setattr__(self, "spec_dict_snapshot", copy.deepcopy(self.spec_dict_snapshot))
        # Truncate change_summary to the spec-mandated 500 char limit.
        if self.change_summary and len(self.change_summary) > 500:
            object.__setattr__(self, "change_summary", self.change_summary[:500])

    # ──────────────────────────────────────────────────────────────────────
    # Serialisation helpers
    # ──────────────────────────────────────────────────────────────────────

    def to_summary(self) -> dict:
        """Lightweight dict suitable for paginated list responses.

        Deliberately excludes ``spec_dict_snapshot`` to keep payloads small.
        """
        return {
            "version": self.version,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "change_summary": self.change_summary,
        }

    def to_detail(self) -> dict:
        """Full dict including ``spec_dict_snapshot`` for single-version responses."""
        return {
            **self.to_summary(),
            "blueprint_id": self.blueprint_id,
            "spec_dict_snapshot": copy.deepcopy(self.spec_dict_snapshot),
        }
