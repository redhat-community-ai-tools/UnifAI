"""
Unit tests for BlueprintVersionDocument — GENIE-1336.

Covers:
  - Construction defaults (created_at, _id)
  - Deep-copy isolation of spec_dict_snapshot
  - change_summary truncation at 500 chars
  - to_summary() shape
  - to_detail() shape (includes blueprint_id and snapshot)
"""

import copy
import pytest
from datetime import datetime, timezone

from mas.blueprints.models.blueprint_version import BlueprintVersionDocument


@pytest.mark.unit
class TestBlueprintVersionDocumentConstruction:
    """BlueprintVersionDocument construction and defaults."""

    def test_minimal_construction_sets_defaults(self):
        """created_at defaults to UTC now; _id defaults to None."""
        before = datetime.now(timezone.utc)
        doc = BlueprintVersionDocument(
            blueprint_id="bp-1",
            version=1,
            spec_dict_snapshot={"name": "hello"},
            created_by="user-a",
        )
        after = datetime.now(timezone.utc)

        assert doc.blueprint_id == "bp-1"
        assert doc.version == 1
        assert doc.created_by == "user-a"
        assert doc.change_summary is None
        assert doc._id is None
        # created_at should be within the test window
        assert before <= doc.created_at <= after

    def test_explicit_values_are_preserved(self):
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        doc = BlueprintVersionDocument(
            blueprint_id="bp-99",
            version=7,
            spec_dict_snapshot={"x": 1},
            created_by="alice",
            created_at=ts,
            change_summary="Added node X",
            _id="some-mongo-id",
        )

        assert doc.version == 7
        assert doc.created_at == ts
        assert doc.change_summary == "Added node X"
        assert doc._id == "some-mongo-id"


@pytest.mark.unit
class TestBlueprintVersionDocumentImmutability:
    """spec_dict_snapshot is deep-copied on construction."""

    def test_snapshot_is_isolated_from_source_dict(self):
        source = {"nodes": [{"id": "n1", "type": "llm"}]}
        doc = BlueprintVersionDocument(
            blueprint_id="bp-1",
            version=1,
            spec_dict_snapshot=source,
            created_by="user",
        )
        # Mutate the original — doc must not be affected.
        source["nodes"].append({"id": "n2"})
        source["extra"] = "should not appear"

        assert len(doc.spec_dict_snapshot["nodes"]) == 1
        assert "extra" not in doc.spec_dict_snapshot

    def test_to_detail_returns_independent_copy_of_snapshot(self):
        doc = BlueprintVersionDocument(
            blueprint_id="bp-2",
            version=3,
            spec_dict_snapshot={"k": "v"},
            created_by="user",
        )
        detail = doc.to_detail()
        detail["spec_dict_snapshot"]["k"] = "MUTATED"

        # The internal snapshot must not be affected.
        assert doc.spec_dict_snapshot["k"] == "v"


@pytest.mark.unit
class TestChangeSummaryTruncation:
    """change_summary is truncated to 500 characters at construction time."""

    def test_short_summary_is_kept_as_is(self):
        doc = BlueprintVersionDocument(
            blueprint_id="b",
            version=1,
            spec_dict_snapshot={},
            created_by="u",
            change_summary="Short summary.",
        )
        assert doc.change_summary == "Short summary."

    def test_long_summary_is_truncated_to_500(self):
        long_summary = "x" * 600
        doc = BlueprintVersionDocument(
            blueprint_id="b",
            version=1,
            spec_dict_snapshot={},
            created_by="u",
            change_summary=long_summary,
        )
        assert len(doc.change_summary) == 500
        assert doc.change_summary == "x" * 500

    def test_exactly_500_chars_is_not_truncated(self):
        exact = "a" * 500
        doc = BlueprintVersionDocument(
            blueprint_id="b",
            version=1,
            spec_dict_snapshot={},
            created_by="u",
            change_summary=exact,
        )
        assert len(doc.change_summary) == 500

    def test_none_summary_remains_none(self):
        doc = BlueprintVersionDocument(
            blueprint_id="b",
            version=1,
            spec_dict_snapshot={},
            created_by="u",
            change_summary=None,
        )
        assert doc.change_summary is None


@pytest.mark.unit
class TestToSummary:
    """to_summary() returns the correct lightweight dict."""

    def test_to_summary_keys(self):
        ts = datetime(2025, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
        doc = BlueprintVersionDocument(
            blueprint_id="bp-x",
            version=5,
            spec_dict_snapshot={"big": "payload"},
            created_by="carol",
            created_at=ts,
            change_summary="Refactored pipeline",
        )
        summary = doc.to_summary()

        assert set(summary.keys()) == {"version", "created_by", "created_at", "change_summary"}
        assert summary["version"] == 5
        assert summary["created_by"] == "carol"
        assert summary["created_at"] == ts.isoformat()
        assert summary["change_summary"] == "Refactored pipeline"

    def test_to_summary_excludes_snapshot(self):
        doc = BlueprintVersionDocument(
            blueprint_id="bp-y",
            version=2,
            spec_dict_snapshot={"secret": "data"},
            created_by="u",
        )
        summary = doc.to_summary()
        assert "spec_dict_snapshot" not in summary
        assert "blueprint_id" not in summary


@pytest.mark.unit
class TestToDetail:
    """to_detail() includes blueprint_id and the full snapshot."""

    def test_to_detail_keys(self):
        ts = datetime(2025, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
        doc = BlueprintVersionDocument(
            blueprint_id="bp-z",
            version=9,
            spec_dict_snapshot={"nodes": []},
            created_by="dave",
            created_at=ts,
            change_summary=None,
        )
        detail = doc.to_detail()

        assert "version" in detail
        assert "created_by" in detail
        assert "created_at" in detail
        assert "change_summary" in detail
        assert "blueprint_id" in detail
        assert "spec_dict_snapshot" in detail

        assert detail["blueprint_id"] == "bp-z"
        assert detail["spec_dict_snapshot"] == {"nodes": []}

    def test_to_detail_snapshot_is_copy(self):
        """Mutating the returned detail dict does not corrupt the document."""
        doc = BlueprintVersionDocument(
            blueprint_id="bp",
            version=1,
            spec_dict_snapshot={"a": 1},
            created_by="u",
        )
        detail = doc.to_detail()
        detail["spec_dict_snapshot"]["a"] = 999

        assert doc.spec_dict_snapshot["a"] == 1
