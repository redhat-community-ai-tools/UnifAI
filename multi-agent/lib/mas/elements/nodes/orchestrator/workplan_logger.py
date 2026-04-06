"""
Work plan debug logging utility.

Extracted from OrchestratorPhaseProvider to keep the provider focused
on coordination. Called after phase transitions to aid debugging.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class WorkPlanLogger:
    """Formats work plan state for debug logging. Standalone utility."""

    @staticmethod
    def log_after_transition(
        workspace_service: Any,
        thread_id: str,
        owner_uid: str,
        phase: str,
    ) -> None:
        """Log work plan status after a phase transition."""
        try:
            from mas.elements.nodes.common.workload import WorkItemStatus, WorkItemKind

            plan = workspace_service.load_work_plan(thread_id, owner_uid)
            if not plan or not plan.items:
                return

            status = workspace_service.get_work_plan_status(thread_id, owner_uid)

            status_parts = []
            if status.pending_items > 0:
                status_parts.append(f"{status.pending_items} Pending")
            if status.in_progress_items > 0:
                status_parts.append(f"{status.in_progress_items} In Progress")
            if status.done_items > 0:
                status_parts.append(f"{status.done_items} Done")
            if status.failed_items > 0:
                status_parts.append(f"{status.failed_items} Failed")

            extras = []
            if status.blocked_items > 0:
                extras.append(f"{status.blocked_items} Blocked")
            if status.waiting_items > 0:
                extras.append(f"{status.waiting_items} Waiting")

            extra_str = f" [{', '.join(extras)}]" if extras else ""

            lines = [
                "=" * 80,
                f"WORK PLAN after {phase.upper()} ({status.total_items} items)",
                "=" * 80,
                f"Status: {' | '.join(status_parts)}{extra_str}",
            ]

            for item_status in [
                WorkItemStatus.PENDING,
                WorkItemStatus.IN_PROGRESS,
                WorkItemStatus.DONE,
                WorkItemStatus.FAILED,
            ]:
                items = plan.get_items_by_status(item_status)
                if not items:
                    continue

                for item in items:
                    label = {
                        WorkItemStatus.PENDING: "[PENDING]",
                        WorkItemStatus.IN_PROGRESS: "[IN_PROGRESS]",
                        WorkItemStatus.DONE: "[DONE]",
                        WorkItemStatus.FAILED: "[FAILED]",
                    }.get(item_status, "")

                    kind = (
                        "local"
                        if item.kind == WorkItemKind.LOCAL
                        else f"->{item.assigned_uid}"
                    )
                    item_line = f"{label} {item.title[:50]}"
                    if len(item.title) > 50:
                        item_line += "..."
                    item_line += f" ({kind})"

                    if item.dependencies:
                        completed_deps = plan.get_completed_item_ids()
                        dep_status = []
                        for dep_id in item.dependencies:
                            dep_item = plan.items.get(dep_id)
                            if dep_item:
                                dep_title = (
                                    dep_item.title[:20] + "..."
                                    if len(dep_item.title) > 20
                                    else dep_item.title
                                )
                                if dep_id in completed_deps:
                                    dep_status.append(f"done:{dep_title}")
                                else:
                                    dep_status.append(f"pending:{dep_title}")
                            else:
                                dep_status.append(f"?{dep_id}")
                        item_line += f" [depends on: {', '.join(dep_status)}]"

                    if item.result and item.result.delegations:
                        delegation_count = len(item.result.delegations)
                        processed_count = sum(
                            1 for d in item.result.delegations if d.processed
                        )
                        pending_count = sum(
                            1 for d in item.result.delegations if d.is_pending
                        )
                        unprocessed_count = sum(
                            1 for d in item.result.delegations if d.needs_attention
                        )

                        if delegation_count == 1:
                            latest = item.result.delegations[0]
                            if latest.is_pending:
                                item_line += (
                                    f"\n      Waiting for response from"
                                    f" {latest.delegated_to}"
                                )
                            elif latest.needs_attention:
                                resp = (
                                    latest.response_content[:100].replace("\n", " ")
                                    if latest.response_content
                                    else "No content"
                                )
                                item_line += f"\n      NEW: {resp}..."
                            else:
                                resp = (
                                    latest.response_content[:100].replace("\n", " ")
                                    if latest.response_content
                                    else "No content"
                                )
                                item_line += f"\n      Processed: {resp}..."
                        else:
                            item_line += (
                                f"\n      {delegation_count} turns"
                                f" ({processed_count} processed,"
                                f" {unprocessed_count} pending,"
                                f" {pending_count} waiting)"
                            )
                            latest = item.result.delegations[-1]
                            if latest.is_pending:
                                item_line += (
                                    f"\n      Latest: Waiting for"
                                    f" {latest.delegated_to}"
                                )
                            elif latest.needs_attention:
                                resp = (
                                    latest.response_content[:100].replace("\n", " ")
                                    if latest.response_content
                                    else "No content"
                                )
                                item_line += f"\n      Latest: {resp}..."
                            else:
                                resp = (
                                    latest.response_content[:100].replace("\n", " ")
                                    if latest.response_content
                                    else "No content"
                                )
                                item_line += f"\n      Latest: {resp}..."

                    lines.append(f"   {item_line}")

            lines.append("=" * 80)
            logger.debug("\n".join(lines))
        except Exception:
            pass
