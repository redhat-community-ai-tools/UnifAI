"""Monitoring phase — interpret responses and manage work item lifecycle."""

from typing import Any, List

from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.tools.builtin.workplan.mark_status import MarkWorkItemStatusTool
from mas.elements.tools.builtin.delegation.delegate_task import DelegateTaskTool
from mas.elements.tools.builtin.topology.list_adjacent import ListAdjacentNodesTool
from mas.elements.tools.builtin.time import GetCurrentTimeTool

from .constants import OrchestratorPhase
from .base import Phase, PhaseDependencies, PlanSnapshotMode, PromptContext
from .validators import MonitoringValidator


class MonitoringPhase(Phase):
    name = OrchestratorPhase.MONITORING
    needs_node_context = True
    snapshot_mode = PlanSnapshotMode.ATTENTION

    def create_tools(self, deps: PhaseDependencies) -> List[BaseTool]:
        return [
            MarkWorkItemStatusTool(
                get_thread_id=deps.get_thread_id,
                get_owner_uid=deps.get_owner_uid,
                get_workload_service=deps.get_workload_service,
            ),
            DelegateTaskTool(
                send_task=deps.send_task,
                get_owner_uid=deps.get_owner_uid,
                get_current_thread=deps.get_current_thread,
                get_thread_service=deps.get_thread_service,
                get_workspace_service=deps.get_workspace_service,
                check_adjacency=deps.check_adjacency,
            ),
            ListAdjacentNodesTool(get_adjacent_nodes=deps.get_adjacent_nodes),
            GetCurrentTimeTool(),
        ]

    def get_guidance(self) -> str:
        return (
            "MONITORING: Review responses and decide next actions.\n\n"
            "For each item with a new response, pick ONE action:\n"
            "- Accept: MarkWorkItemStatusTool(item_id, 'done')\n"
            "- Follow up: DelegateTaskTool(agent, question, work_item_id) — agent sees history\n"
            "- Fail: MarkWorkItemStatusTool(item_id, 'failed')\n\n"
            "DECISION RULE: Mark DONE if the response answers the work item's requirement.\n"
            "Only follow up when critical information is clearly missing, the answer is\n"
            "ambiguous, or the response contains errors that need clarification.\n"
            "Do NOT re-ask for information already provided in the response.\n\n"
            "NEVER call DelegateTaskTool AND MarkWorkItemStatusTool on the same item.\n"
            "If you follow up, the item stays IN_PROGRESS — wait for the next response.\n"
            "You are a COORDINATOR — do not execute work yourself."
        )

    def create_validator(self):
        return MonitoringValidator()

    def decide_next(self, status: Any) -> str:
        if status.is_complete:
            return OrchestratorPhase.SYNTHESIS
        if status.has_responses:
            return OrchestratorPhase.MONITORING

        if (status.blocked_items > 0
                and status.pending_items == 0
                and not status.has_local_ready
                and not status.has_remote_waiting):
            return OrchestratorPhase.SYNTHESIS

        if status.has_local_ready:
            return OrchestratorPhase.EXECUTION
        if status.pending_items > 0:
            return OrchestratorPhase.PLANNING

        return OrchestratorPhase.MONITORING

    def on_limit_exceeded(self, status: Any) -> str:
        if status and status.has_remote_waiting:
            return OrchestratorPhase.MONITORING
        return OrchestratorPhase.SYNTHESIS

    def build_focused_prompt(self, ctx: PromptContext) -> str:
        from ..context.models import CycleTriggerReason

        reason = ctx.trigger_reason
        plan = ctx.plan

        if not plan:
            return "Review work plan and update item statuses."

        needs_attention = []
        waiting = []
        for item in plan.items.values():
            if item.result and item.result.delegations:
                for ex in item.result.delegations:
                    if ex.needs_attention:
                        needs_attention.append(item)
                        break
                    elif ex.is_pending:
                        waiting.append(item)
                        break

        if reason == CycleTriggerReason.RESPONSE_ARRIVED and len(ctx.changed_items) == 1:
            iid = ctx.changed_items[0]
            return (
                "**RESPONSE RECEIVED**\n\n"
                f"Agent responded to work item: `{iid}`\n\n"
                "**Decision:**\n"
                f"- **Acceptable?** -> `MarkWorkItemStatusTool('{iid}', 'done')`\n"
                f"- **Needs clarification?** -> `DelegateTaskTool(same agent, question, work_item_id)`\n"
                f"- **Failed/impossible?** -> `MarkWorkItemStatusTool('{iid}', 'failed')`\n\n"
                "Mark DONE if the response answers the requirement — do not re-ask\n"
                "for information already provided. Only follow up if critical info\n"
                "is missing or the answer is ambiguous."
            )

        if reason == CycleTriggerReason.RESPONSE_ARRIVED and len(ctx.changed_items) > 1:
            items_list = ", ".join([f"`{i}`" for i in ctx.changed_items[:4]])
            if len(ctx.changed_items) > 4:
                items_list += f" (+{len(ctx.changed_items) - 4} more)"
            return (
                f"**{len(ctx.changed_items)} RESPONSES RECEIVED**\n\n"
                f"Items: {items_list}\n\n"
                "**For each response:**\n"
                "1. Does it answer the work item's requirement? -> Mark DONE\n"
                "2. Critical info missing or answer ambiguous? -> Follow up\n"
                "3. Error or impossible? -> Mark FAILED\n\n"
                "Do NOT re-ask for information already provided in a response."
            )

        if ctx.phase_changed and reason != CycleTriggerReason.RESPONSE_ARRIVED:
            if needs_attention:
                return (
                    f"**REVIEW {len(needs_attention)} RESPONSE(S)**\n\n"
                    "Local execution complete. Now review responses from delegated work."
                )
            if waiting:
                return (
                    f"**WAITING FOR {len(waiting)} RESPONSE(S)**\n\n"
                    "All actionable work complete. Waiting for agents to respond.\n"
                    "Finish to pause (will resume when responses arrive)."
                )
            return "**NO PENDING RESPONSES**\n\nAll work items processed.\nFinish to proceed to SYNTHESIS."

        if not ctx.phase_changed and needs_attention:
            return (
                f"**CONTINUE MONITORING** ({len(needs_attention)} items need attention)\n\n"
                "Continue processing remaining responses."
            )

        if not ctx.phase_changed and not needs_attention:
            if waiting:
                return (
                    f"**WAITING FOR RESPONSES** ({len(waiting)} items)\n\n"
                    "All available responses processed.\n"
                    "Finish to pause until more responses arrive."
                )
            return "**MONITORING COMPLETE**\n\nAll work items reviewed and processed.\nFinish to proceed to SYNTHESIS."

        return "Review responses and update work item statuses."
