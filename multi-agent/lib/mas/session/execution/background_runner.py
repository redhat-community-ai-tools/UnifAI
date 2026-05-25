"""
Canonical lifecycle runner for background session execution.

Defines the application-level ordering rule that ALL background engines
must follow:

    begin  →  execute_graph  →  complete
                                 (or fail on error)
                                 (or cancel on SessionCancelledException)

The ordering lives HERE, in the application layer — not inside any
infrastructure adapter.  Each adapter (Temporal, Celery, RQ, …)
implements BackgroundSessionOps to supply the engine-specific mechanics,
but the sequence is always driven by BackgroundSessionRunner.

Inputs are already staged into the SessionRecord by SessionInputProjector
before any background worker starts.  begin() only transitions the
session from QUEUED → RUNNING.
"""
from typing import Protocol, runtime_checkable

from mas.graph.state.graph_state import GraphState
from mas.session.domain.exceptions import SessionCancelledException


@runtime_checkable
class BackgroundSessionOps(Protocol):
    """
    Engine-specific mechanics for background session execution.

    Each background engine implements these five async operations.
    The runner calls them in the canonical order.

    Temporal implements them as workflow activities / child workflows.
    Celery implements them as direct service calls inside a task.

    Each engine is responsible for translating its native cancel signal
    (e.g. asyncio.CancelledError, SoftTimeLimitExceeded) into
    SessionCancelledException inside its ops methods. The runner catches
    it and calls cancel().
    """

    async def begin(self) -> GraphState:
        """Mark RUNNING, bind context, persist. Return staged GraphState."""
        ...

    async def execute_graph(self, seeded_state: GraphState) -> GraphState:
        """Run the graph and return the final GraphState."""
        ...

    async def complete(self, final_state: GraphState) -> None:
        """Attach final state, mark COMPLETED, persist."""
        ...

    async def fail(self, error: Exception) -> None:
        """Mark FAILED, persist."""
        ...

    async def cancel(self) -> None:
        """Mark CANCELLED, close channels, persist."""
        ...


class BackgroundSessionRunner:
    """
    Runs the full background session lifecycle.

    This is the single source of truth for the ordering rule.
    Infrastructure adapters supply BackgroundSessionOps; this class
    ensures they are called in the correct sequence.

    Handles all terminal transitions:
      - COMPLETED via complete()
      - FAILED via fail()
      - CANCELLED via cancel()

    Mirrors ForegroundSessionRunner for the background path.
    """

    async def run(self, ops: BackgroundSessionOps) -> GraphState:
        """
        Execute the full background session lifecycle.

        Args:
            ops: Engine-specific operations (Temporal activities,
                 Celery service calls, etc.)

        Returns:
            The final GraphState.
        """
        try:
            seeded_state = await ops.begin()
            final_state = await ops.execute_graph(seeded_state)
            await ops.complete(final_state)
            return final_state
        except SessionCancelledException:
            await ops.cancel()
            raise
        except Exception as e:
            await ops.fail(e)
            raise
