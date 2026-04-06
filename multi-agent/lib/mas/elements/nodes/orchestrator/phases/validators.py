"""Orchestrator-specific phase validators."""

from typing import Dict, Any, List
from mas.elements.nodes.common.agent.phases.models import PhaseValidationContext
from mas.elements.nodes.common.workload import WorkPlan, WorkItemStatus, WorkItemKind


class PlanningValidator:
    """
    Validates planning phase to ensure work plan quality.
    
    Supports multi-request workflows on same thread.
    
    SOLID SRP: Responsible only for planning phase validation logic.
    """
    
    def validate(self, context: PhaseValidationContext) -> str:
        """
        Validate planning phase state with multi-request awareness.
        
        Checks for common planning issues:
        - Missing work plan
        - Empty work plan
        - Circular dependencies
        - Provides guidance when existing plan is present
        
        Args:
            context: Validation context with work plan
            
        Returns:
            Guidance text if issues found, empty string if all good
        """
        plan = context.plan
        
        if not isinstance(plan, WorkPlan):
            return "No work plan found. Use CreateOrUpdateWorkPlanTool to create one."
        
        if not plan.items:
            return "Empty work plan. Break down the request into specific work items."
        
        # Check for circular dependencies
        circular = self._find_circular_dependencies(plan)
        if circular:
            return f"Circular dependencies detected: {circular}. Fix dependency chain."
        
        # ✅ NEW: Provide guidance for existing work plans (multi-request scenario)
        has_done_items = any(item.status == WorkItemStatus.DONE for item in plan.items.values())
        has_in_progress = any(item.status == WorkItemStatus.IN_PROGRESS for item in plan.items.values())
        has_failed = any(item.status == WorkItemStatus.FAILED for item in plan.items.values())
        
        sections: List[str] = []

        if has_done_items or has_in_progress or has_failed:
            done_count = sum(1 for item in plan.items.values() if item.status == WorkItemStatus.DONE)
            in_progress_count = sum(1 for item in plan.items.values() if item.status == WorkItemStatus.IN_PROGRESS)
            pending_count = sum(1 for item in plan.items.values() if item.status == WorkItemStatus.PENDING)
            failed_count = sum(1 for item in plan.items.values() if item.status == WorkItemStatus.FAILED)

            sections.append(
                f"EXISTING WORK PLAN DETECTED:\n"
                f"   Status: {done_count} done, {in_progress_count} in progress, "
                f"{pending_count} pending, {failed_count} failed\n\n"
                f"   FOR NEW REQUEST:\n"
                f"   - If independent work -> Add new items with CreateOrUpdateWorkPlanTool\n"
                f"   - If follow-up on completed work -> Add items depending on DONE items\n"
                f"   - If clarification only -> May not need new items, proceed to next phase\n"
                f"   - If re-do failed work -> Update failed items with new approach\n\n"
                f"   REMEMBER: CreateOrUpdateWorkPlanTool preserves existing item status!"
            )

        # Always check delegation readiness (even when plan has activity)
        delegation_issues = self._check_delegation_readiness(plan, context.adjacent_nodes)
        if delegation_issues:
            sections.append(delegation_issues)

        return "\n\n".join(sections)
    
    def _check_delegation_readiness(self, plan: WorkPlan, adjacent_nodes) -> str:
        """Check for REMOTE items that need delegation."""
        if adjacent_nodes is None:
            from mas.graph.models import AdjacentNodes
            adjacent_nodes = AdjacentNodes.empty()

        issues: List[str] = []

        for item in plan.items.values():
            if item.status != WorkItemStatus.PENDING or item.kind != WorkItemKind.REMOTE:
                continue
            if not item.result or not item.result.delegations:
                if item.assigned_uid and item.assigned_uid not in adjacent_nodes:
                    issues.append(
                        f"Remote item '{item.id}' assigned to non-adjacent '{item.assigned_uid}'. "
                        f"Use ListAdjacentNodesTool to find available agents."
                    )
                else:
                    issues.append(
                        f"Remote item '{item.id}' not yet delegated. "
                        f"Use DelegateTaskTool(dst_uid, content, work_item_id='{item.id}')."
                    )

        if issues:
            return "DELEGATION NEEDED:\n" + "\n".join(issues)
        return ""
    
    def _find_circular_dependencies(self, plan: WorkPlan) -> List[str]:
        """
        Find circular dependencies using DFS.
        
        Args:
            plan: Work plan to check
            
        Returns:
            List of item IDs involved in circular dependencies
        """
        visited = set()
        rec_stack = set()
        circular_items = []
        
        def dfs(item_id: str) -> bool:
            if item_id in rec_stack:
                circular_items.append(item_id)
                return True
            if item_id in visited:
                return False
            
            visited.add(item_id)
            rec_stack.add(item_id)
            
            item = plan.items.get(item_id)
            if item and item.dependencies:
                for dep_id in item.dependencies:
                    if dfs(dep_id):
                        circular_items.append(item_id)
                        return True
            
            rec_stack.remove(item_id)
            return False
        
        for item_id in plan.items:
            if item_id not in visited:
                dfs(item_id)
        
        return list(set(circular_items))


class ExecutionValidator:
    """Validates execution phase — flags data integrity issues only."""
    
    def validate(self, context: PhaseValidationContext) -> str:
        plan = context.plan
        if not isinstance(plan, WorkPlan) or not plan.items:
            return ""

        completed_ids = plan.get_completed_item_ids()
        blocked = [
            item for item in plan.items.values()
            if item.status == WorkItemStatus.PENDING
            and item.kind == WorkItemKind.LOCAL
            and item.is_blocked(completed_ids)
        ]

        if blocked:
            names = ", ".join(f"'{i.id}'" for i in blocked[:3])
            return f"BLOCKED: {len(blocked)} LOCAL item(s) waiting for dependencies: {names}"
        return ""


class MonitoringValidator:
    """Validates monitoring phase — flags blocked-by-failure items."""
    
    def validate(self, context: PhaseValidationContext) -> str:
        plan = context.plan
        if not isinstance(plan, WorkPlan) or not plan.items:
            return ""

        blocked_by_failure = plan.get_items_blocked_by_failure()
        if not blocked_by_failure:
            return ""

        items_text = ", ".join(
            f"'{i.id}' (blocked by "
            + ", ".join(d for d in i.dependencies
                        if plan.items.get(d) and plan.items[d].status == WorkItemStatus.FAILED)
            + ")"
            for i in blocked_by_failure[:3]
        )
        return f"BLOCKED BY FAILURE: {len(blocked_by_failure)} item(s): {items_text}"


class SynthesisValidator:
    """Validates synthesis phase — warns about incomplete work."""
    
    def validate(self, context: PhaseValidationContext) -> str:
        plan = context.plan
        if not isinstance(plan, WorkPlan) or not plan.items:
            return ""

        incomplete = [
            i for i in plan.items.values()
            if i.status not in [WorkItemStatus.DONE, WorkItemStatus.FAILED]
        ]
        if incomplete:
            return (
                f"WORK INCOMPLETE: {len(incomplete)} item(s) still in progress. "
                f"Note them in your response if proceeding."
            )
        return ""
