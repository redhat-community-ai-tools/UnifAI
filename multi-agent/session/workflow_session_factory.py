from catalog.element_registry import ElementRegistry
from session.element_builder import SessionElementBuilder
from engine.builder.graph_builder_factory import GraphBuilderFactory
from session.workflow_session import WorkflowSession
from graph.state.graph_state import GraphState
from graph.plan_builder import PlanBuilder
from graph.rt_graph_plan import RTGraphPlan
from core.run_context import RunContext
from core.context import set_current_context
from blueprints.models.blueprint import BlueprintSpec
from .models import SessionMeta


class WorkflowSessionFactory:
    """
    Orchestrates the creation of a WorkflowSession end-to-end:
      0) Build RunContext & set it
      1) Load & validate blueprint
      2) Instantiate atomic elements
      3) Build GraphPlan
      4) Compile to ExecutableGraph
      5) Create logger, saver, modifier
      6) Wire everything into WorkflowSession
      7) Persist initial snapshot
    """

    def __init__(
            self,
            element_registry: ElementRegistry,
            engine_name: str,
            # logger_factory: Callable[[RunContext], LoggerInterface],
    ):
        self._elements = element_registry
        self._session_builder = SessionElementBuilder(element_registry)
        self._engine_name = engine_name
        # self._logger_factory = logger_factory

    def create(
            self,
            *,
            user_id: str,
            blueprint_spec: BlueprintSpec,
            blueprint_id: str,
            metadata: SessionMeta = None,
            graph_state: GraphState = GraphState(),
    ) -> WorkflowSession:
        # Ensure metadata is a SessionMeta instance
        session_meta = metadata if metadata is not None else SessionMeta()
        
        # 0) Build and propagate RunContext ———
        # RunContext.metadata expects a dict, so convert SessionMeta to dict
        ctx = RunContext(
            user_id=user_id,
            engine_name=self._engine_name,
            metadata=session_meta.to_dict()
        )
        set_current_context(ctx)

        # 1. Build logical plan
        plan_builder = PlanBuilder(self._elements)
        logical_plan = plan_builder.build(blueprint_spec)

        # Optional: visualize
        logical_plan.pretty_print()

        # 2. Instantiate session‐wide components ———
        session_registry = self._session_builder.build(blueprint_spec)

        # 3. Compose abstract plan ———
        rt_graph_plan = RTGraphPlan(logical_plan, session_registry)

        # 4. Compile to executable graph ———
        _engine_builder = GraphBuilderFactory(GraphState).create(self._engine_name)
        executable_graph = _engine_builder.compile_from_plan(rt_graph_plan)

        # 5. Wire into WorkflowSession ———
        session = WorkflowSession(
            session_registry=session_registry,
            blueprint_id=blueprint_id,
            rt_graph_plan=rt_graph_plan,
            executable_graph=executable_graph,
            builder=_engine_builder,
            run_context=ctx,
            metadata=session_meta,
            graph_state=graph_state,
        )

        return session
