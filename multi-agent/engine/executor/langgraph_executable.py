from typing import Any
from engine.executor.interfaces import GraphExecutor


class LangGraphExecutor(GraphExecutor):
    """
    Wraps a LangGraph compiled graph (which has .invoke),
    exposing it as a GraphExecutor with .run().
    """

    def __init__(self, compiled_graph: Any) -> None:
        self._compiled = compiled_graph

    def run(self, initial_state):
        # delegate to LangGraph's invoke API
        return self._compiled.invoke(initial_state, config={"recursion_limit": 100})

    def stream(self, initial_state, *args, **kwargs):
        """
        stream the graph's output to the given stream.
        """
        stream_mode = kwargs.get("stream_mode", None)
        if stream_mode:
            for chunk in self._compiled.stream(
                    initial_state,
                    stream_mode=stream_mode,
                    config={"recursion_limit": 100}
            ):
                yield chunk

    def get_state(self):
        """
        Get the current state of the graph.
        """
        return self._compiled.get_state(None)
