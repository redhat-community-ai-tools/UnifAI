"""Every path that builds elements must receive the identity provider.

A memory tool with ``access.mode: team`` refuses to be built without it, so a build path that
forgets to forward it (graph nodes, conditions, late-bound container wiring) fails at construction.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from mas.blueprints.models.blueprint import BlueprintSpec
from mas.catalog.element_registry import ElementRegistry
from mas.core.element_deps import ElementBuildContext
from mas.core.execution_context import ExecutionContextHolder
from mas.elements.common.exceptions import PluginConfigurationError
from mas.elements.tools.memory import adapters
from mas.engine.distributed.node_executor import NodeExecutor
from mas.session.building import WorkflowSessionFactory

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from test_memory_tool import FakeEmbedder, FakeFacts, FakeIndex, FakeStore  # noqa: E402


class Provider:
    def is_member(self, username, team_id):
        return True


@pytest.fixture(scope="module")
def element_registry():
    from mas.catalog.spec_discoverer import SpecDiscoverer

    reg = ElementRegistry()
    for spec_cls in SpecDiscoverer().discover():
        try:
            reg.register_spec_class(spec_cls)
        except ValueError:  # duplicates left in the subclass tree by other test modules
            pass
    return reg


@pytest.fixture(autouse=True)
def fake_backends(monkeypatch):
    monkeypatch.setattr(adapters, "MongoFactStore", lambda *a, **k: FakeFacts())
    monkeypatch.setattr(adapters, "MongoMemoryTextStore", lambda *a, **k: FakeStore())
    monkeypatch.setattr(adapters, "QdrantMemoryIndex", lambda *a, **k: FakeIndex())
    monkeypatch.setattr(adapters, "ServiceEmbedder", lambda *a, **k: FakeEmbedder())


def blueprint(mode="team"):
    return BlueprintSpec.model_validate({
        "name": "bp", "description": "d",
        "providers": [], "llms": [], "retrievers": [], "nodes": [], "plan": [],
        "tools": [{
            "rid": "mem", "name": "mem", "type": "memory",
            "config": {"type": "memory", "scope_id": "team-1", "access": {"mode": mode}},
        }],
    })


def test_session_registry_gets_the_identity_provider(element_registry):
    factory = WorkflowSessionFactory(element_registry, "langgraph")
    with pytest.raises(PluginConfigurationError):
        factory.build_session_registry(blueprint())
    factory.set_identity_provider(Provider())
    registry = factory.build_session_registry(blueprint())
    assert registry is not None


def test_runtime_plan_gets_the_identity_provider(element_registry):
    factory = WorkflowSessionFactory(element_registry, "langgraph")
    with pytest.raises(PluginConfigurationError):
        factory.build_runtime_plan(blueprint())
    factory.set_identity_provider(Provider())
    assert factory.build_runtime_plan(blueprint()) is not None


def test_constructor_provider_is_used_too(element_registry):
    factory = WorkflowSessionFactory(element_registry, "langgraph", identity_provider=Provider())
    assert factory.build_session_registry(blueprint()) is not None


def test_mode_none_needs_no_provider(element_registry):
    factory = WorkflowSessionFactory(element_registry, "langgraph")
    assert factory.build_session_registry(blueprint("none")) is not None


def test_build_context_is_shared_by_all_paths(element_registry):
    seen = []
    factory = WorkflowSessionFactory(element_registry, "langgraph", identity_provider=Provider())
    real = factory._session_builder.build
    factory._session_builder.build = lambda bp, deps=None: (seen.append(deps), real(bp, deps=deps))[1]
    factory.build_runtime_plan(blueprint("none"))
    factory.build_session_registry(blueprint("none"))
    assert len(seen) == 2
    for deps in seen:
        assert isinstance(deps, ElementBuildContext)
        assert deps.identity_provider is not None
        assert isinstance(deps.execution_ctx, ExecutionContextHolder)


def test_node_executor_uses_the_factory_it_is_given(element_registry):
    """The worker hands the container's factory to NodeExecutor; a late-bound provider reaches it."""
    factory = WorkflowSessionFactory(element_registry, "langgraph")
    executor = NodeExecutor(session_factory=factory, tracing_service=SimpleNamespace())
    factory.set_identity_provider(Provider())  # the container does this after building the factory
    assert executor._factory is factory
    assert executor._factory.build_runtime_plan(blueprint()) is not None


def test_worker_and_container_share_one_factory():
    """Static guard: the temporal worker takes the container's factory, the container binds the provider."""
    root = Path(__file__).resolve().parents[3]
    worker = (root / "adapters/inbound/temporal/worker.py").read_text()
    container = (root / "bootstrap/container.py").read_text()
    assert "session_factory=container.session_factory" in worker
    assert "WorkflowSessionFactory(" not in worker
    assert "self.session_factory.set_identity_provider(self.identity_provider)" in container
