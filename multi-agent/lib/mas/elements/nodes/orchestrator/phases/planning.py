"""Planning phase — create/update work plan and delegate REMOTE items."""

from typing import Any, List

from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.tools.builtin.workplan.create_or_update import CreateOrUpdateWorkPlanTool
from mas.elements.tools.builtin.delegation.delegate_task import DelegateTaskTool
from mas.elements.tools.builtin.topology.list_adjacent import ListAdjacentNodesTool
from mas.elements.tools.builtin.time import GetCurrentTimeTool

from .constants import OrchestratorPhase
from .base import Phase, PhaseDependencies, PlanSnapshotMode, PromptContext
from .validators import PlanningValidator


class PlanningPhase(Phase):
    name = OrchestratorPhase.PLANNING
    needs_node_context = True
    snapshot_mode = PlanSnapshotMode.FULL

    def create_tools(self, deps: PhaseDependencies) -> List[BaseTool]:
        return [
            CreateOrUpdateWorkPlanTool(
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
            "PLANNING: Create/update work plan and delegate REMOTE items.\n\n"
            "- CreateOrUpdateWorkPlanTool: define items (LOCAL/REMOTE), dependencies, snake_case IDs\n"
            "- DelegateTaskTool: delegate each REMOTE item immediately after plan creation\n"
            "- For follow-ups: prefer re-delegating to existing items (same work_item_id)\n"
            "  over creating new ones — agent sees full conversation history\n"
            "- Agents work in parallel — leverage this for broad information needs\n"
            "- NO synthesis/compile work items — SYNTHESIS phase handles final answers\n"
            "- DO NOT execute work (EXECUTION phase handles that)\n"
            "- Undelegated REMOTE items will keep you in this phase"
        )

    def create_validator(self):
        return PlanningValidator()

    def decide_next(self, status: Any) -> str:
        if not status.total_items or status.has_remote_ready:
            return OrchestratorPhase.PLANNING
        if status.has_local_ready:
            return OrchestratorPhase.EXECUTION
        if status.has_responses or status.has_remote_waiting:
            return OrchestratorPhase.MONITORING
        if status.is_complete:
            return OrchestratorPhase.SYNTHESIS
        return OrchestratorPhase.PLANNING

    def on_limit_exceeded(self, status: Any) -> str:
        if status and status.has_local_ready:
            return OrchestratorPhase.EXECUTION
        if status and (status.has_remote_waiting or status.in_progress_items > 0):
            return OrchestratorPhase.MONITORING
        return OrchestratorPhase.SYNTHESIS

    def build_focused_prompt(self, ctx: PromptContext) -> str:
        from ..context.models import CycleTriggerReason

        reason = ctx.trigger_reason
        status = ctx.status
        user_request = ctx.user_request or "the request"

        if reason == CycleTriggerReason.NEW_REQUEST and status.total_items == 0:
            return (
                "**NEW REQUEST - CREATE WORK PLAN AND DELEGATE**\n\n"
                f"User asked: \"{user_request}\"\n\n"
                "**Your task:** Create a work plan AND delegate REMOTE items in one step.\n\n"
                "**Steps:**\n"
                "1. Analyze the request to understand information needs\n"
                "2. Review 'Available Agents' section above to see agent capabilities\n"
                "3. For each work item, determine:\n"
                "   - Type: LOCAL (you execute) or REMOTE (delegate to agent)\n"
                "   - Dependencies: Which items must complete first\n"
                "   - Assignment: For REMOTE items, which agent based on their capabilities\n"
                "4. Use `CreateOrUpdateWorkPlanTool` with all items\n"
                "5. **IMMEDIATELY** delegate REMOTE items using `DelegateTaskTool`\n"
                "   - DelegateTaskTool(dst_uid, content, work_item_id) handles assignment automatically\n"
                "   - Delegate all independent REMOTE items in this same iteration\n\n"
                "**COMPREHENSIVE COVERAGE:** When information completeness is important,\n"
                "create work items for multiple agents. Information is often distributed\n"
                "across multiple data sources.\n\n"
                "**DO NOT** create a 'synthesize' or 'compile results' work item — "
                "the SYNTHESIS phase handles the final answer automatically."
            )

        if reason == CycleTriggerReason.NEW_REQUEST and status.is_complete:
            return (
                "**FOLLOW-UP REQUEST**\n\n"
                f"User's follow-up: \"{user_request}\"\n\n"
                f"**Context:** Existing plan has {status.total_items} items (all complete).\n\n"
                "**DECIDE your approach** by reviewing the existing results above:\n\n"
                "**Option A — RE-DELEGATE to existing agent (same work item):**\n"
                "  Use when the follow-up relates to work an agent already did.\n"
                "  `DelegateTaskTool(same_agent_uid, follow_up_question, work_item_id=existing_id)`\n"
                "  The agent sees the full previous conversation — no need to repeat context.\n"
                "  This reuses the thread and resets the item to IN_PROGRESS.\n\n"
                "**Option B — CREATE new work items:**\n"
                "  Use when the follow-up needs entirely new work (different topic or agent).\n"
                "  `CreateOrUpdateWorkPlanTool` + `DelegateTaskTool` for new REMOTE items.\n\n"
                "**Option C — ANSWER directly (no new work):**\n"
                "  Use when existing results already contain the answer.\n"
                "  Just finish — the SYNTHESIS phase will produce the answer.\n\n"
                "**Choose the most efficient path.** Re-delegation is preferred when\n"
                "the follow-up builds on previous work — it preserves context and is faster."
            )

        if reason == CycleTriggerReason.NEW_REQUEST and status.total_items > 0:
            active = status.in_progress_items + status.pending_items + status.waiting_items
            return (
                "**FOLLOW-UP REQUEST (PLAN IN PROGRESS)**\n\n"
                f"User's follow-up: \"{user_request}\"\n\n"
                f"**Context:** Plan has {status.total_items} items "
                f"({status.done_items} done, {active} active, {status.failed_items} failed).\n\n"
                "**DECIDE your approach** by reviewing the plan above:\n\n"
                "**Option A — RE-DELEGATE to an agent (continue conversation):**\n"
                "  Use when the follow-up relates to a DONE or IN_PROGRESS item.\n"
                "  `DelegateTaskTool(agent_uid, follow_up, work_item_id=existing_id)`\n"
                "  Agent sees full conversation history — just ask your question.\n\n"
                "**Option B — ADD new work items:**\n"
                "  Use when the follow-up requires entirely new work.\n"
                "  `CreateOrUpdateWorkPlanTool` + `DelegateTaskTool` for REMOTE items.\n\n"
                "**Option C — WAIT for active work:**\n"
                "  If active items will answer the follow-up, just finish.\n"
                "  Results will be processed when responses arrive.\n\n"
                "**Prefer re-delegation** over creating new items when the follow-up\n"
                "builds on work that was already done or is in progress."
            )

        if reason == CycleTriggerReason.RESPONSE_ARRIVED:
            return (
                "**RESPONSES ARRIVED - REVIEW PLAN**\n\n"
                "New responses have been received. You're in PLANNING phase, which means\n"
                "the system detected that the plan might need updates.\n\n"
                "**Your task:** Review the plan and decide:\n"
                "- Are new work items needed based on responses?\n"
                "- Should failed items be retried with different approach?\n"
                "- Is the plan still appropriate?\n\n"
                "Update plan if needed, or finish to proceed to next phase."
            )

        if not ctx.phase_changed:
            return (
                "**CONTINUE PLANNING**\n\n"
                "You're still in PLANNING phase.\n\n"
                "**Options:**\n"
                "- Delegate undelegated REMOTE items using `DelegateTaskTool`\n"
                "- Refine work items or update dependencies\n"
                "- Finish to proceed to next phase (all REMOTE items must be delegated first)"
            )

        return "Review and create/update the work plan. Delegate any REMOTE items."
