"""Regression tests for tolerant loading of legacy/removed BlueprintDraft fields.

Blueprints saved while the (since-removed) ``auths`` resource category was
still part of the schema keep ``auths: []`` baked into their stored
``spec_dict`` forever. Because ``BlueprintDraft`` uses ``Extra.forbid``,
reconstructing those documents with a plain ``BlueprintDraft(**spec_dict)``
raises a validation error — this is what broke loading/validating any
blueprint saved before the ``auths`` field was dropped from the model.
"""
import pytest
from pydantic import ValidationError

from mas.blueprints.models.blueprint import BlueprintDraft

_MINIMAL_STORED_DICT = {
    "providers": [],
    "llms": [],
    "retrievers": [],
    "tools": [],
    "nodes": [],
    "conditions": [],
    # Legacy field: removed from the schema, but still present on documents
    # saved before the removal.
    "auths": [],
    "plan": [],
    "name": "legacy blueprint",
    "description": "",
}


class TestBlueprintDraftLegacyFields:
    def test_direct_construction_rejects_legacy_field(self):
        """Sanity check: plain construction is still strict for fresh input."""
        with pytest.raises(ValidationError):
            BlueprintDraft(**_MINIMAL_STORED_DICT)

    def test_from_stored_dict_strips_legacy_field(self):
        draft = BlueprintDraft.from_stored_dict(_MINIMAL_STORED_DICT)
        assert draft.name == "legacy blueprint"
        assert not hasattr(draft, "auths")

    def test_from_stored_dict_preserves_known_fields(self):
        stored = {**_MINIMAL_STORED_DICT, "description": "kept"}
        draft = BlueprintDraft.from_stored_dict(stored)
        assert draft.description == "kept"

    def test_from_stored_dict_still_enforces_required_fields(self):
        """Tolerance only applies to *unknown* keys — a genuinely missing
        required field (e.g. ``plan``) should still raise."""
        stored = {k: v for k, v in _MINIMAL_STORED_DICT.items() if k != "plan"}
        with pytest.raises(ValidationError):
            BlueprintDraft.from_stored_dict(stored)
