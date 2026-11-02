"""
Streaming hook implementation for WorkPlan.

Emits workplan snapshots via callback when operations occur.
"""

import logging
from typing import Callable, Optional


from .hooks import BaseWorkPlanHook
from .models import WorkPlan

logger = logging.getLogger(__name__)


class WorkPlanStreamingHook(BaseWorkPlanHook):
    """Hook that streams workplan snapshots using model_dump()."""
    
    def __init__(self, stream_callback: Callable[[dict], None]):
        """
        Initialize with streaming callback.
        
        Args:
            stream_callback: Function to call with streaming data
        """
        self._stream_callback = stream_callback
    
    def on_post_save(self, plan: WorkPlan, context: dict) -> None:
        """Stream workplan snapshot after successful save."""
        try:
            self._emit_snapshot(plan, action="saved")
        except Exception as e:
            logger.error("workload.stream_hook_error", extra={"hook_point": "post_save", "thread_id": plan.thread_id, "owner_uid": plan.owner_uid, "error": str(e)})
    
    def on_post_load(self, plan: Optional[WorkPlan], context: dict) -> None:
        """Stream workplan snapshot after load (if plan exists)."""
        if plan:
            try:
                self._emit_snapshot(plan, action="loaded")
            except Exception as e:
                logger.error("workload.stream_hook_error", extra={"hook_point": "post_load", "thread_id": plan.thread_id, "owner_uid": plan.owner_uid, "error": str(e)})
    
    def on_post_delete(self, context: dict) -> None:
        """Stream deletion event."""
        try:
            self._stream_callback({
                "type": "workplan_deleted",
                "plan_id": f"{context['thread_id']}:{context['owner_uid']}",
                "thread_id": context['thread_id'],
                "owner_uid": context['owner_uid'],
                "action": "deleted"
            })
        except Exception as e:
            logger.error("workload.stream_hook_error", extra={"hook_point": "post_delete", "thread_id": context.get("thread_id"), "owner_uid": context.get("owner_uid"), "error": str(e)})
    
    def _emit_snapshot(self, plan: WorkPlan, action: str = "updated") -> None:
        """Emit complete workplan snapshot using model_dump()."""
        self._stream_callback({
            "type": "workplan_snapshot",
            "action": action,
            "plan_id": f"{plan.thread_id}:{plan.owner_uid}",
            "thread_id": plan.thread_id,
            "owner_uid": plan.owner_uid,
            "workplan": plan.model_dump()
        })

