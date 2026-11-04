"""Force-delete orchestration: auth, strategy dispatch, and cleanup ownership."""
from unittest.mock import Mock

import pytest

from mas.core.caller_scope import CallerScope
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.core.ref.raw_blueprint_spec import (
    remove_resource_ref_from_catalogue,
    remove_resource_ref_from_nested_dict,
)
from mas.resources.deletion.service import ResourceDeletionService
from mas.resources.deletion.strategies import DeleteStrategy
from mas.resources.errors import ResourceAccessDeniedError
from mas.resources.models import Resource


def _resource(rid: str, category: ResourceCategory, *, type_: str = "t") -> Resource:
    return Resource(
        rid=rid,
        identity=Identity.user("bob"),
        category=category,
        type=type_,
        name=rid,
        cfg_dict={},
    )


def _service(target: Resource, replacement: Resource | None = None):
    registry = Mock()

    def _get(rid: str) -> Resource:
        if replacement is not None and rid == replacement.rid:
            return replacement
        if rid == target.rid:
            return target
        raise KeyError(rid)

    registry.get.side_effect = _get
    registry.check_usage.return_value = (["bp-1"], ["res-1"])
    resources = Mock()
    resources.guard_write_access.return_value = target
    if replacement is not None:
        resources.get_visible.return_value = replacement
    bp_refs = Mock()
    service = ResourceDeletionService(registry, bp_refs, resources)
    caller = CallerScope(identity=Identity.user("bob"))
    return service, registry, bp_refs, resources, caller


class TestDeleteStrategyMap:
    def test_every_category_has_one_strategy(self):
        mapping = DeleteStrategy.build_strategy_map()
        assert set(mapping) == set(ResourceCategory)


class TestRawSpecRefRemoval:
    def test_nested_ref_field_is_dropped_not_nulled(self):
        cleaned = remove_resource_ref_from_nested_dict(
            {
                "tools": ["$ref:keep", "$ref:gone"],
                "llm": "$ref:gone",
                "note": None,
                "name": "x",
            },
            "gone",
        )
        assert cleaned == {
            "tools": ["$ref:keep"],
            "note": None,
            "name": "x",
        }

    def test_catalogue_drops_prefixed_and_bare_rid(self):
        spec = remove_resource_ref_from_catalogue(
            {
                "llms": [
                    {"rid": "$ref:gone", "name": "a"},
                    {"rid": "gone", "name": "b"},
                    {"rid": "$ref:keep", "name": "c"},
                ]
            },
            "gone",
        )
        assert spec["llms"] == [{"rid": "$ref:keep", "name": "c"}]


class TestForceDelete:
    def test_replace_rewrites_refs_then_deletes_through_facade(self):
        target = _resource("old", ResourceCategory.LLM)
        replacement = _resource("new", ResourceCategory.LLM)
        service, registry, bp_refs, resources, caller = _service(target, replacement)

        service.force_delete("old", "replace", "new", caller=caller, username="bob")

        resources.guard_write_access.assert_called_once_with("old", caller, username="bob")
        resources.get_visible.assert_called_once_with("new", caller=caller)
        registry.remap_nested_refs.assert_called_once_with("old", {"old": "new"})
        bp_refs.remap_refs.assert_called_once_with("bp-1", {"old": "new"})
        resources.delete.assert_called_once_with("old")

    def test_wrong_mode_does_not_mutate(self):
        target = _resource("old", ResourceCategory.LLM)
        service, registry, bp_refs, resources, caller = _service(target)

        with pytest.raises(ValueError, match="not permitted"):
            service.force_delete("old", "cascade", caller=caller)

        registry.remap_nested_refs.assert_not_called()
        bp_refs.delete.assert_not_called()
        resources.delete.assert_not_called()

    def test_hidden_replacement_does_not_mutate(self):
        target = _resource("old", ResourceCategory.LLM)
        replacement = _resource("new", ResourceCategory.LLM)
        service, registry, _bp_refs, resources, caller = _service(target, replacement)
        resources.get_visible.side_effect = KeyError("new")

        with pytest.raises(KeyError):
            service.force_delete("old", "replace", "new", caller=caller)

        registry.remap_nested_refs.assert_not_called()
        resources.delete.assert_not_called()

    def test_replacement_must_match_category(self):
        target = _resource("old", ResourceCategory.LLM)
        replacement = _resource("new", ResourceCategory.CONDITION)
        service, registry, _bp_refs, resources, caller = _service(target, replacement)

        with pytest.raises(ValueError, match="same category"):
            service.force_delete("old", "replace", "new", caller=caller)

        registry.remap_nested_refs.assert_not_called()
        resources.delete.assert_not_called()

    def test_detach_includes_sandboxes(self):
        target = _resource("sb", ResourceCategory.SANDBOX)
        service, registry, bp_refs, resources, caller = _service(target)

        service.force_delete("sb", "detach", caller=caller)

        registry.strip_nested_refs.assert_called_once_with("sb")
        bp_refs.strip_refs.assert_called_once_with("bp-1", "sb")
        resources.delete.assert_called_once_with("sb")

    def test_cascade_deletes_blueprints_without_stripping_them(self):
        target = _resource("agent", ResourceCategory.NODE)
        service, registry, bp_refs, resources, caller = _service(target)

        service.force_delete("agent", "cascade", caller=caller)

        bp_refs.delete.assert_called_once_with("bp-1")
        bp_refs.strip_refs.assert_not_called()
        registry.strip_nested_refs.assert_called_once_with("agent")
        resources.delete.assert_called_once_with("agent")

    def test_access_denied_stops_before_any_rewrite(self):
        target = _resource("old", ResourceCategory.TOOL)
        service, registry, _bp_refs, resources, caller = _service(target)
        resources.guard_write_access.side_effect = ResourceAccessDeniedError("old")

        with pytest.raises(ResourceAccessDeniedError):
            service.force_delete("old", "detach", caller=caller)

        registry.get.assert_not_called()
        registry.strip_nested_refs.assert_not_called()
        resources.delete.assert_not_called()
