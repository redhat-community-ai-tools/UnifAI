"""
WorkPlan service layer.

Provides business logic and service operations for work plan management.
Models are now in models/workplan_models.py.
"""

import logging
import threading
from collections import defaultdict
from typing import Dict, List, Optional


from .models import (
    WorkPlan,
    WorkItem,
    WorkItemStatus,
    WorkItemKind,
    WorkPlanStatus,
)
from .hooks import WorkPlanHook, WorkPlanHookPoint

logger = logging.getLogger(__name__)


class WorkPlanService:
    """
    Domain service for WorkPlan operations.
    
    SOLID design: Handles all work plan business logic and workspace access.
    Directly manages work plans stored in workspace.context.work_plans field.
    
    Responsibilities:
    - Work plan CRUD operations (create, load, save, remove)
    - Business logic (status transitions, delegation, response ingestion)
    - Thread-safe atomic updates with per-plan locking
    - Direct workspace access for work plan data management
    
    Thread-safe: Uses RLock per (thread_id, owner_uid) to prevent race conditions.
    """
    
    # Class-level lock registry to ensure same lock instance per workplan
    _locks: Dict[str, threading.RLock] = defaultdict(threading.RLock)
    _locks_lock = threading.Lock()  # Protects the locks dictionary itself
    
    def __init__(self, workspace_service, thread_service):
        """
        Initialize with focused service dependencies.
        
        Args:
            workspace_service: IWorkspaceService for workspace operations
            thread_service: IThreadService for thread hierarchy operations
        """
        self._workspace_service = workspace_service
        self._thread_service = thread_service
        self._hooks: List[WorkPlanHook] = []
    
    def _get_lock(self, thread_id: str, owner_uid: str) -> threading.RLock:
        """Get or create a lock for the specific workplan."""
        lock_key = f"{thread_id}:{owner_uid}"
        with self._locks_lock:
            return self._locks[lock_key]
    
    def with_lock(self, thread_id: str, owner_uid: str):
        """Context manager for thread-safe workplan operations."""
        return self._get_lock(thread_id, owner_uid)
    
    # -------------------------------------------------------------------------
    # Hook Management API
    # -------------------------------------------------------------------------
    
    def add_hook(self, hook: WorkPlanHook) -> None:
        """Register a lifecycle hook."""
        self._hooks.append(hook)
    
    def remove_hook(self, hook: WorkPlanHook) -> None:
        """Unregister a hook."""
        if hook in self._hooks:
            self._hooks.remove(hook)
    
    def clear_hooks(self) -> None:
        """Remove all hooks."""
        self._hooks.clear()
    
    def get_hooks(self) -> List[WorkPlanHook]:
        """Get list of registered hooks."""
        return list(self._hooks)
    
    # -------------------------------------------------------------------------
    # Hook Execution (Internal)
    # -------------------------------------------------------------------------
    
    def _execute_hooks(self, hook_point: WorkPlanHookPoint, *args, **kwargs) -> None:
        """Execute all registered hooks for a lifecycle point."""
        if not self._hooks:
            return
        
        method_name = hook_point.value
        
        for hook in self._hooks:
            try:
                method = getattr(hook, method_name)
                method(*args, **kwargs)
            except Exception as e:
                hook_name = hook.__class__.__name__
                logger.error("workload.plan_hook_error", extra={"hook": hook_name, "method": method_name, "error": str(e)})
    
    # -------------------------------------------------------------------------
    # WorkPlan Operations
    # -------------------------------------------------------------------------
    
    def create(self, thread_id: str, owner_uid: str) -> WorkPlan:
        """Create a new work plan."""
        plan = WorkPlan(
            summary="New Work Plan",
            owner_uid=owner_uid,
            thread_id=thread_id
        )
        return plan
    
    def load(self, thread_id: str, owner_uid: str) -> Optional[WorkPlan]:
        """Load work plan from dedicated workspace field."""
        try:
            workspace = self._workspace_service.get_workspace(thread_id)
            plan_data = workspace.context.work_plans.get(owner_uid)
            
            plan = None
            if plan_data:
                plan = WorkPlan(**plan_data)
            
            # POST-LOAD HOOK
            context = {
                "thread_id": thread_id,
                "owner_uid": owner_uid,
                "operation": "load",
                "found": plan is not None
            }
            self._execute_hooks(WorkPlanHookPoint.POST_LOAD, plan, context)
            
            return plan
        except Exception as e:
            logger.error("workload.plan_load_error", extra={"thread_id": thread_id, "owner_uid": owner_uid, "error": str(e)})
            return None
    
    def load_for_response(self, response_thread_id: str, owner_uid: str) -> Optional[WorkPlan]:
        """
        Load work plan for response processing.
        
        Automatically resolves target thread using thread service.
        This handles child thread responses by finding the thread that owns the work plan.
        
        Args:
            response_thread_id: Thread ID from response (may be child thread)
            owner_uid: Owner node identifier
            
        Returns:
            WorkPlan instance for the correct thread, or None if not found
        """
        target_thread_id = self._thread_service.find_work_plan_owner(response_thread_id, owner_uid)
        if not target_thread_id:
            logger.error("workload.plan_owner_not_found", extra={"response_thread_id": response_thread_id, "owner_uid": owner_uid})
            return None
            
        return self.load(target_thread_id, owner_uid)
    
    def save(self, plan: WorkPlan) -> bool:
        """Save work plan to dedicated workspace field (thread-safe)."""
        with self.with_lock(plan.thread_id, plan.owner_uid):
            try:
                plan.mark_updated()
                
                workspace = self._workspace_service.get_workspace(plan.thread_id)
                workspace.context.work_plans[plan.owner_uid] = plan.model_dump()
                self._workspace_service.update_workspace(workspace)
                
                # POST-SAVE HOOK
                context = {
                    "thread_id": plan.thread_id,
                    "owner_uid": plan.owner_uid,
                    "operation": "save",
                    "success": True
                }
                self._execute_hooks(WorkPlanHookPoint.POST_SAVE, plan, context)
                
                return True
            except Exception as e:
                logger.error("workload.plan_save_error", extra={"thread_id": plan.thread_id, "owner_uid": plan.owner_uid, "error": str(e)})
                return False
    
    def remove(self, thread_id: str, owner_uid: str) -> bool:
        """Remove work plan from workspace (thread-safe)."""
        with self.with_lock(thread_id, owner_uid):
            try:
                workspace = self._workspace_service.get_workspace(thread_id)
                if owner_uid in workspace.context.work_plans:
                    del workspace.context.work_plans[owner_uid]
                    self._workspace_service.update_workspace(workspace)
                    
                    # POST-DELETE HOOK
                    context = {
                        "thread_id": thread_id,
                        "owner_uid": owner_uid,
                        "operation": "delete",
                        "success": True
                    }
                    self._execute_hooks(WorkPlanHookPoint.POST_DELETE, context)
                    
                    return True
                return False
            except Exception as e:
                logger.error("workload.plan_remove_error", extra={"thread_id": thread_id, "owner_uid": owner_uid, "error": str(e)})
                return False
    
    def get_status(self, thread_id: str, owner_uid: str) -> WorkPlanStatus:
        """
        Get status for work plan.
        
        Calculates waiting_items as IN_PROGRESS + kind=REMOTE items.
        This maintains backward compatibility while using the new status model.
        """
        plan = self.load(thread_id, owner_uid)
        
        if not plan:
            return WorkPlanStatus(exists=False)
        
        counts = plan.get_status_counts()
        ready_items = plan.get_ready_items()
        
        # Check for local ready items (PENDING + LOCAL + dependencies met)
        has_local_ready = any(
            item.kind == WorkItemKind.LOCAL 
            for item in ready_items
        )
        
        # Check for remote ready items (PENDING + REMOTE + dependencies met)
        has_remote_ready = any(
            item.kind == WorkItemKind.REMOTE
            for item in ready_items
        )
        
        # Calculate remote waiting items (IN_PROGRESS + REMOTE)
        remote_in_progress_items = [
            item for item in plan.items.values()
            if item.status == WorkItemStatus.IN_PROGRESS and item.kind == WorkItemKind.REMOTE
        ]
        
        has_remote_waiting = len(remote_in_progress_items) > 0
        waiting_items_count = len(remote_in_progress_items)
        
        status = WorkPlanStatus(
            exists=True,
            total_items=len(plan.items),
            pending_items=counts.pending,
            in_progress_items=counts.in_progress,
            waiting_items=waiting_items_count,  # Calculated from IN_PROGRESS + REMOTE
            done_items=counts.done,
            failed_items=counts.failed,
            blocked_items=counts.blocked,
            has_local_ready=has_local_ready,
            has_remote_ready=has_remote_ready,
            has_remote_waiting=has_remote_waiting,
            is_complete=plan.is_complete()
        )
        
        return status
