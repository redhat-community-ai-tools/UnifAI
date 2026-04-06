"""
Tool for creating or updating work plans.
"""

from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.nodes.common.workload import WorkPlan, WorkItem, WorkItemKind, WorkItemStatus
from mas.elements.nodes.common.agent.constants import ToolNames


class WorkItemSpec(BaseModel):
    """Specification for a work item to be created."""
    id: str = Field(..., description="Unique identifier for the work item (use snake_case, e.g., 'analyze_data')")
    title: str = Field(..., description="Short, descriptive title for the work item")
    description: str = Field(..., description="Detailed description of what needs to be done")
    dependencies: List[str] = Field(
        default_factory=list, 
        description="List of work item IDs that must complete before this item can start"
    )
    kind: WorkItemKind = Field(
        default=WorkItemKind.REMOTE,
        description="LOCAL for tasks you can do yourself, REMOTE for tasks to delegate to other nodes"
    )
    assigned_uid: Optional[str] = Field(
        None,
        description="Optional: Pre-assign to specific node UID (will be set automatically when delegating)"
    )


class CreateOrUpdatePlanArgs(BaseModel):
    """Arguments for creating or updating a work plan."""
    summary: str = Field(
        ..., 
        description="High-level summary of what this work plan accomplishes (e.g., 'Analyze Q4 sales data and create presentation')"
    )
    items: List[WorkItemSpec] = Field(
        ...,
        description="List of work items to create. Each item should have a clear purpose and dependencies.",
        min_items=1
    )


class CreateOrUpdateWorkPlanTool(BaseTool):
    """Create or update a work plan with structured work items."""
    
    name = ToolNames.WORKPLAN_CREATE_OR_UPDATE
    description = """Create a new work plan or update existing plan with structured work items.
    
    Use this to:
    - Break down complex requests into manageable work items
    - Add new work items to handle responses like "I need X and Y first"
    - Update work items based on changing requirements
    - Structure dependencies between work items
    
    WORK ITEM GUIDELINES:
    - Each item should be specific and actionable
    - Use LOCAL for tasks you can do yourself, REMOTE for delegation
    - Set dependencies by item ID (items wait for dependencies to be 'done')
    - Use snake_case for IDs (e.g., 'analyze_data', 'create_report')
    - Do NOT create synthesis/summarize/compile items — the SYNTHESIS phase handles final answers automatically
    
    DEPENDENCY EXAMPLES:
    - Item 'create_report' depends on ['analyze_data', 'gather_feedback']
    - Item 'analyze_data' has no dependencies (can start immediately)
    
    WHEN TO USE:
    - Initial planning: Break down the main request
    - Response handling: Add items for "I need X first" scenarios
    - Replanning: Adjust based on new information or failures"""
    args_schema = CreateOrUpdatePlanArgs
    
    def __init__(
        self,
        get_thread_id: Callable[[], str],
        get_owner_uid: Callable[[], str],
        get_workload_service: Callable[[], Any]
    ):
        """
        Initialize with clean SOLID dependencies.
        
        Args:
            get_thread_id: Function to get current thread ID
            get_owner_uid: Function to get owner node UID
            get_workload_service: Function to get workload service
        """
        self._get_thread_id = get_thread_id
        self._get_owner_uid = get_owner_uid
        self._get_workload_service = get_workload_service
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """Create or update work plan (thread-safe with atomic operations)."""
        
        args = CreateOrUpdatePlanArgs(**kwargs)
        
        # Get context
        thread_id = self._get_thread_id()
        owner_uid = self._get_owner_uid()
        workload_service = self._get_workload_service()
        workspace_service = workload_service.get_workspace_service()
        
        
        # ✅ FIX: Use lock to prevent race conditions with mark tool
        # All operations within single lock to ensure atomicity
        with workspace_service._with_work_plan_lock(thread_id, owner_uid):
            # Load existing plan or create new one
            plan = workspace_service.load_work_plan(thread_id, owner_uid)
            if not plan:
                plan = workspace_service.create_work_plan(
                    thread_id=thread_id,
                    owner_uid=owner_uid,
                    summary=args.summary
                )
                workspace_service.save_work_plan(plan)
            else:
                plan.summary = args.summary
            
            # Process each item atomically
            for i, item_spec in enumerate(args.items):
                
                if item_spec.id in plan.items:
                    existing_item = plan.items[item_spec.id]
                    
                    # Guard: don't mutate kind on active items (would corrupt state)
                    if (existing_item.status != WorkItemStatus.PENDING
                            and item_spec.kind != existing_item.kind):
                        continue

                    existing_item.title = item_spec.title
                    existing_item.description = item_spec.description
                    existing_item.dependencies = item_spec.dependencies
                    existing_item.kind = item_spec.kind
                    
                    if item_spec.assigned_uid is not None:
                        existing_item.assigned_uid = item_spec.assigned_uid
                    
                    existing_item.mark_updated()
                else:
                    # ✅ CREATE: New item with defaults
                    new_item = WorkItem(
                        id=item_spec.id,
                        title=item_spec.title,
                        description=item_spec.description,
                        dependencies=item_spec.dependencies,
                        kind=item_spec.kind,
                        assigned_uid=item_spec.assigned_uid  # ✅ Support pre-assignment
                    )
                    plan.items[item_spec.id] = new_item
            
            # Save once at the end (within lock)
            workspace_service.save_work_plan(plan)
        
        # Get status summary for response
        status_summary = workspace_service.get_work_plan_status(thread_id, owner_uid)
        
        result = {
            "success": True,
            "plan_id": f"{thread_id}:{owner_uid}",
            "total_items": status_summary.total_items,
            "status_counts": {
                "pending": status_summary.pending_items,
                "waiting": status_summary.waiting_items,
                "in_progress": status_summary.in_progress_items,
                "done": status_summary.done_items,
                "failed": status_summary.failed_items,
                "blocked": status_summary.blocked_items
            }
        }
        
        return result
