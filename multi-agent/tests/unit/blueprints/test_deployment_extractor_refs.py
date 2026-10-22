"""Node mini-blueprints ship every resource a node references, inline-id or ``$ref:``."""
import pytest
from pydantic import BaseModel

from mas.blueprints.exceptions import UnresolvedResourceEntryError
from mas.blueprints.models.blueprint import BlueprintDraft, BlueprintResource
from mas.blueprints.resolver import BlueprintResolver, check_inline_entries
from mas.core.enums import ResourceCategory
from mas.core.ref.models import LLMRef, ToolRef
from mas.engine.distributed.deployment_extractor import NodeDeploymentExtractor, _collect_refs


class _Cfg(BaseModel):
    llm: LLMRef
    tools: list[ToolRef] = []
    note: str = "plain text, not a ref"


class _Elem:
    def __init__(self, spec):
        self.resource_spec = spec


class _Spec:
    def __init__(self, rid, config):
        self.rid = rid
        self.config = config


class _Registry:
    def __init__(self, store):
        self._store = store

    def get(self, category, rid):
        return self._store[category][rid]


def _extractor(node_cfg, extra=None):
    store = {c: {} for c in ResourceCategory}
    store[ResourceCategory.LLM]["llm1"] = _Elem(_Spec("llm1", _Empty()))
    store[ResourceCategory.TOOL]["tool1"] = _Elem(_Spec("tool1", _Empty()))
    for (cat, rid), spec in (extra or {}).items():
        store[cat][rid] = _Elem(spec)
    node = _Spec("n1", node_cfg)
    store[ResourceCategory.NODE]["n1"] = _Elem(node)
    return NodeDeploymentExtractor(_Registry(store)), node


class _Empty(BaseModel):
    pass


@pytest.mark.parametrize("llm,tool", [("llm1", "tool1"), ("$ref:llm1", "$ref:tool1")])
def test_plain_and_external_ids_are_both_collected(llm, tool):
    ex, node = _extractor(_Cfg(llm=llm, tools=[tool]))
    found = {(c, s.rid) for c, s in ex._collect_dependencies(node)}
    assert found == {(ResourceCategory.LLM, "llm1"), (ResourceCategory.TOOL, "tool1")}


def test_untyped_plain_strings_are_not_mistaken_for_refs():
    ex, node = _extractor(_Cfg(llm="llm1", note="tool1"))
    assert {s.rid for _, s in ex._collect_dependencies(node)} == {"llm1"}


def test_dependencies_are_followed_transitively():
    class ToolCfg(BaseModel):
        llm: LLMRef

    ex, node = _extractor(_Cfg(llm="x", tools=["tool1"]),
                          {(ResourceCategory.TOOL, "tool1"): _Spec("tool1", ToolCfg(llm="llm1")),
                           (ResourceCategory.LLM, "x"): _Spec("x", _Empty())})
    assert {s.rid for _, s in ex._collect_dependencies(node)} == {"x", "tool1", "llm1"}


def test_unknown_ids_are_skipped():
    ex, node = _extractor(_Cfg(llm="nope"))
    assert ex._collect_dependencies(node) == []


def test_collect_refs_still_finds_prefixed_strings():
    assert _collect_refs({"a": ["$ref:x", {"b": "$ref:y"}], "c": "z"}) == {"x", "y"}


# ── entries without a config ──────────────────────────────────────────

def _draft(rid):
    return BlueprintDraft(llms=[{"rid": rid}], plan=[])


def test_plain_id_without_config_is_reported_in_strict_mode():
    with pytest.raises(UnresolvedResourceEntryError) as exc:
        BlueprintResolver(object()).resolve(_draft("llm1"))
    assert "$ref:llm1" in str(exc.value)


def test_plain_id_without_config_is_a_broken_ref_in_tolerant_mode():
    spec, broken = BlueprintResolver(object()).resolve_tolerant(_draft("llm1"))
    assert "llm1" in broken and "$ref:llm1" in broken["llm1"]
    assert spec.llms == []


def test_check_inline_entries_rejects_early_but_accepts_external_refs():
    with pytest.raises(UnresolvedResourceEntryError):
        check_inline_entries(_draft("llm1"))
    check_inline_entries(_draft("$ref:llm1"))
