"""
WorkPlan data models.

Pydantic models for work planning and execution tracking.
Pure data models with no business logic or service dependencies.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timezone
from enum import Enum
import uuid


class WorkItemStatus(str, Enum):
    """
    Status of a work item.
    
    Status Semantics:
    - PENDING: Not yet assigned or started
    - IN_PROGRESS: Being executed (local) or delegated (remote)
      * For LOCAL items: Currently executing locally
      * For REMOTE items: Delegated and waiting for response
    - DONE: Successfully completed
    - FAILED: Failed after retries
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class WorkItemKind(str, Enum):
    """Kind of work item execution."""
    LOCAL = "local"    # Execute locally on this node
    REMOTE = "remote"  # Delegate to adjacent node


class ToolArguments(BaseModel):
    """Dynamic tool arguments for work items."""
    
    class Config:
        extra = "allow"  # Allow arbitrary additional fields
    
    def __init__(self, data: Optional[Dict[str, Any]] = None, **kwargs):
        """Initialize with either a dict or keyword arguments."""
        if data is not None:
            if kwargs:
                raise ValueError("Cannot provide both 'data' dict and keyword arguments")
            super().__init__(**data)
        else:
            super().__init__(**kwargs)
    
    def __len__(self) -> int:
        """Return the number of arguments."""
        return len(self.__dict__)
    
    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access."""
        return getattr(self, key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dict-like assignment."""
        setattr(self, key, value)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return hasattr(self, key)


class LocalExecution(BaseModel):
    """
    Local work execution record (for LOCAL work items).
    
    Captures what the orchestrator did directly without delegation.
    Simple narrative format - LLM describes execution naturally.
    """
    outcome: str = Field(
        ..., 
        description="Complete execution result: what was done, how it was done, and what was achieved. Natural narrative format."
    )
    executed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="When execution completed"
    )


class DelegationExchange(BaseModel):
    """
    Complete request-response exchange in a delegation conversation.
    
    Represents one complete turn: orchestrator asks → agent responds.
    Multiple exchanges form a multi-turn conversation.
    """
    # Ordering and identification
    sequence: int = Field(..., description="Turn number in conversation (0=first, 1=second, etc.)")
    task_id: str = Field(..., description="Unique task ID for this delegation")
    
    # Request side (what orchestrator asked)
    query: str = Field(..., description="What was specifically asked/delegated")
    delegated_to: str = Field(..., description="UID of agent this was delegated to")
    delegated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="When delegation was sent")
    
    # Response side (what agent answered)
    response_content: Optional[str] = Field(None, description="Agent's response text")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Structured data (AgentResult, etc.)")
    responded_by: Optional[str] = Field(None, description="Who responded (usually same as delegated_to)")
    responded_at: Optional[str] = Field(None, description="When response was received")
    
    # State tracking
    processed: bool = Field(default=False, description="Whether LLM has acted on this response (re-delegated or marked status)")
    
    @property
    def is_pending(self) -> bool:
        """Check if waiting for response."""
        return self.response_content is None
    
    @property
    def needs_attention(self) -> bool:
        """Check if has response but LLM hasn't acted on it yet."""
        return self.response_content is not None and not self.processed


class WorkItemResult(BaseModel):
    """
    Complete result container for both LOCAL and REMOTE work items.
    
    Design: Unified model that adapts based on work item kind.
    - REMOTE items: Use 'delegations' list to track conversation history
    - LOCAL items: Use 'local_execution' to record direct execution
    
    This follows SOLID principles: single model, different fields populated.
    """
    # For REMOTE items: delegation conversation history
    delegations: List[DelegationExchange] = Field(
        default_factory=list,
        description="Delegation conversation history (REMOTE items only). Empty for LOCAL items."
    )
    
    # For LOCAL items: execution record
    local_execution: Optional[LocalExecution] = Field(
        None, 
        description="Local execution details (LOCAL items only). None for REMOTE items."
    )
    
    # Common fields (both LOCAL and REMOTE)
    success: bool = Field(default=False, description="Final success status (set when marked DONE)")
    final_summary: Optional[str] = Field(None, description="Final synthesized result or conclusion")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured result data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    artifacts: List[str] = Field(default_factory=list, description="List of created artifacts")
    
    @property
    def pending_exchange(self) -> Optional[DelegationExchange]:
        """Get the currently pending delegation exchange (waiting for response), if any."""
        for ex in reversed(self.delegations):  # Check most recent first
            if ex.is_pending:
                return ex
        return None
    
    @property
    def latest_exchange(self) -> Optional[DelegationExchange]:
        """Get the most recent delegation exchange."""
        return self.delegations[-1] if self.delegations else None
    
    @property
    def has_unprocessed_responses(self) -> bool:
        """Check if any delegation responses need LLM interpretation."""
        return any(ex.needs_attention for ex in self.delegations)
    
    def conversation_summary(self, truncate: bool = False, max_chars: int = 250) -> str:
        """
        Format delegation history with state indicators for LLM interpretation.
        
        Shows clear indicators of what needs attention vs what's been handled.
        Helps LLM understand conversation state and decide next actions.
        
        Args:
            truncate: If True, truncate long responses for console display
            max_chars: Maximum characters for truncated responses
        
        Returns:
            Formatted string with conversation history and state indicators
        """
        if not self.delegations:
            return ""
        
        # Helper to truncate content
        def _truncate_if_needed(content: str) -> str:
            if truncate and len(content) > max_chars:
                return content[:max_chars] + "..."
            return content
        
        # Single exchange: simple format
        if len(self.delegations) == 1:
            ex = self.delegations[0]
            if ex.is_pending:
                return f"⏳ WAITING for response from {ex.delegated_to}"
            elif ex.needs_attention:
                content = _truncate_if_needed(ex.response_content)
                return f"🔔 NEW RESPONSE from {ex.responded_by} (needs your interpretation):\n  {content}"
            else:
                content = _truncate_if_needed(ex.response_content)
                return f"✓ Response from {ex.responded_by} (processed):\n  {content}"
        
        # Multi-turn conversation: detailed format
        lines = [f"Conversation History ({len(self.delegations)} turns):"]
        for ex in self.delegations:
            if ex.is_pending:
                lines.append(f"  [{ex.sequence}] ⏳ WAITING: Query sent to {ex.delegated_to}")
                lines.append(f"      Query: {ex.query}")
            elif ex.needs_attention:
                lines.append(f"  [{ex.sequence}] 🔔 NEW: Response from {ex.responded_by} (needs interpretation)")
                lines.append(f"      Query: {ex.query}")
                content = _truncate_if_needed(ex.response_content)
                lines.append(f"      Response: {content}")
            else:
                lines.append(f"  [{ex.sequence}] ✓ PROCESSED: {ex.responded_by}")
                content = _truncate_if_needed(ex.response_content)
                lines.append(f"      Response: {content}")
        
        return "\n".join(lines)


class WorkItem(BaseModel):
    """A single work item in a work plan."""
    
    # Core identification
    id: str = Field(..., description="Unique identifier for this work item")
    title: str = Field(..., description="Short, descriptive title")
    description: str = Field(..., description="Detailed description of the work")
    
    # Dependencies and execution
    dependencies: List[str] = Field(default_factory=list, description="Work item IDs that must complete first")
    status: WorkItemStatus = Field(default=WorkItemStatus.PENDING, description="Current status")
    kind: WorkItemKind = Field(default=WorkItemKind.LOCAL, description="Local or remote execution")
    
    # Assignment and execution details
    assigned_uid: Optional[str] = Field(None, description="UID of assigned node")
    tool: Optional[str] = Field(None, description="Tool to use for execution")
    args: ToolArguments = Field(default_factory=ToolArguments, description="Tool arguments")
    
    # Results and tracking
    result: Optional[WorkItemResult] = Field(None, description="Execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    child_thread_id: Optional[str] = Field(None, description="Child thread ID for re-delegation context continuity")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts before marking as failed")
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def is_ready_for_execution(self, completed_item_ids: Set[str]) -> bool:
        """Check if this item is ready for execution based on dependencies."""
        if self.status != WorkItemStatus.PENDING:
            return False
        
        # All dependencies must be completed
        for dep_id in self.dependencies:
            if dep_id not in completed_item_ids:
                return False
        
        return True
    
    def is_blocked(self, completed_item_ids: Set[str]) -> bool:
        """Check if this item is blocked by incomplete dependencies."""
        if self.status != WorkItemStatus.PENDING:
            return False
        
        # Check if any dependencies are not completed
        for dep_id in self.dependencies:
            if dep_id not in completed_item_ids:
                return True
        
        return False
    
    def can_retry(self) -> bool:
        """Check if this item can be retried."""
        from ..retry_policy import RetryPolicyService
        return RetryPolicyService.can_retry(self)
    
    def increment_retry(self) -> bool:
        """
        Increment retry count and mark as updated.
        
        Returns:
            True if increment was successful, False if max retries exceeded
        """
        from ..retry_policy import RetryPolicyService
        return RetryPolicyService.increment_retry(self)
    
    def has_unprocessed_responses(self) -> bool:
        """
        Check if this work item has unprocessed responses needing LLM action.
        
        Returns True only if:
        - Item is IN_PROGRESS (actively being worked on)
        - Item is REMOTE (delegated to another agent)
        - Item has result with delegations
        - At least one delegation response is unprocessed
        
        This is the canonical check for "orchestrator needs to act on this item's responses"
        """
        return (
            self.status == WorkItemStatus.IN_PROGRESS 
            and self.kind == WorkItemKind.REMOTE
            and self.result is not None
            and self.result.has_unprocessed_responses
        )
    
    def mark_updated(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()


class WorkItemStatusCounts(BaseModel):
    """
    Count of work items by status.
    
    Note: 'waiting' is removed - use in_progress with kind=REMOTE instead.
    'blocked' is a computed metric (PENDING items with incomplete dependencies).
    """
    pending: int = 0
    in_progress: int = 0
    done: int = 0
    failed: int = 0
    blocked: int = 0
    
    @property
    def total(self) -> int:
        """Total count of all items."""
        return self.pending + self.in_progress + self.done + self.failed + self.blocked


class WorkPlanStatus(BaseModel):
    """
    Complete status snapshot of a work plan.
    
    Single source of truth for work plan status across the system.
    Used by both service layer and phase decision logic.
    
    Note: waiting_items is kept for backward compatibility but is now
    calculated as (IN_PROGRESS items where kind=REMOTE). The actual
    status for these items is IN_PROGRESS.
    """
    exists: bool = False
    total_items: int = 0
    pending_items: int = 0
    in_progress_items: int = 0
    waiting_items: int = 0  # Calculated: IN_PROGRESS + kind=REMOTE
    done_items: int = 0
    failed_items: int = 0
    blocked_items: int = 0
    has_local_ready: bool = False
    has_remote_ready: bool = False  # True if any PENDING + kind=REMOTE items with dependencies met
    has_remote_waiting: bool = False  # True if any IN_PROGRESS + kind=REMOTE items exist
    has_responses: bool = False  # True if any IN_PROGRESS + kind=REMOTE items have result with delegations
    is_complete: bool = False


class WorkPlan(BaseModel):
    """A work plan containing multiple work items."""
    
    # Core identification
    summary: str = Field(..., description="High-level summary of the work plan")
    owner_uid: str = Field(..., description="UID of the node that owns this plan")
    thread_id: str = Field(..., description="Thread ID this plan belongs to")
    
    # Work items
    items: Dict[str, WorkItem] = Field(default_factory=dict, description="Work items by ID")
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @property
    def total_items(self) -> int:
        """Get the total number of work items in this plan."""
        return len(self.items)
    
    def get_completed_item_ids(self) -> Set[str]:
        """
        Get IDs of successfully completed items (DONE only).
        
        Note: FAILED items are NOT considered completed for dependency resolution.
        Items depending on FAILED items will be blocked until the dependency is
        retried successfully or the dependent item is explicitly marked as FAILED.
        
        This prevents cascade cycles where items appear "ready" but actually
        cannot proceed due to missing dependency results.
        """
        completed = set()
        for item_id, item in self.items.items():
            if item.status == WorkItemStatus.DONE:
                completed.add(item_id)
        return completed
    
    def get_failed_item_ids(self) -> Set[str]:
        """Get IDs of failed items."""
        failed = set()
        for item_id, item in self.items.items():
            if item.status == WorkItemStatus.FAILED:
                failed.add(item_id)
        return failed
    
    def get_ready_items(self) -> List[WorkItem]:
        """Get items that are ready for execution (dependencies satisfied)."""
        completed_ids = self.get_completed_item_ids()
        ready_items = []
        
        for item in self.items.values():
            if item.is_ready_for_execution(completed_ids):
                ready_items.append(item)
        
        return ready_items
    
    def get_blocked_items(self) -> List[WorkItem]:
        """Get items that are blocked by incomplete dependencies."""
        completed_ids = self.get_completed_item_ids()
        blocked_items = []
        
        for item in self.items.values():
            if item.is_blocked(completed_ids):
                blocked_items.append(item)
        
        return blocked_items
    
    def get_items_blocked_by_failure(self) -> List[WorkItem]:
        """
        Get items that are blocked specifically by failed dependencies.
        
        These items are PENDING but cannot proceed because one or more
        of their dependencies has FAILED. They need special handling:
        either retry the failed dependency or mark these items as failed too.
        """
        completed_ids = self.get_completed_item_ids()
        failed_ids = self.get_failed_item_ids()
        blocked_by_failure = []
        
        for item in self.items.values():
            if item.status == WorkItemStatus.PENDING:
                # Check if any dependencies are failed
                has_failed_dep = any(dep_id in failed_ids for dep_id in item.dependencies)
                # And item is blocked (not all deps are DONE)
                is_blocked = item.is_blocked(completed_ids)
                
                if has_failed_dep and is_blocked:
                    blocked_by_failure.append(item)
        
        return blocked_by_failure
    
    def get_items_by_status(self, status: WorkItemStatus) -> List[WorkItem]:
        """Get all items with the specified status."""
        return [item for item in self.items.values() if item.status == status]
    
    def get_status_counts(self) -> WorkItemStatusCounts:
        """
        Get count of items by status.
        
        Note: WAITING status is removed. Items that were WAITING are now IN_PROGRESS
        with kind=REMOTE. Use get_status_summary() to get waiting_items count.
        """
        counts = WorkItemStatusCounts()
        completed_ids = self.get_completed_item_ids()
        
        for item in self.items.values():
            if item.status == WorkItemStatus.PENDING:
                if item.is_blocked(completed_ids):
                    counts.blocked += 1
                else:
                    counts.pending += 1
            elif item.status == WorkItemStatus.IN_PROGRESS:
                counts.in_progress += 1
            elif item.status == WorkItemStatus.DONE:
                counts.done += 1
            elif item.status == WorkItemStatus.FAILED:
                counts.failed += 1
        
        return counts
    
    def is_complete(self) -> bool:
        """Check if all work items are complete (DONE or FAILED)."""
        if not self.items:
            return False
        
        for item in self.items.values():
            if item.status not in [WorkItemStatus.DONE, WorkItemStatus.FAILED]:
                return False
        
        return True
    
    def mark_updated(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_slim_snapshot(self) -> Dict[str, Any]:
        """
        Lightweight projection of the plan for streaming consumers.

        Keeps structural and status fields needed to track progress.
        Drops heavyweight internal fields (response_data, local_execution,
        metadata, artifacts, tool args, etc.) and caps delegation
        response_content at 200 chars to keep payloads small.
        """
        slim_items: Dict[str, Any] = {}

        for item_id, item in self.items.items():
            slim_delegations = None
            if item.result and item.result.delegations:
                slim_delegations = [
                    {
                        "sequence": ex.sequence,
                        "task_id": ex.task_id,
                        "query": ex.query,
                        "delegated_to": ex.delegated_to,
                        "delegated_at": ex.delegated_at,
                        "response_content": (
                            ex.response_content[:200] + "..."
                            if ex.response_content and len(ex.response_content) > 200
                            else ex.response_content
                        ),
                        "responded_at": ex.responded_at,
                    }
                    for ex in item.result.delegations
                ]

            slim_items[item_id] = {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "kind": item.kind.value,
                "status": item.status.value,
                "dependencies": item.dependencies,
                "assigned_uid": item.assigned_uid,
                "error": item.error,
                "retry_count": item.retry_count,
                "max_retries": item.max_retries,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "result": {
                    "delegations": slim_delegations or [],
                    "local_execution": None,
                    "success": item.result.success if item.result else False,
                    "final_summary": None,
                    "data": None,
                    "metadata": {},
                    "artifacts": [],
                } if item.result else None,
            }

        return {
            "summary": self.summary,
            "owner_uid": self.owner_uid,
            "thread_id": self.thread_id,
            "items": slim_items,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

