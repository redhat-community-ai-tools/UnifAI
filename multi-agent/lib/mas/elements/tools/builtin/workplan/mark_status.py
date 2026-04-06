"""
Tool for marking work item status.
"""

from typing import Dict, Any, Optional, Callable, Literal
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.nodes.common.workload import WorkItemStatus, WorkItemKind
from mas.elements.nodes.common.agent.constants import ToolNames


class MarkStatusArgs(BaseModel):
    """Arguments for marking work item status."""
    item_id: str = Field(
        ..., 
        description="ID of the work item to update (get from work plan context)"
    )
    status: Literal['done', 'failed'] = Field(
        ..., 
        description="""Final status for the work item. Only two valid values:
        - 'done': Task completed successfully
        - 'failed': Task failed and cannot be completed
        
        Note: 
        - IN_PROGRESS is set automatically by DelegateTaskTool (not manual)
        - PENDING is the initial state (not set via this tool)
        - LOCAL items use RecordLocalExecutionTool (auto-marks DONE)"""
    )
    notes: Optional[str] = Field(
        None, 
        description="Explanation of the status change. REQUIRED for 'failed' to explain what went wrong. Helpful for 'done' to summarize accomplishments."
    )


class MarkWorkItemStatusTool(BaseTool):
    """Mark work item as DONE or FAILED after completion."""
    
    name = ToolNames.WORKPLAN_MARK
    description = """Mark work item status as DONE or FAILED.

    Use this when:
    - 'done': Work is complete, requirements met, quality acceptable
    - 'failed': Work cannot be completed (retries exhausted, fundamentally impossible)
    
    DO NOT use this for:
    - Setting IN_PROGRESS (DelegateTaskTool does this automatically)
    - Setting PENDING (initial state only)
    
    For REMOTE items: Review responses first, then mark done/failed
    For LOCAL items: RecordLocalExecutionTool auto-marks DONE (rarely need this tool)
    
    CRITICAL RULES:
    - If you re-delegated (sent a follow-up), do NOT mark done — wait for the response
    - Never call DelegateTaskTool AND MarkWorkItemStatusTool on the same item in one turn
    - Only mark 'done' when you're truly satisfied with the result"""
    args_schema = MarkStatusArgs
    
    def __init__(
        self,
        get_thread_id: Callable[[], str],
        get_owner_uid: Callable[[], str],
        get_workload_service: Callable[[], Any]
    ):
        self._get_thread_id = get_thread_id
        self._get_owner_uid = get_owner_uid
        self._get_workload_service = get_workload_service
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """Mark work item status with all validation inside the lock."""
        args = MarkStatusArgs(**kwargs)
        
        thread_id = self._get_thread_id()
        owner_uid = self._get_owner_uid()
        workload_service = self._get_workload_service()
        workspace_service = workload_service.get_workspace_service()

        validation_error = None

        def validate_and_update(item, plan):
            nonlocal validation_error

            target_status = WorkItemStatus.DONE if args.status == 'done' else WorkItemStatus.FAILED

            # --- Guard 1: already in target status (idempotent, no-op) ---
            if item.status == target_status:
                validation_error = f"Item '{args.item_id}' is already {args.status}."
                return

            # --- Guard 2: LOCAL items need RecordLocalExecutionTool for DONE ---
            if item.kind == WorkItemKind.LOCAL and target_status == WorkItemStatus.DONE:
                if not item.result or not item.result.local_execution:
                    validation_error = (
                        f"Cannot mark LOCAL item '{args.item_id}' as DONE without recording execution. "
                        f"Use RecordLocalExecutionTool instead — it records and marks DONE atomically."
                    )
                    return

            # --- Guard 3: pending delegation (follow-up in flight) ---
            if (target_status == WorkItemStatus.DONE
                    and item.kind == WorkItemKind.REMOTE
                    and item.result and item.result.pending_exchange):
                pending = item.result.pending_exchange
                validation_error = (
                    f"Cannot mark '{args.item_id}' as DONE — a follow-up is pending with "
                    f"{pending.delegated_to} (sent: \"{pending.query[:60]}...\"). "
                    f"Wait for the response in a future cycle, or mark 'failed' to abandon."
                )
                return

            # --- Guard 4: PENDING item with no work done at all ---
            if (target_status == WorkItemStatus.DONE
                    and item.status == WorkItemStatus.PENDING):
                validation_error = (
                    f"Cannot mark PENDING item '{args.item_id}' as DONE — no work was performed. "
                    f"Delegate it first (REMOTE) or execute it (LOCAL)."
                )
                return

            # --- All guards passed — apply the update ---
            item.status = target_status

            if target_status == WorkItemStatus.FAILED and args.notes:
                item.error = args.notes

            if item.result and item.result.delegations:
                for exchange in item.result.delegations:
                    exchange.processed = True

            if args.notes and item.result:
                item.result.final_summary = args.notes

            if target_status == WorkItemStatus.DONE and item.result:
                item.result.success = True

        success = workspace_service.atomic_update_work_item(
            thread_id, owner_uid, args.item_id, validate_and_update
        )

        if validation_error:
            return {"success": False, "error": validation_error}

        if not success:
            return {"success": False, "error": f"Work item '{args.item_id}' not found in work plan."}

        return {
            "success": True,
            "item_id": args.item_id,
            "new_status": args.status
        }
