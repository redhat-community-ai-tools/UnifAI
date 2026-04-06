"""
Context formatter for orchestrator LLM interactions.

SRP: Formats workspace/work-plan data into ChatMessage objects.
Uses Phase metadata (snapshot_mode, needs_node_context) instead of
hard-coded phase-name checks.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.nodes.common.workload import WorkItemStatus, WorkItemKind
from .base import Phase, PlanSnapshotMode

logger = logging.getLogger(__name__)


class ContextFormatter:
    """
    Formats workspace state into ChatMessage objects for LLM consumption.

    Stateless — all data is passed via method arguments or the Phase object.
    """

    def __init__(
        self,
        thread_id: str,
        node_uid: str,
        get_adjacent_nodes: Callable[[], Dict],
    ):
        self._thread_id = thread_id
        self._node_uid = node_uid
        self._get_adjacent_nodes = get_adjacent_nodes

    # ------------------------------------------------------------------
    # Public API (accepts Phase object instead of phase_name string)
    # ------------------------------------------------------------------

    def build_dynamic_context_messages(
        self,
        phase: Phase,
        plan: Any,
        workspace_service: Any,
        orch_context: Any,
        phase_changed: bool = True,
    ) -> List[ChatMessage]:
        """
        Build the dynamic context messages sent before each LLM call.

        Tiered context:
        - phase_changed=True  → FULL context
        - phase_changed=False → BRIEF context (status + actionable items)

        Messages are tagged with additional_kwargs for tag-based filtering
        in the strategy (no more string-prefix matching).
        """
        messages: List[ChatMessage] = []

        try:
            mode = phase.snapshot_mode

            if phase_changed:
                content = self._build_full_context(plan, workspace_service, orch_context, mode)
            else:
                content = self._build_brief_context(plan, workspace_service, mode)

            if logger.isEnabledFor(logging.DEBUG):
                tier = "FULL" if phase_changed else "BRIEF"
                logger.debug(
                    "DYNAMIC CONTEXT [%s] (%s): %s",
                    phase.name.upper() if hasattr(phase, 'name') else "?",
                    tier,
                    content[:500],
                )

            messages.append(ChatMessage(
                role=Role.USER,
                content=content,
                additional_kwargs={"dynamic_context": True},
            ))

        except Exception as e:
            logger.error("Error building dynamic context: %s", e)

        return messages

    def build_static_context(self, phase: Phase) -> List[ChatMessage]:
        """
        Build phase-specific static context (e.g. adjacent-node descriptions).

        Driven by phase.needs_node_context — no hardcoded phase-name set.
        """
        if not phase.needs_node_context:
            return []

        nodes_text = self._format_adjacent_nodes()
        if not nodes_text:
            return []

        return [ChatMessage(role=Role.SYSTEM, content=nodes_text)]

    # ------------------------------------------------------------------
    # Internal: full context
    # ------------------------------------------------------------------

    def _build_full_context(
        self, plan: Any, workspace_service: Any, orch_context: Any,
        mode: PlanSnapshotMode,
    ) -> str:
        plan_snapshot = (
            self._build_plan_snapshot(plan, workspace_service, mode)
            if plan else "No work plan exists yet."
        )
        if orch_context:
            return orch_context.format_context(plan_snapshot)
        return f"Current Work Plan:\n{plan_snapshot}"

    # ------------------------------------------------------------------
    # Internal: brief context (continuation)
    # ------------------------------------------------------------------

    def _build_brief_context(
        self, plan: Any, workspace_service: Any, mode: PlanSnapshotMode,
    ) -> str:
        status = workspace_service.get_work_plan_status(self._thread_id, self._node_uid)

        lines = [
            f"[CONTINUATION] Work Plan Status: "
            f"pending={status.pending_items}, in_progress={status.in_progress_items}, "
            f"done={status.done_items}, failed={status.failed_items}, "
            f"complete={status.is_complete}",
        ]

        if not plan or not hasattr(plan, 'items') or not plan.items:
            return "\n".join(lines)

        # Items needing attention (all modes)
        attention_items = []
        for item in plan.items.values():
            if item.result and item.result.delegations:
                for ex in item.result.delegations:
                    if ex.needs_attention:
                        resp = ex.response_content or "No content"
                        attention_items.append(
                            f"  - {item.id}: NEW RESPONSE from {ex.delegated_to}: {resp}"
                        )
                        break

        if attention_items:
            lines.append(f"\nItems needing attention ({len(attention_items)}):")
            lines.extend(attention_items)

        # Ready items for LOCAL_ONLY mode (execution)
        if mode == PlanSnapshotMode.LOCAL_ONLY:
            ready = plan.get_ready_items()
            if ready:
                ready_items = [f"  - {item.id}: {item.title}" for item in ready[:5]]
                lines.append(f"\nReady items ({len(ready)}):")
                lines.extend(ready_items)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal: plan snapshot (mode-driven filtering)
    # ------------------------------------------------------------------

    def _build_plan_snapshot(
        self,
        plan: Any,
        workspace_service: Any,
        mode: PlanSnapshotMode,
    ) -> str:
        """
        Build a mode-filtered work-plan snapshot.

        FULL:       show everything (PLANNING, SYNTHESIS)
        LOCAL_ONLY: only LOCAL items, skip REMOTE response content (EXECUTION)
        ATTENTION:  full responses for quality judgment on items w/ responses (MONITORING)
        """
        status = workspace_service.get_work_plan_status(self._thread_id, self._node_uid)

        lines = [
            f"Work Plan: {status.total_items} items | "
            f"pending={status.pending_items} in_progress={status.in_progress_items} "
            f"done={status.done_items} failed={status.failed_items} | "
            f"complete={status.is_complete}",
        ]

        if not plan:
            return "\n".join(lines)

        lines.append(f"Summary: {plan.summary}")

        all_statuses = [
            WorkItemStatus.PENDING, WorkItemStatus.IN_PROGRESS,
            WorkItemStatus.DONE, WorkItemStatus.FAILED,
        ]

        for item_status in all_statuses:
            items = plan.get_items_by_status(item_status)
            if not items:
                continue

            # LOCAL_ONLY: only LOCAL items that are actionable
            if mode == PlanSnapshotMode.LOCAL_ONLY:
                if item_status == WorkItemStatus.FAILED:
                    continue
                items = [i for i in items if i.kind == WorkItemKind.LOCAL]
                if not items:
                    continue

            lines.append(f"\n{item_status.value.upper()} ({len(items)}):")
            for item in items:
                info = f"  - {item.title} (ID: {item.id})"
                if item.dependencies:
                    info += f"\n    Dependencies: {item.dependencies}"
                if item.kind == WorkItemKind.REMOTE:
                    info += f" -> {item.assigned_uid}"
                else:
                    info += " [LOCAL]"
                if item.retry_count > 0:
                    info += f" [retries: {item.retry_count}/{item.max_retries}]"
                lines.append(info)

                # FAILED items: always show error reason
                if item_status == WorkItemStatus.FAILED:
                    if item.error:
                        lines.append(f"    Error: {item.error}")
                    continue

                # LOCAL_ONLY: local execution outcome
                if mode == PlanSnapshotMode.LOCAL_ONLY:
                    if item.result and item.result.local_execution:
                        outcome = item.result.local_execution.outcome or ""
                        if outcome:
                            lines.append(f"    Execution: {outcome}")
                    continue

                # ATTENTION: full response for quality judgment
                if mode == PlanSnapshotMode.ATTENTION:
                    if item.result and item.result.delegations:
                        latest = item.result.delegations[-1]
                        if latest.needs_attention:
                            resp = latest.response_content or "No content"
                            lines.append(f"    NEW RESPONSE from {latest.delegated_to}: {resp}")
                        elif latest.is_pending:
                            lines.append(f"    Waiting for {latest.delegated_to}")
                        else:
                            lines.append(
                                f"    Processed ({len(item.result.delegations)} exchanges)"
                            )
                    continue

                # FULL: show everything
                if item.result and item.result.delegations:
                    summary = item.result.conversation_summary(
                        truncate=False, max_chars=250,
                    )
                    for line in summary.split("\n"):
                        lines.append(f"    {line}")
                elif item.result and item.result.local_execution:
                    outcome = item.result.local_execution.outcome or ""
                    if outcome:
                        lines.append(f"    Execution: {outcome}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal: adjacent nodes
    # ------------------------------------------------------------------

    def _format_adjacent_nodes(self) -> Optional[str]:
        try:
            nodes = self._get_adjacent_nodes()
            if not nodes:
                return None
            lines = ["## Available Agents for Delegation\n"]
            for uid, card in nodes.items():
                lines.append(str(card))
                lines.append("")
            return "\n".join(lines)
        except Exception:
            return None
