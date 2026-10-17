from typing import Any, Optional

from mas.engine.domain.base_executor import BaseGraphExecutor
from mas.engine.domain.types import DEFAULT_RECURSION_LIMIT
from mas.core.execution_context import ExecutionContext
from mas.graph.state.graph_state import GraphState


class LangGraphExecutor(BaseGraphExecutor):
    """
    Wraps a LangGraph compiled graph (which has .invoke),
    exposing it as a BaseGraphExecutor with .run().
    """

    def __init__(
        self,
        compiled_graph: Any,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    ) -> None:
        self._compiled = compiled_graph
        self._recursion_limit = recursion_limit

    def run(
        self,
        initial_state: GraphState,
        *,
        session_id: str = "",
        execution_context: Optional[ExecutionContext] = None,
    ) -> GraphState:
        result = self._compiled.invoke(
            initial_state,
            config={"recursion_limit": self._recursion_limit},
        )
        return GraphState.model_validate(result) if isinstance(result, dict) else result

    def get_state(self) -> Any:
        return self._compiled.get_state(None)
