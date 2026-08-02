"""
Canonical lifecycle runner for scheduled session execution.

Owns the application-level ordering:

    provision → execute → record (always, via finally)

Adapters implement ScheduledRunOps for engine-specific mechanics;
execute() delegates to existing session lifecycle machinery.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from mas.scheduling.models import RunOutcome
from mas.session.domain.exceptions import (
    ScheduledSessionCancelledException,
    ScheduledSessionSetupError,
)
from mas.session.execution.ports import ScheduledExecutionParams


@runtime_checkable
class ScheduledRunOps(Protocol):
    """Engine-specific mechanics for scheduled session execution.

    Adapters translate native cancel signals into
    ScheduledSessionCancelledException; the runner still calls record().
    """

    async def provision(self) -> tuple[str, ScheduledExecutionParams]:
        """Prepare a session for execution.

        Create session, stage inputs, resolve blueprint, compile graph.
        Returns (session_id, params_ready_for_execution).
        """
        ...

    async def execute(self, params: ScheduledExecutionParams) -> RunOutcome:
        """Run the full session lifecycle via existing machinery.

        Returns COMPLETED or FAILED. Raises ScheduledSessionCancelledException
        on cancellation so the runner records CANCELLED.
        """
        ...

    async def record(
        self,
        session_id: str,
        outcome: RunOutcome,
        failure_reason: Optional[str],
    ) -> None:
        """Post-execution bookkeeping. Adapters must ensure this still runs under cancellation."""
        ...


class ScheduledSessionRunner:
    """Domain-layer orchestrator for scheduled execution.

    Ordering: provision → execute → record (always, via finally).
    """

    async def run(self, ops: ScheduledRunOps) -> str:
        """Execute the full scheduled session lifecycle.

        Returns session_id. Re-raises ScheduledSessionCancelledException
        after recording; raises ScheduledSessionSetupError if provision fails.
        """
        session_id: Optional[str] = None
        outcome = RunOutcome.FAILED
        failure_reason: Optional[str] = None

        try:
            session_id, params = await ops.provision()
            outcome = await ops.execute(params)
        except ScheduledSessionCancelledException:
            outcome = RunOutcome.CANCELLED
            failure_reason = "WorkflowCancelled"
            raise
        except Exception as e:
            failure_reason = f"{type(e).__name__}: {e}"
        finally:
            if session_id is not None:
                await ops.record(session_id, outcome, failure_reason)

        if session_id is None:
            raise ScheduledSessionSetupError(failure_reason)

        return session_id
