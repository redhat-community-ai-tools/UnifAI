"""
Tool for delegating tasks to other nodes.
"""

from typing import Dict, Any, Callable, Optional
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.nodes.common.workload import (
    Task,
    WorkItemStatus,
    WorkItemKind,
    DelegationExchange,
    WorkItemResult
)
from mas.elements.nodes.common.agent.constants import ToolNames


class DelegateTaskArgs(BaseModel):
    """Simplified arguments for delegating a task to an adjacent node."""
    dst_uid: str = Field(
        ..., 
        description="UID of the target adjacent node (check with ListAdjacentNodesTool first)"
    )
    content: str = Field(
        ...,
        description="Clear, detailed description of what the target node should do. Include context and expected deliverables."
    )
    work_item_id: str = Field(
        ...,
        description="ID of the work item being delegated (required for proper status tracking and response correlation)"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Additional structured data the target node might need"
    )


class DelegateTaskTool(BaseTool):
    """Delegate a task to an adjacent node via IEM."""
    
    name = ToolNames.IEM_DELEGATE_TASK
    description = """Delegate work to specialized agents with automatic thread and context management.
    
    PRIMARY USES:
    1. INITIAL DELEGATION: Send new work item to an agent
    2. RE-DELEGATION (Follow-up): Continue conversation with same agent for same work item
       - Thread context preserved automatically - agent sees previous conversation
       - Perfect for: clarifications, more details, refinements, elaborations
       - Example: "Please elaborate on point 3 from your previous response"
    
    WORKFLOW:
    1. Use ListAdjacentNodesTool to find capable nodes
    2. Use GetNodeCardTool to understand their capabilities  
    3. Use this tool to delegate with clear, specific instructions
    4. Thread automatically reused for same work_item_id (context preserved)
    5. Work item status automatically updates to 'in_progress' (remote delegation)
    
    RE-DELEGATION BENEFITS:
    ✅ Agent automatically sees previous responses (thread workspace)
    ✅ No need to repeat context in your message
    ✅ Enables iterative refinement and quality improvement
    ✅ Supports multi-turn conversations for complex tasks
    
    IMPORTANT: 
    - Be specific in 'content' - include requirements and expected deliverables
    - Always provide work_item_id to ensure proper orchestration workflow
    - For follow-ups: Just ask your question - agent has previous context
    - Feel free to delegate multiple times to get the quality you need"""
    args_schema = DelegateTaskArgs
    
    def __init__(
        self,
        send_task: Callable[[str, Task], str],
        get_owner_uid: Callable[[], str],
        get_current_thread: Callable[[], Any],  # Returns Thread object
        get_thread_service: Callable[[], Any],
        get_workspace_service: Callable[[], Any],
        check_adjacency: Optional[Callable[[str], bool]] = None
    ):
        """
        Initialize with focused service dependencies.
        
        Args:
            send_task: Function to send task via IEM (dst_uid, task) -> packet_id
            get_owner_uid: Function to get current node UID
            get_current_thread: Function to get current Thread object
            get_thread_service: Function to get thread service
            get_workspace_service: Function to get workspace service
            check_adjacency: Optional function to verify adjacency
        """
        self._send_task = send_task
        self._get_owner_uid = get_owner_uid
        self._get_current_thread = get_current_thread
        self._get_thread_service = get_thread_service
        self._get_workspace_service = get_workspace_service
        self._check_adjacency = check_adjacency
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """Delegate task to adjacent node with automatic thread and status management."""
        
        args = DelegateTaskArgs(**kwargs)
        
        # Get current thread context
        current_thread = self._get_current_thread()
        
        # Check adjacency if validator provided
        if self._check_adjacency and not self._check_adjacency(args.dst_uid):
            error_msg = f"Node {args.dst_uid} is not adjacent, or the uid is wrong, check what it is really adjacent"
            return {
                "success": False,
                "error": error_msg
            }
        
        # Prevent circular delegation
        if self._would_create_cycle(args.dst_uid, current_thread):
            error_msg = f"Circular delegation detected: {args.dst_uid} is already in delegation chain"
            return {
                "success": False,
                "error": error_msg
            }
        
        
        # Use provided work_item_id (now required)
        work_item_id = args.work_item_id
        
        # ✅ Check if this work item already has a child thread (re-delegation)
        workspace_service = self._get_workspace_service()
        owner_uid = self._get_owner_uid()
        plan = workspace_service.load_work_plan(current_thread.thread_id, owner_uid)
        target_item = plan.items.get(work_item_id) if plan else None
        
        # ✅ Validate that LOCAL items cannot be delegated (must be executed locally)
        if target_item and target_item.kind == WorkItemKind.LOCAL:
            error_msg = (
                f"Cannot delegate LOCAL work item '{work_item_id}'. "
                f"LOCAL items must be executed by the orchestrator, not delegated. "
                f"Only REMOTE items can be delegated to other agents."
            )
            return {
                "success": False,
                "error": error_msg
            }

        # ✅ Reuse existing child thread or create new one
        child_thread = None
        if target_item and target_item.child_thread_id:
            thread_service = self._get_thread_service()
            child_thread = thread_service.get_thread(target_item.child_thread_id)
            if not child_thread:
                child_thread = None

        if not child_thread:
            child_thread = current_thread.create_child(
                title=f"Delegated: {args.content[:50]}...",
                objective=args.content,
                initiator=owner_uid
            )

        # Create task (not sent yet — only sent after atomic update succeeds)
        task = Task.create(
            content=args.content,
            data=args.data,
            should_respond=True,
            thread_id=child_thread.thread_id,
            created_by=self._get_owner_uid()
        )
        task.data["work_item_id"] = work_item_id
        task.response_to = self._get_owner_uid()

        try:
            # ✅ Atomic update with pending_exchange guard INSIDE the lock.
            # Parallel DelegateTaskTool calls for the same item race here;
            # the lock ensures only one creates the exchange.
            validation_error = None

            def update_for_delegation(item, plan):
                """Validate and create delegation exchange under lock."""
                nonlocal validation_error

                # Guard: block if a previous delegation is still pending
                if item.result and item.result.pending_exchange:
                    pending = item.result.pending_exchange
                    validation_error = (
                        f"Work item '{work_item_id}' already has a pending delegation "
                        f"(task {pending.task_id} to {pending.delegated_to}). "
                        f"The agent is still processing — wait for the response."
                    )
                    return

                if not item.result:
                    item.result = WorkItemResult()

                for exchange in item.result.delegations:
                    exchange.processed = True

                sequence = len(item.result.delegations)
                exchange = DelegationExchange(
                    sequence=sequence,
                    task_id=task.task_id,
                    query=args.content or item.description,
                    delegated_to=args.dst_uid
                )

                item.result.delegations.append(exchange)
                item.status = WorkItemStatus.IN_PROGRESS
                item.kind = WorkItemKind.REMOTE
                item.assigned_uid = args.dst_uid
                item.child_thread_id = child_thread.thread_id

            success = workspace_service.atomic_update_work_item(
                current_thread.thread_id, owner_uid, work_item_id, update_for_delegation
            )

            if validation_error:
                return {"success": False, "error": validation_error}

            if not success:
                return {
                    "success": False,
                    "error": f"Work item {work_item_id} not found in work plan"
                }

            # ✅ Send IEM only after atomic update succeeded
            packet_id = self._send_task(args.dst_uid, task)

            # Save threads
            thread_service = self._get_thread_service()
            thread_service.save_thread(current_thread)
            thread_service.save_thread(child_thread)

            return {
                "success": True,
                "task_id": task.task_id,
                "packet_id": packet_id,
                "dst_uid": args.dst_uid,
                "child_thread_id": child_thread.thread_id,
                "parent_thread_id": current_thread.thread_id,
                "correlation_info": {
                    "task_id": task.task_id,
                    "work_item_id": work_item_id,
                    "child_thread_id": child_thread.thread_id
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delegate task: {str(e)}"
            }
    
    # ========== HELPER METHODS ==========
    
    def _would_create_cycle(self, dst_uid: str, current_thread) -> bool:
        """
        Check if delegation would create a cycle using thread service.
        
        Args:
            dst_uid: Target node UID for delegation
            current_thread: Current thread context
            
        Returns:
            True if delegation would create a cycle
        """
        try:
            thread_service = self._get_thread_service()
            return thread_service.detect_delegation_cycle(current_thread.thread_id, dst_uid)
        except Exception as e:
            return False  # Allow delegation if we can't check
    
