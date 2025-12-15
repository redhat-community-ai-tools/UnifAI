from session.session_registry import SessionRegistry
from graph.rt_graph_plan import RTGraphPlan
from engine.builder.base_graph_builder import BaseGraphBuilder
from engine.executor.interfaces import GraphExecutor
from core.run_context import RunContext
from core.enums import ResourceCategory
from core.channels import SessionChannel
from graph.state.graph_state import GraphState
from typing import Optional
from .status import SessionStatus
from .models import SessionMeta


class WorkflowSession:
    """
    Holds all runtime state for a single user-run of a blueprint:
      - session_registry: dynamic component instances (LLMs, agents, etc.)
      - blueprint: the validated BlueprintSpec
      - graph_plan: the abstract plan (list of Steps)
      - executable_graph: compiled graph ready to invoke()
      - logger: records every event
      - builder: the graph builder used (for live recompilation)
      - metadata: arbitrary dict (run_id, timestamps, user_id, etc.)
    """

    def __init__(
            self,
            session_registry: SessionRegistry,
            blueprint_id: str,
            rt_graph_plan: RTGraphPlan,
            executable_graph: GraphExecutor,
            builder: BaseGraphBuilder,
            run_context: RunContext,
            # logger: LoggerInterface,
            graph_state: GraphState,
            metadata: SessionMeta | None = None
    ) -> None:
        self.session_registry = session_registry
        self.blueprint_id = blueprint_id
        self.rt_graph_plan = rt_graph_plan
        self.executable_graph = executable_graph
        # self.logger = logger
        self.builder = builder
        self.run_context = run_context
        self.metadata = metadata
        self.graph_state = graph_state
        self.status: SessionStatus = SessionStatus.PENDING

    def recompile(self) -> None:
        """
        Rebuilds the executable_graph from the current graph_plan,
        using the stored builder.
        """
        self.executable_graph = self.builder.compile_from_plan(self.rt_graph_plan)

    def get_user_id(self) -> str:
        """
        Returns the user ID associated with this session.
        """
        return self.run_context.user_id

    def get_run_id(self) -> str:
        """
        Returns the user ID associated with this session.
        """
        return self.run_context.run_id

    def get_state(self) -> GraphState:
        """
        Returns the current state of the graph.
        """
        return self.graph_state

    def get_status(self) -> SessionStatus:
        """
        Returns the current status of the session.
        """
        return self.status.name

    def update_status(self, new: SessionStatus) -> None:
        self.status = new

    def prepare_for_streaming(self, channel: Optional[SessionChannel]) -> None:
        """
        Inject streaming channel into all nodes that support streaming.
        Called by SessionExecutor._pre_run when streaming=True.
        """
        for node in self.session_registry.all_of(ResourceCategory.NODE).values():
            if hasattr(node, 'set_streaming_channel'):
                node.set_streaming_channel(channel)
    
    def cleanup_streaming(self) -> None:
        """
        Clear streaming channel from all nodes.
        Called by SessionExecutor._post_run when streaming=True.
        """
        self.prepare_for_streaming(None)
