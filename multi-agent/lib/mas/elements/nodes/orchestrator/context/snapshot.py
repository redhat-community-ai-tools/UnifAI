"""
Iteration snapshot for caching workspace state within a single LLM iteration.

Prevents redundant loads of plan, status, and adjacent nodes that otherwise
happen 3+ times per think() call across get_dynamic_context_messages,
build_focused_prompt, _build_validation_context, and get_phase_context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IterationSnapshot:
    """
    Immutable snapshot of workspace state for a single LLM iteration.

    Created once at the start of each think() cycle, used by all methods
    that need plan/status/adjacent_nodes, then discarded.

    Frozen dataclass ensures no accidental mutation during the iteration.
    """
    plan: Any = None
    status: Any = None
    adjacent_nodes: Optional[Dict] = field(default_factory=dict)
    workspace_service: Any = None
    thread_id: str = ""
    node_uid: str = ""

    @classmethod
    def capture(
        cls,
        get_workload_service: Callable[[], Any],
        get_adjacent_nodes: Callable[[], Dict],
        thread_id: str,
        node_uid: str,
    ) -> IterationSnapshot:
        """
        Capture current workspace state into an immutable snapshot.

        Loads plan, status, and adjacent nodes exactly once.

        Args:
            get_workload_service: Factory for workspace service
            get_adjacent_nodes: Factory for adjacent nodes
            thread_id: Current thread ID
            node_uid: Current node UID

        Returns:
            Frozen IterationSnapshot with all data loaded
        """
        try:
            workspace_service = get_workload_service().get_workspace_service()
            plan = workspace_service.load_work_plan(thread_id, node_uid)
            status = workspace_service.get_work_plan_status(thread_id, node_uid)
            adjacent = get_adjacent_nodes()
        except Exception as e:
            logger.warning("Failed to capture iteration snapshot: %s", e)
            workspace_service = None
            plan = None
            status = None
            adjacent = {}

        return cls(
            plan=plan,
            status=status,
            adjacent_nodes=adjacent or {},
            workspace_service=workspace_service,
            thread_id=thread_id,
            node_uid=node_uid,
        )

    @property
    def has_plan(self) -> bool:
        return self.plan is not None and bool(getattr(self.plan, 'items', None))

    @property
    def total_items(self) -> int:
        if self.status:
            return getattr(self.status, 'total_items', 0)
        return 0
