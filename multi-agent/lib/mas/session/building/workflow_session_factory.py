from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from mas.catalog.element_registry import ElementRegistry
from mas.session.building.element_builder import SessionElementBuilder
from mas.session.domain.session_registry import SessionRegistry
from mas.session.domain.session_record import SessionRecord
from mas.engine.factory import GraphBuilderFactory
from mas.session.domain.workflow_session import WorkflowSession
from mas.graph.state.graph_state import GraphState
from mas.graph.plan_builder import PlanBuilder
from mas.graph.rt_graph_plan import RTGraphPlan
from mas.core.execution_context import ExecutionContextHolder
from mas.core.element_deps import ElementDeps
from mas.blueprints.models.blueprint import BlueprintSpec
from mas.core.auth.service import AuthService

if TYPE_CHECKING:
    from mas.core.platform_config import PlatformConfig


class WorkflowSessionFactory:
    """
    Builds heavy runtime artifacts (plan, graph, registry) for a session.

    Exposes:
      - build_session(record, spec) — full WorkflowSession from a SessionRecord
      - build_runtime_plan()        — plan with bound callables (Temporal nodes)
      - build_session_registry()    — element instances only (Temporal conditions)
    """

    def __init__(
            self,
            element_registry: ElementRegistry,
            engine_name: str,
            auth_service: Optional[AuthService] = None,
            file_retrieve_tool_factory: Optional[Callable] = None,
            platform_config: Optional[PlatformConfig] = None,
    ):
        self._elements = element_registry
        self._engine_name = engine_name
        self._auth_service = auth_service
        self._file_retrieve_tool_factory = file_retrieve_tool_factory
        self._platform_config = platform_config
        self._session_builder = SessionElementBuilder(element_registry)

    @property
    def engine_name(self) -> str:
        return self._engine_name

    def build_runtime_plan(
        self,
        blueprint_spec: BlueprintSpec,
        ctx_holder: Optional[ExecutionContextHolder] = None,
    ) -> RTGraphPlan:
        """
        Build an RTGraphPlan from a blueprint spec.

        Creates all session components, binds callables, injects StepContext.
        The caller owns the ExecutionContextHolder and passes it in.
        """
        holder = ctx_holder if ctx_holder is not None else ExecutionContextHolder()
        deps = ElementDeps(
            execution_ctx=holder,
            auth_service=self._auth_service,
            file_retrieve_tool_factory=self._file_retrieve_tool_factory,
            platform_config=self._platform_config,
        )
        logical_plan = PlanBuilder(self._elements).build(blueprint_spec)
        registry = self._session_builder.build(blueprint_spec, deps=deps)
        return RTGraphPlan(logical_plan, registry, self._elements)

    def build_session_registry(self, blueprint_spec: BlueprintSpec) -> SessionRegistry:
        """
        Build a SessionRegistry from a blueprint spec.

        Creates element instances without building a plan or binding callables.
        Used by Temporal condition activities (conditions don't need a plan).
        """
        return self._session_builder.build(blueprint_spec)

    def build_session(self, record: SessionRecord, blueprint_spec: BlueprintSpec) -> WorkflowSession:
        """
        Build a full WorkflowSession from a persisted SessionRecord.

        Compiles the graph, creates node instances, and wires them into a
        session that shares the record by reference (mutations propagate).
        """
        ctx_holder = ExecutionContextHolder()
        rt_graph_plan = self.build_runtime_plan(blueprint_spec, ctx_holder=ctx_holder)
        rt_graph_plan.pretty_print()

        engine_builder = GraphBuilderFactory(GraphState).create(self._engine_name)
        executable_graph = engine_builder.compile_from_plan(rt_graph_plan)

        return WorkflowSession(
            record=record,
            session_registry=rt_graph_plan.session_registry,
            rt_graph_plan=rt_graph_plan,
            executable_graph=executable_graph,
            builder=engine_builder,
            execution_holder=ctx_holder,
        )
