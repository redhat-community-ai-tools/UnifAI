"""
Unit tests for BlueprintDocument model — version field regression (GENIE-1336).

Covers:
  - ``version`` field defaults to 1 when the field is absent
  - ``version`` field is preserved when explicitly set
  - Pre-existing documents without a ``version`` field are backward-compatible
    (Pydantic default kicks in)
  - Parsing via ``model_validate`` from a raw dict mirrors what pymongo returns
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from pydantic import ValidationError

from mas.blueprints.models.blueprint import BlueprintDocument


# ── Helpers ──────────────────────────────────────────────────────────────────────────────


def _minimal_doc_dict(**overrides) -> dict:
    """Return the minimum dict that parses as a valid BlueprintDocument."""
    base = {
        "blueprint_id": "bp-test-001",
        "name": "Test Blueprint",
        "spec_dict": {},
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


# ── version field defaults ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestBlueprintDocumentVersionField:
    """The ``version`` field was added by GENIE-1336 with default=1."""

    def test_version_defaults_to_1_when_absent(self):
        """A dict without 'version' (legacy stored doc) produces version=1."""
        doc = BlueprintDocument.model_validate(_minimal_doc_dict())
        assert doc.version == 1

    def test_version_preserved_when_set_to_1(self):
        """Explicit version=1 is round-tripped without modification."""
        doc = BlueprintDocument.model_validate(_minimal_doc_dict(version=1))
        assert doc.version == 1

    def test_version_preserved_when_set_to_higher_value(self):
        """A blueprint at version 7 keeps that value after parsing."""
        doc = BlueprintDocument.model_validate(_minimal_doc_dict(version=7))
        assert doc.version == 7

    def test_version_is_integer(self):
        """The version field is always an int (not a float or string)."""
        doc = BlueprintDocument.model_validate(_minimal_doc_dict())
        assert isinstance(doc.version, int)

    def test_version_is_positive(self):
        """Default version must be ≥ 1 (never 0 or negative)."""
        doc = BlueprintDocument.model_validate(_minimal_doc_dict())
        assert doc.version >= 1

    def test_serialisation_includes_version(self):
        """model_dump() always emits the version field."""
        doc = BlueprintDocument.model_validate(_minimal_doc_dict(version=5))
        dumped = doc.model_dump()
        assert "version" in dumped
        assert dumped["version"] == 5

    def test_json_serialisation_includes_version(self):
        """model_dump(mode='json') also emits version."""
        doc = BlueprintDocument.model_validate(_minimal_doc_dict(version=3))
        dumped = doc.model_dump(mode="json")
        assert dumped["version"] == 3


# ── Backward compatibility ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestBlueprintDocumentBackwardCompatibility:
    """Legacy documents stored before GENIE-1336 had no ``version`` field.

    These tests confirm the migration path: Pydantic's default=1 silently
    fills the gap so old documents work immediately without a schema migration.
    """

    def test_legacy_doc_without_version_parses_successfully(self):
        """Parsing a doc that has no ``version`` key must NOT raise."""
        raw = _minimal_doc_dict()
        raw.pop("version", None)  # Ensure key is truly absent.
        doc = BlueprintDocument.model_validate(raw)
        assert doc.version == 1  # Default applied.

    def test_none_version_is_rejected(self):
        """Pydantic rejects version=None — None is not a valid version."""
        with pytest.raises(ValidationError):
            BlueprintDocument.model_validate(_minimal_doc_dict(version=None))

    def test_existing_blueprints_retain_their_version_after_round_trip(self):
        """An already-versioned document survives a model_dump → model_validate cycle."""
        original = BlueprintDocument.model_validate(_minimal_doc_dict(version=4))
        dumped = original.model_dump()
        reloaded = BlueprintDocument.model_validate(dumped)
        assert reloaded.version == 4
