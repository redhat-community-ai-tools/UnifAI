"""Regression tests: `ShareCloner._batch_create_resources` must not leave
orphaned resources behind when a save fails partway through the batch —
everything already persisted for this failed clone should be rolled back
before the failure is propagated to the caller.
"""
from typing import Tuple
from unittest.mock import create_autospec

import pytest
from unittest.mock import MagicMock

from mas.sharing.cloner import ShareCloner
from mas.resources.models import Resource
from mas.resources.service import ResourcesService
from mas.blueprints.service import BlueprintService
from mas.catalog.element_registry import ElementRegistry
from mas.core.identity import Identity
from mas.core.enums import ResourceCategory


def _make_resource(rid: str) -> Resource:
    return Resource(
        rid=rid,
        identity=Identity.user("bob"),
        category=ResourceCategory.PROVIDER.value,
        type="fake_provider",
        name=f"resource-{rid}",
        cfg_dict={},
    )


def _build_cloner() -> Tuple[ShareCloner, MagicMock]:
    resources_service = create_autospec(ResourcesService, instance=True)
    bp_service = create_autospec(BlueprintService, instance=True)
    element_registry = create_autospec(ElementRegistry, instance=True)
    # Not exercised by these batch-rollback tests (they operate purely on
    # already-computed docs), but the constructor now requires it.
    builtin_resource_service = MagicMock()
    builtin_resource_service.get_descriptor.return_value = None
    return ShareCloner(resources_service, bp_service, element_registry, builtin_resource_service), resources_service


class TestBatchCreateResourcesRollback:
    """Tests for `ShareCloner._batch_create_resources`'s all-or-nothing rollback behavior."""

    def test_all_succeed_no_rollback(self) -> None:
        cloner, resources_service = _build_cloner()
        docs = [_make_resource("r1"), _make_resource("r2")]

        cloner._batch_create_resources(docs)

        assert resources_service.save_resource.call_count == 2
        resources_service.delete.assert_not_called()

    def test_partial_failure_rolls_back_already_saved_resources(self) -> None:
        cloner, resources_service = _build_cloner()
        docs = [_make_resource("r1"), _make_resource("r2"), _make_resource("r3")]
        resources_service.save_resource.side_effect = [None, None, RuntimeError("boom")]

        with pytest.raises(RuntimeError, match="boom"):
            cloner._batch_create_resources(docs)

        # Only the two that actually succeeded are rolled back, most
        # recently created first (later docs may reference earlier ones).
        deleted_rids = [call.args[0] for call in resources_service.delete.call_args_list]
        assert deleted_rids == ["r2", "r1"]

    def test_first_save_failing_rolls_back_nothing(self) -> None:
        cloner, resources_service = _build_cloner()
        docs = [_make_resource("r1")]
        resources_service.save_resource.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            cloner._batch_create_resources(docs)

        resources_service.delete.assert_not_called()

    def test_rollback_failure_does_not_mask_the_original_error(self) -> None:
        """If cleanup itself fails (e.g. transient DB error), the caller
        must still see the original save failure, not a rollback error."""
        cloner, resources_service = _build_cloner()
        docs = [_make_resource("r1"), _make_resource("r2")]
        resources_service.save_resource.side_effect = [None, RuntimeError("save failed")]
        resources_service.delete.side_effect = RuntimeError("delete failed")

        with pytest.raises(RuntimeError, match="save failed"):
            cloner._batch_create_resources(docs)

        resources_service.delete.assert_called_once_with("r1")
