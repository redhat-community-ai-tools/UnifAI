"""Scope access control of the memory tool: every branch, with fakes."""
import sys
from pathlib import Path

import pytest

from mas.core.execution_context import CREDENTIAL_USER_ID_TAG, ExecutionContext, ExecutionContextHolder
from mas.core.identity import Identity
from mas.elements.tools.memory.access import (
    OwnerScopeAccessChecker, ScopeAccessDenied, TeamScopeAccessChecker, build_access_checker,
)
from mas.elements.tools.memory.config import AccessMode, MemoryToolConfig
from mas.elements.tools.memory.memory import MemoryTool
from mas.elements.tools.memory.memory_factory import MemoryToolFactory
from mas.core.element_deps import ElementBuildContext

sys.path.insert(0, str(Path(__file__).parent))
from test_memory_tool import FakeEmbedder, FakeFacts, FakeIndex, FakeStore


class FakeProvider:
    def __init__(self, members=(), error=None):
        self.members = set(members)
        self.error = error
        self.calls = []

    def is_member(self, username, team_id):
        self.calls.append((username, team_id))
        if self.error:
            raise self.error
        return (username, team_id) in self.members


def holder_for(user=None, team=None):
    holder = ExecutionContextHolder()
    if user is None and team is None:
        return holder  # never filled
    if team:
        ctx = ExecutionContext(session_id="s", identity=Identity(type="team", id=team, display_name=team))
        ctx = ctx.with_credential_user(user or "")
    else:
        ctx = ExecutionContext(session_id="s", identity=Identity(type="user", id=user, display_name=user))
    holder.context = ctx
    return holder


def make(checker):
    store, index, emb, facts = FakeStore(), FakeIndex(), FakeEmbedder(), FakeFacts()
    tool = MemoryTool("team-1", store, index, emb, facts=facts, access_checker=checker)
    return tool, store, index, facts, emb


ALL_OPS = [
    dict(operation="write", text="Budget note"),
    dict(operation="read", query="budget"),
    dict(operation="set_fact", key="k", value=1),
    dict(operation="get_fact", key="k"),
    dict(operation="list_facts"),
]


def test_team_member_is_allowed():
    provider = FakeProvider(members={("alice", "team-1")})
    tool, store, *_ = make(TeamScopeAccessChecker(provider, holder_for("alice", team="other-team")))
    assert tool.run(operation="write", text="Budget note")["success"] is True
    assert provider.calls[0] == ("alice", "team-1")
    assert len(store.docs) == 1


@pytest.mark.parametrize("args", ALL_OPS)
def test_non_member_is_refused_and_nothing_is_touched(args):
    tool, store, index, facts, emb = make(TeamScopeAccessChecker(FakeProvider(), holder_for("mallory")))
    out = tool.run(**args)
    assert out["success"] is False and "not a member" in out["error"]
    assert store.docs == [] and index.points == {} and facts.docs == {} and emb.calls == 0


@pytest.mark.parametrize("holder", [
    holder_for(),                       # context never filled
    None,                               # no holder at all
    holder_for(team="team-1"),          # team session without credential user
])
def test_no_identity_is_refused(holder):
    provider = FakeProvider(members={("alice", "team-1")})
    tool, store, *_ = make(TeamScopeAccessChecker(provider, holder))
    out = tool.run(operation="write", text="x")
    assert out["success"] is False and "refused" in out["error"]
    assert provider.calls == [] and store.docs == []


def test_identity_provider_error_fails_closed():
    tool, store, *_ = make(TeamScopeAccessChecker(FakeProvider(error=ConnectionError("down")), holder_for("alice")))
    out = tool.run(operation="read", query="x")
    assert out["success"] is False and "could not be verified" in out["error"]
    assert "down" not in out["error"] and store.docs == []


def test_identity_cannot_be_supplied_through_arguments():
    provider = FakeProvider(members={("alice", "team-1")})
    tool, store, *_ = make(TeamScopeAccessChecker(provider, holder_for("mallory")))
    out = tool.run(operation="write", text="x", user="alice", username="alice", author="alice", scope_id="team-1")
    assert out["success"] is False and store.docs == []
    assert provider.calls == [("mallory", "team-1")]


def test_non_boolean_membership_answer_is_not_accepted():
    class Sloppy(FakeProvider):
        def is_member(self, username, team_id):
            return "yes"
    tool, *_ = make(TeamScopeAccessChecker(Sloppy(), holder_for("alice")))
    assert tool.run(operation="read")["success"] is False


def test_owner_mode():
    owner = make(OwnerScopeAccessChecker(holder_for("team-1")))[0]
    assert owner.run(operation="write", text="mine")["success"] is True
    other, store, *_ = make(OwnerScopeAccessChecker(holder_for("bob")))
    out = other.run(operation="write", text="x")
    assert out["success"] is False and "owned by another user" in out["error"] and store.docs == []
    assert make(OwnerScopeAccessChecker(holder_for()))[0].run(operation="read")["success"] is False


def test_unexpected_checker_exception_is_a_refusal():
    class Broken:
        def authorize(self, scope_id):
            raise KeyError("boom")
    tool, store, *_ = make(Broken())
    out = tool.run(operation="write", text="x")
    assert out["success"] is False and "boom" not in out["error"] and store.docs == []


def test_no_checker_keeps_previous_behaviour():
    tool, store, *_ = make(None)
    assert tool.run(operation="write", text="x")["success"] is True


def test_config_default_mode_is_none():
    assert MemoryToolConfig(scope_id="s").access.mode == AccessMode.NONE
    assert MemoryToolConfig(scope_id="s", access={"mode": "team"}).access.mode == AccessMode.TEAM
    with pytest.raises(Exception):
        MemoryToolConfig(scope_id="s", access={"mode": "everyone"})


def test_build_checker_requires_its_dependencies():
    assert build_access_checker(AccessMode.NONE, None, None) is None
    with pytest.raises(ValueError):
        build_access_checker(AccessMode.TEAM, None, holder_for("a"))
    with pytest.raises(ValueError):
        build_access_checker(AccessMode.TEAM, FakeProvider(), None)
    with pytest.raises(ValueError):
        build_access_checker(AccessMode.OWNER, None, None)


def test_factory_wires_checker_from_build_context_and_fails_closed_without_it():
    store, index, emb, facts = FakeStore(), FakeIndex(), FakeEmbedder(), FakeFacts()
    cfg = MemoryToolConfig(scope_id="team-1", access={"mode": "team"})
    backends = dict(store=store, index=index, embedder=emb, facts=facts)
    deps = ElementBuildContext(execution_ctx=holder_for("alice"), identity_provider=FakeProvider())
    tool = MemoryToolFactory().create(cfg, deps=deps, **backends)
    assert tool.run(operation="write", text="x")["success"] is False

    deps_ok = ElementBuildContext(
        execution_ctx=holder_for("alice"), identity_provider=FakeProvider(members={("alice", "team-1")}),
    )
    assert MemoryToolFactory().create(cfg, deps=deps_ok, **backends).run(operation="write", text="x")["success"]

    from mas.elements.common.exceptions import PluginConfigurationError
    with pytest.raises(PluginConfigurationError):
        MemoryToolFactory().create(cfg, **backends)
    with pytest.raises(PluginConfigurationError):
        MemoryToolFactory().create(cfg, deps=ElementBuildContext(execution_ctx=holder_for("a")), **backends)
    # mode none needs nothing
    MemoryToolFactory().create(MemoryToolConfig(scope_id="s"), **backends)
