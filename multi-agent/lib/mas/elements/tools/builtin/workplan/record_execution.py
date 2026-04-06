"""
Tool for recording local execution results.
"""

from typing import Dict, Any, Callable
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.nodes.common.workload import WorkItemKind, WorkItemResult, LocalExecution, WorkItemStatus
from mas.elements.nodes.common.agent.constants import ToolNames


class RecordLocalExecutionArgs(BaseModel):
    """Arguments for recording local execution outcome."""
    item_id: str = Field(
        ..., 
        description="ID of the LOCAL work item you just executed"
    )
    outcome: str = Field(
        ..., 
        description="""Complete execution result in natural narrative format.
        
        Include:
        - What you did (approach, steps, tools if used)
        - How you did it (methods, reasoning)
        - What you achieved (results, findings, outputs, conclusions)
        
        Write naturally - this is for the SYNTHESIS phase to understand your work."""
    )


class RecordLocalExecutionTool(BaseTool):
    """Record execution results for LOCAL work items and mark as DONE.
    
    Use this tool after executing a LOCAL work item to capture what you did and what you achieved.
    Write naturally - describe your execution as a complete narrative.
    
    Workflow (ONE STEP):
    1. Execute LOCAL work item (use domain tools, reasoning, analysis)
    2. Call RecordLocalExecutionTool to capture outcome → automatically marks as DONE
    
    This creates a rich execution record for the SYNTHESIS phase to use."""
    
    name = ToolNames.WORKPLAN_RECORD_EXECUTION
    description = """Record the outcome of executing a LOCAL work item and mark it as DONE.
    
    After you execute work locally (with or without tools), use this to capture:
    - What you did
    - How you approached it
    - What you achieved
    
    Write as a natural narrative - include all relevant details for synthesis.
    This will automatically mark the item as DONE."""
    
    args_schema = RecordLocalExecutionArgs
    
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
        """Record local execution outcome with all validation inside the lock."""
        args = RecordLocalExecutionArgs(**kwargs)
        
        thread_id = self._get_thread_id()
        owner_uid = self._get_owner_uid()
        workload_service = self._get_workload_service()
        workspace_service = workload_service.get_workspace_service()

        validation_error = None

        def validate_and_record(item, plan):
            nonlocal validation_error

            # --- Guard 1: REMOTE items cannot use local execution ---
            if item.kind == WorkItemKind.REMOTE:
                validation_error = (
                    f"Cannot record local execution for REMOTE item '{args.item_id}'. "
                    f"Use DelegateTaskTool to delegate work to agents."
                )
                return

            # --- Guard 2: already DONE (idempotent, don't overwrite) ---
            if item.status == WorkItemStatus.DONE:
                validation_error = (
                    f"Item '{args.item_id}' is already DONE. "
                    f"No need to record execution again."
                )
                return

            # --- Guard 3: unmet dependencies ---
            completed_ids = plan.get_completed_item_ids()
            if item.is_blocked(completed_ids):
                unmet = [d for d in item.dependencies if d not in completed_ids]
                validation_error = (
                    f"Cannot execute '{args.item_id}' — blocked by unmet dependencies: "
                    f"{unmet}. Wait for them to complete first."
                )
                return

            # --- All guards passed — record and mark DONE ---
            if not item.result:
                item.result = WorkItemResult()

            item.result.local_execution = LocalExecution(outcome=args.outcome)
            item.status = WorkItemStatus.DONE

        success = workspace_service.atomic_update_work_item(
            thread_id, owner_uid, args.item_id, validate_and_record
        )

        if validation_error:
            return {"success": False, "error": validation_error}

        if not success:
            return {"success": False, "error": f"Work item '{args.item_id}' not found in work plan."}

        return {
            "success": True,
            "item_id": args.item_id,
            "status": "done",
            "message": f"Execution recorded for '{args.item_id}' and marked as DONE."
        }

