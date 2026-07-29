"""Regression tests: a blueprint referencing a since-deleted resource should
report that as a failing element during validation, not crash the whole
request with a misleading "Blueprint not found" error.

Previously, ``BlueprintResolver.resolve()`` raised a bare ``KeyError(rid)``
the moment it hit *any* unresolvable external ref — including refs nested
deep inside another element's config (e.g. a node's ``providers`` list).
That KeyError propagated out of ``BlueprintService.validate_blueprint()``
uncaught, and the Flask endpoint's generic ``except KeyError`` handler
mislabeled it as "Blueprint not found: '<the missing resource's rid>'",
even though the blueprint itself existed and was visible to the caller.
"""
from typing import Dict, List, Optional

import pytest
from pydantic import BaseModel

from mas.blueprints.models.blueprint import BlueprintDraft, BlueprintDocument, BlueprintResource
from mas.blueprints.resolver import BlueprintResolver
from mas.blueprints.service import BlueprintService
from mas.core.element_meta import ElementConfigMeta
from mas.core.identity import Identity
from mas.core.ref.models import ProviderRef
from mas.elements.common.validator import ElementValidationResult, ValidationContext
from mas.elements.providers.types import ProviderSpec
from mas.resources.models import Resource


class _FakeResourcesService:
    """Minimal stand-in exposing only what BlueprintResolver calls."""

    def get(self, rid: str) -> Resource:
        raise KeyError(rid)

    def get_visible(self, rid: str, *, is_admin: bool = False) -> Resource:
        raise KeyError(rid)

    def resolve_resource(self, resource: Resource, identity: Optional[Identity] = None) -> BaseModel:  # pragma: no cover
        raise AssertionError("resolve_resource should not run when get() fails")


class _FakeBlueprintRepo:
    def __init__(self, doc: BlueprintDocument):
        self._doc = doc

    def load(self, blueprint_id: str) -> BlueprintDocument:
        assert blueprint_id == self._doc.blueprint_id
        return self._doc


class _FakeValidationService:
    def validate_ordered(
        self, configs: List[ElementConfigMeta], context: ValidationContext,
    ) -> Dict[str, ElementValidationResult]:
        # No successfully-resolved elements in these tests.
        assert configs == []
        return {}


def _draft_with_missing_provider_ref(missing_rid: str) -> BlueprintDraft:
    return BlueprintDraft(
        providers=[BlueprintResource[ProviderSpec](rid=ProviderRef.external(missing_rid), config=None)],
        plan=[],
    )


class TestBlueprintResolverTolerance:
    def test_resolve_raises_for_missing_referenced_resource(self):
        resolver = BlueprintResolver(_FakeResourcesService())
        draft = _draft_with_missing_provider_ref("missing-provider")
        with pytest.raises(KeyError):
            resolver.resolve(draft)

    def test_resolve_tolerant_reports_missing_ref_without_raising(self):
        resolver = BlueprintResolver(_FakeResourcesService())
        draft = _draft_with_missing_provider_ref("missing-provider")

        spec, broken_refs = resolver.resolve_tolerant(draft)

        assert spec.providers == []
        assert broken_refs == {
            "missing-provider": "Referenced resource not found: missing-provider",
        }


class TestValidateBlueprintSurfacesBrokenRefs:
    def test_validate_blueprint_reports_broken_ref_as_failing_element(self):
        blueprint_id = "bp-1"
        doc = BlueprintDocument(
            blueprint_id=blueprint_id,
            identity=Identity(type="user", id="alice"),
            spec_dict={
                "providers": [{"rid": "$ref:missing-provider", "config": None}],
                "plan": [],
            },
        )
        service = BlueprintService(
            repo=_FakeBlueprintRepo(doc),
            resolver=BlueprintResolver(_FakeResourcesService()),
            validation_service=_FakeValidationService(),
        )

        result = service.validate_blueprint(blueprint_id=blueprint_id)

        assert result.blueprint_id == blueprint_id
        assert result.is_valid is False
        assert "missing-provider" in result.element_results
        element = result.element_results["missing-provider"]
        assert element.is_valid is False
        assert "missing-provider" in element.messages[0].message
