"""Force-delete orchestration: auth, strategy dispatch, and cleanup ownership."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from mas.blueprints.models.blueprint import BlueprintDocument
from mas.blueprints.ref_service import BlueprintRefService
from mas.core.caller_scope import CallerScope
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.core.ref.raw_blueprint_spec import (
    extract_ref_ids_from_raw_spec,
    remove_resource_ref_from_catalogue,
    remove_resource_ref_from_nested_dict,
)
from mas.collaboration.models import TeamEditLockHolder
from mas.collaboration.service import EditLockKind
from mas.resources.deletion.models import BlueprintUsageDetail
from mas.resources.deletion.service import ResourceDeletionService
from mas.resources.deletion.strategies import DeleteStrategy
from mas.resources.errors import ResourceAccessDeniedError, ResourceLockedError
from mas.resources.models import Resource
from mas.resources.ports import ResourceServicePort
from mas.resources.registry import ResourcesRegistry
from tests.unit.resources.conftest import FakeResourceRepository
from adapters.outbound.mongo.resource_repository import MongoResourceRepository


def _resource(
    rid: str,
    category: ResourceCategory,
    *,
    type_: str = "t",
    cfg_dict: dict | None = None,
    nested_refs: list[str] | None = None,
) -> Resource:
    return Resource(
        rid=rid,
        identity=Identity.user("bob"),
        category=category,
        type=type_,
        name=rid,
        cfg_dict=cfg_dict or {},
        nested_refs=list(nested_refs or []),
    )


class MemoryBlueprintRepository:
    """In-memory stand-in for the blueprint methods deletion rewrites."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}
        self.fail_update_ids: dict[str, int] = {}
        self.update_attempts: list[tuple[str, bool]] = []

    def add(
        self,
        blueprint_id: str,
        spec_dict: dict,
        rid_refs: list[str],
        identity: Identity | None = None,
    ) -> None:
        self._docs[blueprint_id] = {
            "blueprint_id": blueprint_id,
            "identity": identity or Identity.user("bob"),
            "spec_dict": copy.deepcopy(spec_dict),
            "rid_refs": list(rid_refs),
        }

    def load(self, blueprint_id: str) -> BlueprintDocument:
        doc = self._docs.get(blueprint_id)
        if doc is None:
            raise KeyError(f"No blueprint with id={blueprint_id}")
        return BlueprintDocument(
            blueprint_id=doc["blueprint_id"],
            identity=doc["identity"],
            spec_dict=copy.deepcopy(doc["spec_dict"]),
            rid_refs=list(doc["rid_refs"]),
        )

    def update_raw(
        self, *, blueprint_id: str, spec_dict: dict, rid_refs: list[str],
    ) -> bool:
        remaining = self.fail_update_ids.get(blueprint_id, 0)
        if remaining > 0:
            self.fail_update_ids[blueprint_id] = remaining - 1
            self.update_attempts.append((blueprint_id, False))
            raise RuntimeError(f"blueprint update failed: {blueprint_id}")
        if blueprint_id not in self._docs:
            raise KeyError(f"No blueprint with id={blueprint_id}")
        self.update_attempts.append((blueprint_id, True))
        current = self._docs[blueprint_id]
        changed = current["spec_dict"] != spec_dict or current["rid_refs"] != list(rid_refs)
        current["spec_dict"] = copy.deepcopy(spec_dict)
        current["rid_refs"] = list(rid_refs)
        return changed

    def delete(self, blueprint_id: str) -> bool:
        return self._docs.pop(blueprint_id, None) is not None

    def list_direct_usage(self, rid: str) -> list[str]:
        return [bp_id for bp_id, doc in self._docs.items() if rid in doc["rid_refs"]]


@dataclass
class _DeletionHarness:
    service: ResourceDeletionService
    resources: Mock
    caller: CallerScope
    resource_repo: FakeResourceRepository
    bp_repo: MemoryBlueprintRepository
    bp_refs: BlueprintRefService


def _service(
    target: Resource,
    replacement: Resource | None = None,
    *,
    nested: list[Resource] | None = None,
    blueprints: list[tuple[str, dict, list[str]]] | None = None,
    bp_repo: MemoryBlueprintRepository | None = None,
    lock_reader: Mock | None = None,
    identity: Identity | None = None,
) -> _DeletionHarness:
    resource_repo = FakeResourceRepository()
    resource_repo.save(target)
    if replacement is not None:
        resource_repo.save(replacement)
    for doc in nested or []:
        resource_repo.save(doc)

    repo = bp_repo or MemoryBlueprintRepository()
    for blueprint_id, spec_dict, rid_refs in blueprints or []:
        repo.add(blueprint_id, spec_dict, rid_refs)

    registry = ResourcesRegistry(resource_repo, repo)
    bp_refs = BlueprintRefService(repo)
    resources = Mock(spec=ResourceServicePort)
    resources.guard_write_access.return_value = target
    if replacement is not None:
        resources.get_visible.return_value = replacement

    def _delete(rid: str) -> None:
        resource_repo.delete(rid)

    resources.delete.side_effect = _delete
    service = ResourceDeletionService(
        registry, bp_refs, resources, lock_reader=lock_reader,
    )
    caller = CallerScope(identity=identity or Identity.user("bob"))
    return _DeletionHarness(service, resources, caller, resource_repo, repo, bp_refs)


class TestDeleteStrategyMap:
    def test_every_category_has_one_strategy(self):
        mapping = DeleteStrategy.build_strategy_map()
        assert set(mapping) == set(ResourceCategory)


class TestMongoUsageLookup:
    def test_finds_explicit_legacy_ref_missing_from_nested_refs(self):
        repo = MongoResourceRepository.__new__(MongoResourceRepository)
        repo.col = Mock()
        repo.col.find.side_effect = [
            iter([{"_id": "indexed-agent"}]),
            iter([
                {"_id": "legacy-agent", "cfg_dict": {"llm": "$ref:old"}},
                {"_id": "unrelated", "cfg_dict": {"llm": "$ref:other"}},
            ]),
        ]

        assert repo.list_nested_usage("old") == ["indexed-agent", "legacy-agent"]
        assert repo.col.find.call_args_list[1].args[0] == {"nested_refs": {"$ne": "old"}}


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

    def test_extract_includes_ref_strings_and_bare_catalogue_rids(self):
        ids = extract_ref_ids_from_raw_spec(
            {
                "llms": [
                    {"rid": "$ref:old"},
                    {"rid": "bare-keep"},
                    {"rid": ""},
                    {"rid": {"legacy": True}},
                    "not-an-entry",
                ],
                "plan": [{"node": "$ref:other"}],
                "note": "bare-not-a-ref",
            }
        )
        assert ids == {"old", "bare-keep", "other"}


class TestBlueprintSummaries:
    def test_summary_reads_name_and_falls_back_to_id(self):
        target = _resource("old", ResourceCategory.TOOL)
        harness = _service(
            target,
            blueprints=[
                ("named", {"name": "Workflow", "tools": [{"rid": "$ref:old"}]}, ["old"]),
                ("unnamed", {"tools": [{"rid": "$ref:old"}]}, ["old"]),
            ],
        )

        named = harness.bp_refs.get_summary("named")
        unnamed = harness.bp_refs.get_summary("unnamed")

        assert (named.id, named.name) == ("named", "Workflow")
        assert (unnamed.id, unnamed.name) == ("unnamed", "unnamed")
        usage = harness.service.check_usage("old")
        assert {item.id: item.name for item in usage.blueprints} == {
            "named": "Workflow",
            "unnamed": "unnamed",
        }

    def test_malformed_legacy_name_falls_back_on_usage_check(self):
        target = _resource("old", ResourceCategory.TOOL)
        harness = _service(
            target,
            blueprints=[
                (
                    "bp-bad",
                    {"name": {"legacy": True}, "tools": [{"rid": "$ref:old"}]},
                    ["old"],
                ),
            ],
        )

        usage = harness.service.check_usage("old")

        assert usage.blueprints == [BlueprintUsageDetail(id="bp-bad", name="bp-bad")]

    def test_missing_blueprint_falls_back_to_id(self):
        harness = _service(_resource("old", ResourceCategory.TOOL))

        assert harness.service._enrich_blueprints(["gone"]) == [
            BlueprintUsageDetail(id="gone", name="gone")
        ]


class TestForceDelete:
    def test_replace_detects_and_repairs_unindexed_agent_llm_reference(self):
        target = _resource("old", ResourceCategory.LLM, type_="openai_compatible")
        replacement = _resource("new", ResourceCategory.LLM, type_="openai_compatible")
        agent = _resource(
            "agent",
            ResourceCategory.NODE,
            cfg_dict={"llm": "$ref:old"},
            # Simulates a resource saved before nested_refs was maintained.
            nested_refs=[],
        )
        harness = _service(target, replacement, nested=[agent])

        usage = harness.service.check_usage("old")

        assert usage.in_use is True
        assert [(item.id, item.name) for item in usage.resources] == [("agent", "agent")]

        harness.service.force_delete("old", "replace", "new", caller=harness.caller)

        stored_agent = harness.resource_repo.get("agent")
        assert stored_agent.cfg_dict == {"llm": "$ref:new"}
        assert stored_agent.nested_refs == ["new"]

    def test_replace_persists_rewrites_dedupes_and_deletes(self):
        target = _resource("old", ResourceCategory.LLM)
        replacement = _resource("new", ResourceCategory.LLM)
        parent = _resource(
            "parent",
            ResourceCategory.NODE,
            cfg_dict={"llm": "$ref:old", "tools": ["$ref:old", "$ref:keep"]},
            nested_refs=["old", "keep"],
        )
        harness = _service(
            target,
            replacement,
            nested=[parent],
            blueprints=[
                (
                    "bp-1",
                    {
                        "name": "Workflow",
                        "llms": [
                            {"rid": "$ref:old", "name": "a"},
                            {"rid": "$ref:old", "name": "dup"},
                            {"rid": "bare-keep", "name": "legacy"},
                            {"rid": "$ref:other", "name": "c"},
                        ],
                        "plan": [{"node": "$ref:old"}],
                    },
                    ["old"],
                ),
            ],
        )

        harness.service.force_delete(
            "old", "replace", "new", caller=harness.caller, username="bob",
        )

        harness.resources.guard_write_access.assert_called_once_with(
            "old", harness.caller, username="bob",
        )
        harness.resources.get_visible.assert_called_once_with("new", caller=harness.caller)
        harness.resources.delete.assert_called_once_with("old")
        with pytest.raises(KeyError):
            harness.resource_repo.get("old")

        stored_parent = harness.resource_repo.get("parent")
        assert stored_parent.cfg_dict == {
            "llm": "$ref:new",
            "tools": ["$ref:new", "$ref:keep"],
        }
        assert set(stored_parent.nested_refs) == {"new", "keep"}

        stored_bp = harness.bp_repo.load("bp-1")
        assert stored_bp.spec_dict == {
            "name": "Workflow",
            "llms": [
                {"rid": "$ref:new", "name": "a"},
                {"rid": "bare-keep", "name": "legacy"},
                {"rid": "$ref:other", "name": "c"},
            ],
            "plan": [{"node": "$ref:new"}],
        }
        assert set(stored_bp.rid_refs) == {"new", "bare-keep", "other"}

    def test_wrong_mode_does_not_mutate(self):
        target = _resource("old", ResourceCategory.LLM)
        parent = _resource(
            "parent",
            ResourceCategory.NODE,
            cfg_dict={"llm": "$ref:old"},
            nested_refs=["old"],
        )
        spec = {"name": "Workflow", "llms": [{"rid": "$ref:old"}]}
        harness = _service(
            target,
            nested=[parent],
            blueprints=[("bp-1", spec, ["old"])],
        )
        before_parent = harness.resource_repo.get("parent")
        before_bp = harness.bp_repo.load("bp-1")

        with pytest.raises(ValueError, match="not permitted"):
            harness.service.force_delete("old", "cascade", caller=harness.caller)

        assert harness.resource_repo.get("parent").model_dump() == before_parent.model_dump()
        assert harness.bp_repo.load("bp-1").spec_dict == before_bp.spec_dict
        harness.resources.delete.assert_not_called()

    def test_hidden_replacement_does_not_mutate(self):
        target = _resource("old", ResourceCategory.LLM)
        replacement = _resource("new", ResourceCategory.LLM)
        harness = _service(target, replacement)
        harness.resources.get_visible.side_effect = KeyError("new")

        with pytest.raises(KeyError):
            harness.service.force_delete("old", "replace", "new", caller=harness.caller)

        harness.resources.delete.assert_not_called()
        assert harness.resource_repo.get("old").rid == "old"

    def test_replacement_must_match_category(self):
        target = _resource("old", ResourceCategory.LLM)
        replacement = _resource("new", ResourceCategory.CONDITION)
        harness = _service(target, replacement)

        with pytest.raises(ValueError, match="same category"):
            harness.service.force_delete("old", "replace", "new", caller=harness.caller)

        harness.resources.delete.assert_not_called()
        assert harness.resource_repo.get("old").rid == "old"

    def test_detach_persists_nested_and_blueprint_removal(self):
        target = _resource("sb", ResourceCategory.SANDBOX)
        parent = _resource(
            "parent",
            ResourceCategory.NODE,
            cfg_dict={
                "sandbox": "$ref:sb",
                "tools": ["$ref:sb", "$ref:keep"],
                "name": "n",
            },
            nested_refs=["sb", "keep"],
        )
        harness = _service(
            target,
            nested=[parent],
            blueprints=[
                (
                    "bp-1",
                    {
                        "name": "Flow",
                        "sandboxes": [
                            {"rid": "$ref:sb", "name": "s"},
                            {"rid": "sb", "name": "bare"},
                            {"rid": "$ref:keep", "name": "k"},
                            {"rid": "bare-keep", "name": "legacy"},
                        ],
                        "note": "$ref:sb",
                    },
                    ["sb", "bare-keep"],
                ),
            ],
        )

        harness.service.force_delete("sb", "detach", caller=harness.caller)

        harness.resources.delete.assert_called_once_with("sb")
        with pytest.raises(KeyError):
            harness.resource_repo.get("sb")
        stored_parent = harness.resource_repo.get("parent")
        assert stored_parent.cfg_dict == {"tools": ["$ref:keep"], "name": "n"}
        assert stored_parent.nested_refs == ["keep"]
        stored_bp = harness.bp_repo.load("bp-1")
        assert stored_bp.spec_dict == {
            "name": "Flow",
            "sandboxes": [
                {"rid": "$ref:keep", "name": "k"},
                {"rid": "bare-keep", "name": "legacy"},
            ],
        }
        assert set(stored_bp.rid_refs) == {"keep", "bare-keep"}

    def test_cascade_deletes_blueprints_without_stripping_them(self):
        target = _resource("agent", ResourceCategory.NODE)
        parent = _resource(
            "parent",
            ResourceCategory.NODE,
            cfg_dict={"agent": "$ref:agent"},
            nested_refs=["agent"],
        )
        harness = _service(
            target,
            nested=[parent],
            blueprints=[
                ("bp-1", {"name": "Flow", "nodes": [{"rid": "$ref:agent"}]}, ["agent"]),
                ("bp-keep", {"name": "Other", "nodes": [{"rid": "$ref:else"}]}, ["else"]),
            ],
        )

        harness.service.force_delete("agent", "cascade", caller=harness.caller)

        with pytest.raises(KeyError):
            harness.bp_repo.load("bp-1")
        assert harness.bp_repo.load("bp-keep").spec_dict["name"] == "Other"
        assert harness.resource_repo.get("parent").cfg_dict == {}
        assert harness.resource_repo.get("parent").nested_refs == []
        harness.resources.delete.assert_called_once_with("agent")

    def test_access_denied_stops_before_any_rewrite(self):
        target = _resource("old", ResourceCategory.TOOL)
        harness = _service(target)
        harness.resources.guard_write_access.side_effect = ResourceAccessDeniedError("old")

        with pytest.raises(ResourceAccessDeniedError):
            harness.service.force_delete("old", "detach", caller=harness.caller)

        harness.resources.delete.assert_not_called()
        assert harness.resource_repo.get("old").rid == "old"

    def test_later_blueprint_update_failure_restores_persisted_state(self):
        target = _resource("old", ResourceCategory.LLM)
        replacement = _resource("new", ResourceCategory.LLM)
        parent = _resource(
            "parent",
            ResourceCategory.NODE,
            cfg_dict={"llm": "$ref:old"},
            nested_refs=["old"],
        )
        harness = _service(
            target,
            replacement,
            nested=[parent],
            blueprints=[
                (
                    "bp-1",
                    {
                        "name": "First",
                        "llms": [
                            {"rid": "$ref:old", "name": "a"},
                            {"rid": "bare-keep", "name": "legacy"},
                        ],
                    },
                    ["old", "bare-keep"],
                ),
                (
                    "bp-2",
                    {"name": "Second", "llms": [{"rid": "$ref:old", "name": "b"}]},
                    ["old"],
                ),
            ],
        )
        harness.bp_repo.fail_update_ids["bp-2"] = 1
        before_target = harness.resource_repo.get("old")
        before_parent = harness.resource_repo.get("parent")
        before_bp1 = harness.bp_repo.load("bp-1")
        before_bp2 = harness.bp_repo.load("bp-2")

        with pytest.raises(RuntimeError, match="blueprint update failed: bp-2"):
            harness.service.force_delete(
                "old", "replace", "new", caller=harness.caller, username="bob",
            )

        assert harness.resource_repo.get("parent").model_dump() == before_parent.model_dump()
        assert harness.resource_repo.get("old").model_dump() == before_target.model_dump()
        restored_bp1 = harness.bp_repo.load("bp-1")
        restored_bp2 = harness.bp_repo.load("bp-2")
        assert restored_bp1.spec_dict == before_bp1.spec_dict
        assert restored_bp1.rid_refs == before_bp1.rid_refs
        assert restored_bp2.spec_dict == before_bp2.spec_dict
        assert restored_bp2.rid_refs == before_bp2.rid_refs
        assert harness.bp_repo.update_attempts == [
            ("bp-1", True),
            ("bp-2", False),
            ("bp-1", True),
            ("bp-2", True),
        ]
        harness.resources.delete.assert_not_called()

    def test_delete_failure_restores_remaps_and_resource(self):
        target = _resource("old", ResourceCategory.LLM)
        replacement = _resource("new", ResourceCategory.LLM)
        parent = _resource(
            "parent",
            ResourceCategory.NODE,
            cfg_dict={"llm": "$ref:old"},
            nested_refs=["old"],
        )
        harness = _service(
            target,
            replacement,
            nested=[parent],
            blueprints=[
                ("bp-1", {"name": "Flow", "llms": [{"rid": "$ref:old"}]}, ["old"]),
            ],
        )

        def _boom(rid: str) -> None:
            harness.resource_repo.delete(rid)
            raise RuntimeError("delete failed")

        harness.resources.delete.side_effect = _boom
        before_target = harness.resource_repo.get("old")
        before_parent = harness.resource_repo.get("parent")
        before_bp = harness.bp_repo.load("bp-1")

        with pytest.raises(RuntimeError, match="delete failed"):
            harness.service.force_delete(
                "old", "replace", "new", caller=harness.caller, username="bob",
            )

        assert harness.resource_repo.get("old").model_dump() == before_target.model_dump()
        assert harness.resource_repo.get("parent").model_dump() == before_parent.model_dump()
        restored_bp = harness.bp_repo.load("bp-1")
        assert restored_bp.spec_dict == before_bp.spec_dict
        assert restored_bp.rid_refs == before_bp.rid_refs
        harness.resources.delete.assert_called_once_with("old")


def _alice_lock() -> TeamEditLockHolder:
    return TeamEditLockHolder(user_id="alice", display_name="Alice")


def _lock_reader_for(
    *,
    blueprint_holders: dict[str, TeamEditLockHolder | None] | None = None,
    resource_holders: dict[str, TeamEditLockHolder | None] | None = None,
) -> Mock:
    blueprint_holders = blueprint_holders or {}
    resource_holders = resource_holders or {}

    def _batch(team_id: str, kind: str, ids: list[str]) -> dict[str, TeamEditLockHolder | None]:
        source = (
            blueprint_holders if kind == EditLockKind.BLUEPRINT.value else resource_holders
        )
        return {eid: source.get(eid) for eid in ids}

    reader = Mock()
    reader.get_team_edit_locks_batch.side_effect = _batch
    return reader


class TestDependentEditLocks:
    def test_rejects_when_dependent_blueprint_locked_by_other(self):
        target = _resource("old", ResourceCategory.TOOL)
        spec = {"name": "Workflow", "tools": [{"rid": "$ref:old"}]}
        harness = _service(
            target,
            blueprints=[("bp-1", spec, ["old"])],
            lock_reader=_lock_reader_for(blueprint_holders={"bp-1": _alice_lock()}),
            identity=Identity.team("team-eng"),
        )
        before = harness.bp_repo.load("bp-1")

        with pytest.raises(ResourceLockedError) as exc_info:
            harness.service.force_delete(
                "old", "detach", caller=harness.caller, username="bob",
            )

        assert exc_info.value.locked_by_user_id == "alice"
        assert harness.bp_repo.load("bp-1").spec_dict == before.spec_dict
        harness.resources.delete.assert_not_called()

    def test_rejects_when_nested_resource_locked_by_other(self):
        target = _resource("old", ResourceCategory.LLM)
        replacement = _resource("new", ResourceCategory.LLM)
        parent = _resource(
            "parent",
            ResourceCategory.NODE,
            cfg_dict={"llm": "$ref:old"},
            nested_refs=["old"],
        )
        harness = _service(
            target,
            replacement,
            nested=[parent],
            lock_reader=_lock_reader_for(resource_holders={"parent": _alice_lock()}),
            identity=Identity.team("team-eng"),
        )
        before = harness.resource_repo.get("parent")

        with pytest.raises(ResourceLockedError):
            harness.service.force_delete(
                "old", "replace", "new", caller=harness.caller, username="bob",
            )

        assert harness.resource_repo.get("parent").model_dump() == before.model_dump()
        harness.resources.delete.assert_not_called()

    def test_allows_when_lock_held_by_caller(self):
        target = _resource("old", ResourceCategory.TOOL)
        harness = _service(
            target,
            blueprints=[
                ("bp-1", {"name": "Flow", "tools": [{"rid": "$ref:old"}]}, ["old"]),
            ],
            lock_reader=_lock_reader_for(blueprint_holders={"bp-1": _alice_lock()}),
            identity=Identity.team("team-eng"),
        )

        harness.service.force_delete(
            "old", "detach", caller=harness.caller, username="alice",
        )

        harness.resources.delete.assert_called_once_with("old")
        with pytest.raises(KeyError):
            harness.resource_repo.get("old")

    def test_skips_lock_check_in_personal_workspace(self):
        target = _resource("old", ResourceCategory.TOOL)
        lock_reader = _lock_reader_for(blueprint_holders={"bp-1": _alice_lock()})
        harness = _service(
            target,
            blueprints=[
                ("bp-1", {"name": "Flow", "tools": [{"rid": "$ref:old"}]}, ["old"]),
            ],
            lock_reader=lock_reader,
        )

        harness.service.force_delete("old", "detach", caller=harness.caller, username="bob")

        lock_reader.get_team_edit_locks_batch.assert_not_called()
        harness.resources.delete.assert_called_once_with("old")
