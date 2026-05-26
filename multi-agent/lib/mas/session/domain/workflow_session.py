from mas.session.domain.session_registry import SessionRegistry
from mas.graph.rt_graph_plan import RTGraphPlan
from mas.engine.domain.base_builder import BaseGraphBuilder
from mas.engine.domain.base_executor import BaseGraphExecutor
from mas.graph.state.graph_state import GraphState
from mas.session.domain.status import SessionStatus
from mas.session.domain.session_record import SessionRecord
from mas.core.execution_context import ExecutionContextHolder


class WorkflowSession:
    """
    Full runtime session: SessionRecord (persistable) + execution artifacts.

    Holds a SessionRecord by composition — lifecycle methods mutate the
    record directly, and the session sees changes instantly (no sync needed).

    Runtime-only fields (not persisted):
      - session_registry: dynamic component instances (LLMs, agents, etc.)
      - rt_graph_plan: the compiled plan with bound callables
      - executable_graph: compiled graph ready to invoke()
      - builder: the graph builder used (for live recompilation)
    """

    def __init__(
            self,
            record: SessionRecord,
            session_registry: SessionRegistry,
            rt_graph_plan: RTGraphPlan,
            executable_graph: BaseGraphExecutor,
            builder: BaseGraphBuilder,
            execution_holder: ExecutionContextHolder = None,
    ) -> None:
        self.record = record
        self.session_registry = session_registry
        self.rt_graph_plan = rt_graph_plan
        self.executable_graph = executable_graph
        self.builder = builder
        self.execution_holder = execution_holder or ExecutionContextHolder()

    # ---- Delegated properties (backward-compatible access) ----

    @property
    def blueprint_id(self) -> str:
        return self.record.blueprint_id

    @property
    def run_context(self):
        return self.record.run_context

    @run_context.setter
    def run_context(self, value):
        self.record.run_context = value

    @property
    def metadata(self):
        return self.record.metadata

    @metadata.setter
    def metadata(self, value):
        self.record.metadata = value

    @property
    def graph_state(self) -> GraphState:
        return self.record.graph_state

    @graph_state.setter
    def graph_state(self, value):
        self.record.graph_state = value

    @property
    def status(self) -> SessionStatus:
        return self.record.status

    @status.setter
    def status(self, value: SessionStatus):
        self.record.status = value

    # ---- Methods ----

    def recompile(self) -> None:
        self.executable_graph = self.builder.compile_from_plan(self.rt_graph_plan)

    def get_run_id(self) -> str:
        return self.record.run_id

    def get_state(self) -> GraphState:
        return self.record.graph_state

    def get_status(self) -> str:
        return self.record.status.name

    def update_status(self, new: SessionStatus) -> None:
        self.record.status = new

    def to_record(self) -> SessionRecord:
        return self.record
