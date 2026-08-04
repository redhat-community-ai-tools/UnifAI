"""Unit tests: ShareCloner._compute_closure() built-in resource handling.

Verifies that:
- PUBLIC built-ins are skipped (not cloned) and don't raise.
- DRAFT built-ins trigger ShareCloneError.
- Mixed closures (custom depends on public built-in) succeed and only clone custom.
"""
from typing import Any, Optional, Tuple
from unittest.mock import create_autospec, MagicMock

import pytest

from mas.sharing.cloner import ShareCloner, CloneContext, ShareCloneError
from mas.resources.models import Resource
from mas.resources.service import ResourcesService
from mas.blueprints.service import BlueprintService
from mas.catalog.element_registry import ElementRegistry
from mas.core.identity import Identity
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility


def _build_cloner(
    resources_service: Optional[ResourcesService] = None,
) -> Tuple[ShareCloner, ResourcesService, ElementRegistry]:
    resources_service = resources_service or create_autospec(ResourcesService, instance=True)
    bp_service = create_autospec(BlueprintService, instance=True)
    element_registry = create_autospec(ElementRegistry, instance=True)
    return ShareCloner(resources_service, bp_service, element_registry), resources_service, element_registry


def _make_builtin_resource(rid: str, visibility: ResourceVisibility) -> Resource:
    return Resource(
        rid=rid,
        identity=Identity.user("system"),
        category=ResourceCategory.PROVIDER.value,
        type="fake_provider",
        name=f"builtin-{rid}",
        cfg_dict={},
        ownership=ResourceOwnership.BUILTIN,
        visibility=visibility,
    )


def _make_custom_resource(rid: str, owner: str = "alice", deps_cfg: Optional[dict] = None) -> Resource:
    return Resource(
        rid=rid,
        identity=Identity.user(owner),
        category=ResourceCategory.PROVIDER.value,
        type="fake_provider",
        name=f"custom-{rid}",
        cfg_dict=deps_cfg or {},
    )


class TestComputeClosureBuiltinHandling:
    """Tests for built-in resource handling in _compute_closure."""

    def test_public_builtin_skipped_no_error(self) -> None:
        """A PUBLIC built-in dependency is silently skipped (not cloned)."""
        cloner, resources_service, element_registry = _build_cloner()
        public_builtin = _make_builtin_resource("builtin-1", ResourceVisibility.PUBLIC)
        resources_service.get.return_value = public_builtin

        ctx = CloneContext(sender_id="alice", recipient_id="bob")
        result = cloner._compute_closure({"builtin-1"}, ctx)

        assert "builtin-1" not in result

    def test_draft_builtin_raises_share_clone_error(self) -> None:
        """A DRAFT built-in triggers ShareCloneError."""
        cloner, resources_service, element_registry = _build_cloner()
        draft_builtin = _make_builtin_resource("builtin-draft", ResourceVisibility.DRAFT)
        resources_service.get.return_value = draft_builtin

        ctx = CloneContext(sender_id="alice", recipient_id="bob")

        with pytest.raises(ShareCloneError, match="draft built-in"):
            cloner._compute_closure({"builtin-draft"}, ctx)

    def test_mixed_closure_clones_only_custom(self) -> None:
        """Custom resource depending on a public built-in: only custom is cloned."""
        cloner, resources_service, element_registry = _build_cloner()

        custom = _make_custom_resource("custom-1", owner="alice")
        public_builtin = _make_builtin_resource("builtin-pub", ResourceVisibility.PUBLIC)

        resources_service.get.side_effect = lambda rid: {
            "custom-1": custom,
            "builtin-pub": public_builtin,
        }[rid]

        class FakeSchema:
            def __init__(self, **kwargs: Any) -> None:
                pass

        element_registry.get_schema.return_value = FakeSchema

        from unittest.mock import patch
        with patch("mas.sharing.cloner.RefWalker") as mock_walker:
            mock_walker.external_rids.return_value = {"builtin-pub"}

            ctx = CloneContext(sender_id="alice", recipient_id="bob")
            result = cloner._compute_closure({"custom-1"}, ctx)

        assert "custom-1" in result
        assert "builtin-pub" not in result
