"""Execution phase — execute LOCAL work items using domain tools."""

from typing import Any, List

from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.tools.builtin.workplan.record_execution import RecordLocalExecutionTool
from mas.elements.tools.builtin.time import GetCurrentTimeTool

from .constants import OrchestratorPhase
from .base import Phase, PhaseDependencies, PlanSnapshotMode, PromptContext
from .validators import ExecutionValidator


class ExecutionPhase(Phase):
    name = OrchestratorPhase.EXECUTION
    snapshot_mode = PlanSnapshotMode.LOCAL_ONLY

    def create_tools(self, deps: PhaseDependencies) -> List[BaseTool]:
        return [
            RecordLocalExecutionTool(
                get_thread_id=deps.get_thread_id,
                get_owner_uid=deps.get_owner_uid,
                get_workload_service=deps.get_workload_service,
            ),
            GetCurrentTimeTool(),
        ] + list(deps.domain_tools)

    def get_guidance(self) -> str:
        return (
            "EXECUTION: Execute LOCAL work items using domain tools or reasoning.\n\n"
            "For each ready LOCAL item:\n"
            "1. Execute the work (use tools or your own reasoning)\n"
            "2. RecordLocalExecutionTool(item_id, outcome) — marks DONE automatically\n\n"
            "- Skip items with unmet dependencies (they'll appear when unblocked)\n"
            "- Write outcome as a narrative: what you did, results, findings\n"
            "- Do NOT touch REMOTE items (handled in MONITORING)"
        )

    def create_validator(self):
        return ExecutionValidator()

    def decide_next(self, status: Any) -> str:
        if status.is_complete:
            return OrchestratorPhase.SYNTHESIS
        if status.has_local_ready:
            return OrchestratorPhase.EXECUTION
        return OrchestratorPhase.MONITORING

    def on_limit_exceeded(self, status: Any) -> str:
        return OrchestratorPhase.MONITORING

    def build_focused_prompt(self, ctx: PromptContext) -> str:
        from mas.elements.nodes.common.workload import WorkItemKind

        plan = ctx.plan
        if not plan:
            return "Execute pending LOCAL work items."

        ready = plan.get_ready_items()
        blocked = plan.get_blocked_items()
        local_ready = [i for i in ready if i.kind == WorkItemKind.LOCAL]
        local_blocked = [i for i in blocked if i.kind == WorkItemKind.LOCAL]

        if ctx.phase_changed and local_ready:
            details = []
            for item in local_ready[:3]:
                details.append(f"  - `{item.id}`: {item.title}")
            if len(local_ready) > 3:
                details.append(f"  - (+{len(local_ready) - 3} more items)")
            return (
                f"**EXECUTE {len(local_ready)} LOCAL ITEM(S)**\n\n"
                f"Items ready to execute:\n" + "\n".join(details) + "\n\n"
                "**For EACH item:**\n"
                "1. Read the item description carefully\n"
                "2. Execute using your capabilities and available tools\n"
                "3. `RecordLocalExecutionTool(item_id, outcome)`\n"
                "   -> This automatically marks the item as DONE\n\n"
                "**Outcome format:** Describe what you did and the results."
            )

        if ctx.phase_changed and not local_ready and not local_blocked:
            return (
                "**NO LOCAL ITEMS TO EXECUTE**\n\n"
                "All LOCAL items already executed or none exist.\n\n"
                "Finish to proceed to next phase."
            )

        if ctx.phase_changed and local_blocked and not local_ready:
            names = ", ".join([f"'{i.id}'" for i in local_blocked[:2]])
            if len(local_blocked) > 2:
                names += f" (+{len(local_blocked) - 2} more)"
            return (
                "**LOCAL ITEMS BLOCKED**\n\n"
                f"{len(local_blocked)} items blocked by dependencies: {names}\n\n"
                "Cannot execute until dependencies complete.\n"
                "Finish to proceed (will return when unblocked)."
            )

        if not ctx.phase_changed and local_ready:
            return (
                f"**CONTINUE EXECUTION** ({len(local_ready)} remaining)\n\n"
                "Continue executing pending LOCAL items."
            )

        if not ctx.phase_changed and not local_ready:
            return (
                "**EXECUTION COMPLETE**\n\n"
                "All LOCAL items executed.\n\n"
                "Finish to proceed to next phase."
            )

        return "Execute pending LOCAL work items."
