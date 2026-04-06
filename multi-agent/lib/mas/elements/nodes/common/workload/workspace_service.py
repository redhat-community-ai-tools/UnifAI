"""
Workspace Service for centralized workspace content management.

SOLID design focused solely on workspace content operations.
Separates workspace management from thread lifecycle.
Includes work plan management as work plans are workspace content.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from collections import defaultdict
import threading
from datetime import datetime, timezone
from .workspace import Workspace
from .models import (
    AgentResult,
    WorkPlan,
    WorkItemStatus,
    WorkPlanStatus,
    WorkItemResult,
    WorkItemKind,
)
from .hooks import WorkPlanHook, WorkPlanHookPoint
from mas.elements.llms.common.chat.message import ChatMessage


class IWorkspaceService(ABC):
    """
    Service focused solely on workspace content management.
    
    SOLID SRP: Only workspace content, not thread lifecycle.
    Provides clean API for all workspace operations.
    """
    
    # ========== WORKSPACE ACCESS ==========
    
    @abstractmethod
    def get_workspace(self, thread_id: str) -> Workspace:
        """
        Get workspace for thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Workspace instance (creates if doesn't exist)
        """
        pass
    
    @abstractmethod
    def update_workspace(self, workspace: Workspace) -> Workspace:
        """
        Update workspace in storage.
        
        Args:
            workspace: Workspace instance to update
            
        Returns:
            Updated Workspace instance
        """
        pass
    
    # ========== FACTS MANAGEMENT ==========
    
    @abstractmethod
    def add_fact(self, thread_id: str, fact: str) -> None:
        """
        Add fact to workspace.
        
        Args:
            thread_id: Thread ID
            fact: Fact string to add
        """
        pass
    
    @abstractmethod
    def remove_fact(self, thread_id: str, fact: str) -> None:
        """
        Remove fact from workspace.
        
        Args:
            thread_id: Thread ID
            fact: Fact string to remove
        """
        pass
    
    @abstractmethod
    def get_facts(self, thread_id: str) -> List[str]:
        """
        Get all facts from workspace.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of fact strings
        """
        pass
    
    @abstractmethod
    def clear_facts(self, thread_id: str) -> None:
        """
        Clear all facts from workspace.
        
        Args:
            thread_id: Thread ID
        """
        pass
    
    # ========== RESULTS MANAGEMENT ==========
    
    @abstractmethod
    def add_result(self, thread_id: str, result: AgentResult) -> None:
        """
        Add result to workspace.
        
        Args:
            thread_id: Thread ID
            result: AgentResult to add
        """
        pass
    
    @abstractmethod
    def get_results(self, thread_id: str) -> List[AgentResult]:
        """
        Get all results from workspace.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of AgentResult instances
        """
        pass
    
    @abstractmethod
    def get_results_by_agent(self, thread_id: str, agent_id: str) -> List[AgentResult]:
        """
        Get results by specific agent.
        
        Args:
            thread_id: Thread ID
            agent_id: Agent ID to filter by
            
        Returns:
            List of AgentResult instances from the agent
        """
        pass
    
    @abstractmethod
    def clear_results(self, thread_id: str) -> None:
        """
        Clear all results from workspace.
        
        Args:
            thread_id: Thread ID
        """
        pass
    
    # ========== VARIABLES MANAGEMENT ==========
    
    @abstractmethod
    def set_variable(self, thread_id: str, key: str, value: Any) -> None:
        """
        Set variable in workspace.
        
        Args:
            thread_id: Thread ID
            key: Variable key
            value: Variable value
        """
        pass
    
    @abstractmethod
    def get_variable(self, thread_id: str, key: str, default: Any = None) -> Any:
        """
        Get variable from workspace.
        
        Args:
            thread_id: Thread ID
            key: Variable key
            default: Default value if not found
            
        Returns:
            Variable value or default
        """
        pass
    
    @abstractmethod
    def remove_variable(self, thread_id: str, key: str) -> None:
        """
        Remove variable from workspace.
        
        Args:
            thread_id: Thread ID
            key: Variable key to remove
        """
        pass
    
    @abstractmethod
    def get_all_variables(self, thread_id: str) -> Dict[str, Any]:
        """
        Get all variables from workspace.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Dictionary of all variables
        """
        pass
    
    # ========== ARTIFACTS MANAGEMENT ==========
    
    @abstractmethod
    def add_artifact(self, thread_id: str, name: str, artifact_type: str, 
                     location: str, created_by: str, metadata: Dict[str, Any] = None) -> None:
        """
        Add artifact to workspace.
        
        Args:
            thread_id: Thread ID
            name: Artifact name
            artifact_type: Type of artifact
            location: Artifact location/path
            created_by: Creator ID
            metadata: Optional metadata dictionary
        """
        pass
    
    @abstractmethod
    def remove_artifact(self, thread_id: str, name: str) -> None:
        """
        Remove artifact from workspace.
        
        Args:
            thread_id: Thread ID
            name: Artifact name to remove
        """
        pass
    
    @abstractmethod
    def get_artifacts(self, thread_id: str) -> Dict[str, Any]:
        """
        Get all artifacts from workspace.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Dictionary of artifacts
        """
        pass
    
    @abstractmethod
    def get_artifacts_by_type(self, thread_id: str, artifact_type: str) -> List[Any]:
        """
        Get artifacts by type.
        
        Args:
            thread_id: Thread ID
            artifact_type: Type to filter by
            
        Returns:
            List of artifacts of the specified type
        """
        pass
    
    # ========== CONVERSATION MANAGEMENT ==========
    
    @abstractmethod
    def add_message(self, thread_id: str, message: ChatMessage) -> None:
        """
        Add message to conversation history.
        
        Args:
            thread_id: Thread ID
            message: ChatMessage to add
        """
        pass
    
    @abstractmethod
    def add_messages(self, thread_id: str, messages: List[ChatMessage]) -> None:
        """
        Add multiple messages to conversation history.
        
        Args:
            thread_id: Thread ID
            messages: List of ChatMessages to add
        """
        pass
    
    @abstractmethod
    def get_conversation_history(self, thread_id: str) -> List[ChatMessage]:
        """
        Get conversation history.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of ChatMessages
        """
        pass
    
    @abstractmethod
    def get_recent_messages(self, thread_id: str, count: int = 10) -> List[ChatMessage]:
        """
        Get recent messages from conversation.
        
        Args:
            thread_id: Thread ID
            count: Number of recent messages
            
        Returns:
            List of recent ChatMessages
        """
        pass
    
    @abstractmethod
    def clear_conversation(self, thread_id: str) -> None:
        """
        Clear conversation history.
        
        Args:
            thread_id: Thread ID
        """
        pass
    
    # ========== TASKS MANAGEMENT ==========
    
    @abstractmethod
    def add_task(self, thread_id: str, task: 'Task') -> None:
        """
        Add processed task to workspace.
        
        Args:
            thread_id: Thread ID
            task: Task to add
        """
        pass
    
    @abstractmethod
    def get_tasks(self, thread_id: str) -> List['Task']:
        """
        Get all tasks from workspace.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of Task instances
        """
        pass
    
    @abstractmethod
    def get_original_task(self, thread_id: str) -> Optional['Task']:
        """
        Get original task that requires response.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            First task that should_respond=True, or None
        """
        pass
    
    # ========== SUMMARY & CONTEXT ==========
    
    @abstractmethod
    def get_workspace_summary(self, thread_id: str) -> Dict[str, Any]:
        """
        Get workspace content summary.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Dictionary containing workspace statistics
        """
        pass
    
    @abstractmethod
    def get_context_summary(self, thread_id: str) -> Dict[str, Any]:
        """
        Get complete context summary.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Dictionary containing complete context information
        """
        pass
    
    @abstractmethod
    def clear_all_content(self, thread_id: str) -> None:
        """
        Clear all content from workspace.
        
        Args:
            thread_id: Thread ID
        """
        pass
    
    # ========== WORK PLAN MANAGEMENT ==========
    
    @abstractmethod
    def create_work_plan(self, thread_id: str, owner_uid: str, summary: str = "New Work Plan") -> WorkPlan:
        """
        Create a new work plan.
        
        Args:
            thread_id: Thread ID
            owner_uid: Owner node UID
            summary: Work plan summary
            
        Returns:
            Created WorkPlan instance
        """
        pass
    
    @abstractmethod
    def load_work_plan(self, thread_id: str, owner_uid: str) -> Optional[WorkPlan]:
        """
        Load work plan from workspace.
        
        Args:
            thread_id: Thread ID
            owner_uid: Owner node UID
            
        Returns:
            WorkPlan instance or None if not found
        """
        pass
    
    @abstractmethod
    def save_work_plan(self, plan: WorkPlan) -> bool:
        """
        Save work plan to workspace (thread-safe).
        
        Args:
            plan: WorkPlan instance to save
            
        Returns:
            True if saved successfully
        """
        pass
    
    @abstractmethod
    def get_work_plan_status(self, thread_id: str, owner_uid: str) -> WorkPlanStatus:
        """
        Get work plan status.
        
        Args:
            thread_id: Thread ID
            owner_uid: Owner node UID
            
        Returns:
            WorkPlanStatus with status information
        """
        pass
    
    @abstractmethod
    def update_work_item_status(
        self,
        thread_id: str,
        owner_uid: str,
        item_id: str,
        status: WorkItemStatus,
        error: str = None,
        correlation_task_id: str = None
    ) -> bool:
        """
        Update work item status (thread-safe).
        
        Args:
            thread_id: Thread ID
            owner_uid: Owner node UID
            item_id: Work item ID
            status: New status
            error: Optional error message
            correlation_task_id: Optional correlation task ID
            
        Returns:
            True if updated successfully
        """
        pass
    
    @abstractmethod
    def store_task_response_for_work_item(
        self,
        thread_id: str,
        owner_uid: str,
        correlation_task_id: str,
        response_content: str,
        from_uid: str,
        result_data: Any = None
    ) -> bool:
        """
        Store task response as context without changing status - let LLM interpret.
        
        Args:
            thread_id: Thread ID
            owner_uid: Owner node UID
            correlation_task_id: Correlation task ID
            response_content: Response content (string for LLM)
            from_uid: UID of responder
            result_data: Optional structured result data to preserve
            
        Returns:
            True if stored successfully
        """
        pass
    
    @abstractmethod
    def atomic_update_work_item(
        self,
        thread_id: str,
        owner_uid: str,
        item_id: str,
        update_func: callable
    ) -> bool:
        """
        Atomically update a work item using the provided function.
        
        Args:
            thread_id: Thread ID
            owner_uid: Owner node UID
            item_id: Work item ID
            update_func: Function that takes (item, plan) and modifies the item
            
        Returns:
            True if update succeeded
        """
        pass
    
    @abstractmethod
    def get_all_work_plans(self, thread_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all work plans in workspace.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Dictionary of work plans by owner_uid
        """
        pass
    
    @abstractmethod
    def remove_work_plan(self, thread_id: str, owner_uid: str) -> None:
        """
        Remove work plan from workspace.
        
        Args:
            thread_id: Thread ID
            owner_uid: Owner node UID
        """
        pass
    
    @abstractmethod
    def work_plan_exists(self, thread_id: str, owner_uid: str) -> bool:
        """
        Check if work plan exists.
        
        Args:
            thread_id: Thread ID
            owner_uid: Owner node UID
            
        Returns:
            True if work plan exists
        """
        pass
    
    # ========== GRAPHSTATE INTEGRATION ==========
    
    @abstractmethod
    def sync_from_graphstate(
        self,
        thread_id: str,
        graphstate_messages: List[ChatMessage], 
        limit: int = 10,
        strategy: str = "conversation"  # "facts" | "conversation" | "both"
    ) -> int:
        """
        Sync recent GraphState messages to workspace.
        
        Single, clean method that handles all GraphState → workspace synchronization.
        Automatically extracts recent messages and applies the specified strategy.
        
        Args:
            thread_id: Target workspace thread
            graphstate_messages: All GraphState messages (method will extract recent ones)
            limit: Maximum number of recent messages to sync
            strategy: Sync strategy:
                - "conversation": Add to conversation history (DEFAULT - preserves structure)
                - "facts": Add as contextual facts for LLM context
                - "both": Add as both facts and conversation history
            
        Returns:
            Number of messages actually synced
        """
        pass


class WorkspaceService(IWorkspaceService):
    """
    Concrete implementation of workspace service.
    
    SOLID DIP: Depends on storage abstraction for persistence.
    Provides all workspace operations through clean, focused API.
    """
    
    def __init__(self, storage):
        """
        Initialize with storage implementation.
        
        Args:
            storage: Storage implementation (StateBoundStorage or InMemoryStorage)
        """
        self._storage = storage
        self._workplan_hooks: List[WorkPlanHook] = []
    
    def get_workspace(self, thread_id: str) -> Workspace:
        """Get workspace for thread."""
        return self._storage.get_workspace(thread_id)
    
    def update_workspace(self, workspace: Workspace) -> Workspace:
        """Update workspace in storage."""
        return self._storage.update_workspace(workspace)
    
    # ========== WORKPLAN HOOKS MANAGEMENT ==========
    
    def add_workplan_hook(self, hook: WorkPlanHook) -> None:
        """Register a lifecycle hook for workplan operations."""
        self._workplan_hooks.append(hook)
    
    def remove_workplan_hook(self, hook: WorkPlanHook) -> None:
        """Unregister a workplan hook."""
        if hook in self._workplan_hooks:
            self._workplan_hooks.remove(hook)
    
    def clear_workplan_hooks(self) -> None:
        """Remove all workplan hooks."""
        self._workplan_hooks.clear()
    
    def get_workplan_hooks(self) -> List[WorkPlanHook]:
        """Get list of registered workplan hooks."""
        return list(self._workplan_hooks)
    
    def _execute_workplan_hooks(self, hook_point: WorkPlanHookPoint, *args, **kwargs) -> None:
        """Execute all registered workplan hooks for a lifecycle point."""
        if not self._workplan_hooks:
            return
        
        method_name = hook_point.value
        
        for hook in self._workplan_hooks:
            try:
                method = getattr(hook, method_name)
                method(*args, **kwargs)
            except Exception as e:
                hook_name = hook.__class__.__name__
                print(f"⚠️ [WORKPLAN-HOOK] Error in {hook_name}.{method_name}: {e}")
    
    # ========== FACTS MANAGEMENT ==========
    
    def add_fact(self, thread_id: str, fact: str) -> None:
        """Add fact to workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.add_fact(fact)
        self.update_workspace(workspace)
    
    def remove_fact(self, thread_id: str, fact: str) -> None:
        """Remove fact from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.remove_fact(fact)
        self.update_workspace(workspace)
    
    def get_facts(self, thread_id: str) -> List[str]:
        """Get all facts from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.facts
    
    def clear_facts(self, thread_id: str) -> None:
        """Clear all facts from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.clear_facts()
        self.update_workspace(workspace)
    
    # ========== RESULTS MANAGEMENT ==========
    
    def add_result(self, thread_id: str, result: AgentResult) -> None:
        """Add result to workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.add_result(result)
        self.update_workspace(workspace)
    
    def get_results(self, thread_id: str) -> List[AgentResult]:
        """Get all results from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.results
    
    def get_results_by_agent(self, thread_id: str, agent_id: str) -> List[AgentResult]:
        """Get results by specific agent."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_results_by_agent(agent_id)
    
    def clear_results(self, thread_id: str) -> None:
        """Clear all results from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.clear_results()
        self.update_workspace(workspace)
    
    # ========== VARIABLES MANAGEMENT ==========
    
    def set_variable(self, thread_id: str, key: str, value: Any) -> None:
        """Set variable in workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.set_variable(key, value)
        self.update_workspace(workspace)
    
    def get_variable(self, thread_id: str, key: str, default: Any = None) -> Any:
        """Get variable from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_variable(key, default)
    
    def remove_variable(self, thread_id: str, key: str) -> None:
        """Remove variable from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.remove_variable(key)
        self.update_workspace(workspace)
    
    def get_all_variables(self, thread_id: str) -> Dict[str, Any]:
        """Get all variables from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.variables
    
    # ========== ARTIFACTS MANAGEMENT ==========
    
    def add_artifact(self, thread_id: str, name: str, artifact_type: str, 
                     location: str, created_by: str, metadata: Dict[str, Any] = None) -> None:
        """Add artifact to workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.add_artifact(name, artifact_type, location, created_by, metadata)
        self.update_workspace(workspace)
    
    def remove_artifact(self, thread_id: str, name: str) -> None:
        """Remove artifact from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.remove_artifact(name)
        self.update_workspace(workspace)
    
    def get_artifacts(self, thread_id: str) -> Dict[str, Any]:
        """Get all artifacts from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.artifacts
    
    def get_artifacts_by_type(self, thread_id: str, artifact_type: str) -> List[Any]:
        """Get artifacts by type."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_artifact_by_type(artifact_type)
    
    # ========== CONVERSATION MANAGEMENT ==========
    
    def add_message(self, thread_id: str, message: ChatMessage) -> None:
        """Add message to conversation history."""
        workspace = self.get_workspace(thread_id)
        workspace.add_message(message)
        self.update_workspace(workspace)
    
    def add_messages(self, thread_id: str, messages: List[ChatMessage]) -> None:
        """Add multiple messages to conversation history."""
        workspace = self.get_workspace(thread_id)
        workspace.add_messages(messages)
        self.update_workspace(workspace)
    
    def get_conversation_history(self, thread_id: str) -> List[ChatMessage]:
        """Get conversation history."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.conversation_history
    
    def get_recent_messages(self, thread_id: str, count: int = 10) -> List[ChatMessage]:
        """Get recent messages from conversation."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_recent_messages(count)
    
    def clear_conversation(self, thread_id: str) -> None:
        """Clear conversation history."""
        workspace = self.get_workspace(thread_id)
        workspace.clear_conversation_history()
        self.update_workspace(workspace)
    
    # ========== TASKS MANAGEMENT ==========
    
    def add_task(self, thread_id: str, task: 'Task') -> None:
        """Add processed task to workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.context.tasks.append(task)
        self.update_workspace(workspace)
    
    def get_tasks(self, thread_id: str) -> List['Task']:
        """Get all tasks from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.tasks
    
    def get_original_task(self, thread_id: str) -> Optional['Task']:
        """Get original task that requires response."""
        workspace = self.get_workspace(thread_id)
        
        # Find first task that needs response and isn't itself a response
        for task in workspace.context.tasks:
            if task.should_respond and not task.is_response():
                return task
        
        return None
    
    # ========== SUMMARY & CONTEXT ==========
    
    def get_workspace_summary(self, thread_id: str) -> Dict[str, Any]:
        """Get workspace content summary."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_context_summary()
    
    def get_context_summary(self, thread_id: str) -> Dict[str, Any]:
        """Get complete context summary."""
        workspace = self.get_workspace(thread_id)
        return {
            "workspace_summary": workspace.get_context_summary(),
            "conversation_summary": workspace.get_conversation_summary(),
            "recent_messages": len(workspace.get_recent_messages(5)),
            "has_tasks": len(workspace.context.tasks) > 0
        }
    
    def clear_all_content(self, thread_id: str) -> None:
        """Clear all content from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.clear_all()
        self.update_workspace(workspace)
    
    # ========== GRAPHSTATE INTEGRATION IMPLEMENTATION ==========
    
    def sync_from_graphstate(
        self,
        thread_id: str,
        graphstate_messages: List[ChatMessage], 
        limit: int = 10,
        strategy: str = "conversation"
    ) -> int:
        """
        Sync recent GraphState messages to workspace.
        
        Single, unified method that handles all GraphState → workspace synchronization.
        Cleaner than having two separate methods that do almost the same thing.
        
        Strategy implementations:
        - "conversation": Add to conversation history (DEFAULT - preserves structure, avoids duplicates)
        - "facts": Add as contextual facts for LLM context
        - "both": Add as both facts and conversation history (avoids duplicates)
        
        Returns number of messages actually synced.
        """
        # Extract recent messages
        recent_messages = graphstate_messages[-limit:] if graphstate_messages else []
        
        if not recent_messages:
            return 0
        
        workspace = self.get_workspace(thread_id)
        
        # Apply strategy pattern
        if strategy == "facts":
            for msg in recent_messages:
                fact = f"Previous conversation - {msg.role.value}: {msg.content}"
                workspace.add_fact(fact)
        elif strategy == "conversation":
            workspace.append_messages_from_graphstate(recent_messages)
        elif strategy == "both":
            for msg in recent_messages:
                fact = f"Previous conversation - {msg.role.value}: {msg.content}"
                workspace.add_fact(fact)
            workspace.append_messages_from_graphstate(recent_messages)
        else:
            raise ValueError(f"Unknown sync strategy: {strategy}. Use 'facts', 'conversation', or 'both'")
        
        self.update_workspace(workspace)
        return len(recent_messages)
    
    # ========== WORK PLAN MANAGEMENT IMPLEMENTATION ==========
    
    # Class-level lock registry for thread-safe work plan operations
    _work_plan_locks: Dict[str, threading.RLock] = defaultdict(threading.RLock)
    _locks_lock = threading.Lock()
    
    def _get_work_plan_lock(self, thread_id: str, owner_uid: str) -> threading.RLock:
        """Get or create a lock for the specific workplan."""
        lock_key = f"{thread_id}:{owner_uid}"
        with self._locks_lock:
            return self._work_plan_locks[lock_key]
    
    def _with_work_plan_lock(self, thread_id: str, owner_uid: str):
        """Context manager for thread-safe workplan operations."""
        return self._get_work_plan_lock(thread_id, owner_uid)
    
    def create_work_plan(self, thread_id: str, owner_uid: str, summary: str = "New Work Plan") -> WorkPlan:
        """Create a new work plan."""
        plan = WorkPlan(
            summary=summary,
            owner_uid=owner_uid,
            thread_id=thread_id
        )
        return plan
    
    def load_work_plan(self, thread_id: str, owner_uid: str) -> Optional[WorkPlan]:
        """Load work plan from workspace."""
        try:
            workspace = self.get_workspace(thread_id)
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
            self._execute_workplan_hooks(WorkPlanHookPoint.POST_LOAD, plan, context)
            
            return plan
        except Exception as e:
            print(f"❌ [PLAN] Error loading: {e}")
            return None
    
    def save_work_plan(self, plan: 'WorkPlan') -> bool:
        """Save work plan to workspace (thread-safe)."""
        with self._with_work_plan_lock(plan.thread_id, plan.owner_uid):
            try:
                plan.mark_updated()
                
                workspace = self.get_workspace(plan.thread_id)
                workspace.context.work_plans[plan.owner_uid] = plan.model_dump()
                self.update_workspace(workspace)
                
                # POST-SAVE HOOK
                context = {
                    "thread_id": plan.thread_id,
                    "owner_uid": plan.owner_uid,
                    "operation": "save",
                    "success": True
                }
                self._execute_workplan_hooks(WorkPlanHookPoint.POST_SAVE, plan, context)
                
                return True
            except Exception as e:
                print(f"❌ [PLAN] Save error: {e}")
                return False
    
    def get_work_plan_status(self, thread_id: str, owner_uid: str) -> WorkPlanStatus:
        """Get work plan status."""
        plan = self.load_work_plan(thread_id, owner_uid)
        
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
        
        # Check for responses needing interpretation (IN_PROGRESS + REMOTE + unprocessed responses)
        has_responses = any(
            item.has_unprocessed_responses()
            for item in plan.items.values()
        )
        
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
            has_responses=has_responses,
            is_complete=plan.is_complete()
        )
        
        return status
    
    def update_work_item_status(
        self,
        thread_id: str,
        owner_uid: str,
        item_id: str,
        status: WorkItemStatus,
        error: str = None,
        correlation_task_id: str = None
    ) -> bool:
        """Update work item status (thread-safe)."""
        
        with self._with_work_plan_lock(thread_id, owner_uid):
            plan = self.load_work_plan(thread_id, owner_uid)
            if not plan:
                return False
            
            item = plan.items.get(item_id)
            if not item:
                return False
            
            
            old_status = item.status
            item.status = status
            
            if error and status == WorkItemStatus.FAILED:
                item.error = error
            
            if correlation_task_id:
                item.correlation_task_id = correlation_task_id
            
            # If marking as DONE, finalize the result
            if status == WorkItemStatus.DONE and item.result:
                item.result.success = True
                if item.result.metadata:
                    item.result.metadata.pop("needs_interpretation", None)
            
            item.mark_updated()
            self.save_work_plan(plan)
            return True
    
    def store_task_response_for_work_item(
        self,
        thread_id: str,
        owner_uid: str,
        correlation_task_id: str,
        response_content: str,
        from_uid: str,
        result_data: Any = None
    ) -> bool:
        """
        Store response by finding and filling pending DelegationExchange.
        
        Finds the delegation exchange matching the correlation_task_id and fills in
        the response fields. This is the core of multi-turn conversation support.
        
        Design: Each delegation creates a DelegationExchange with task_id. When response
        arrives, we find that exchange and fill it in. No overwriting, clean pairing.
        """
        plan = self.load_work_plan(thread_id, owner_uid)
        if not plan:
            return False
        
        # Find item with delegation exchange matching task_id
        target_item = None
        target_exchange = None
        
        for item in plan.items.values():
            if item.result and item.result.delegations:
                for exchange in item.result.delegations:
                    if exchange.task_id == correlation_task_id:
                        target_item = item
                        target_exchange = exchange
                        break
                if target_item:
                    break
        
        if not target_item or not target_exchange:
            return False
        
        # Extract structured data if provided
        from mas.elements.nodes.common.workload.models import AgentResult
        data_to_store = None
        if isinstance(result_data, AgentResult):
            data_to_store = result_data.model_dump()
        elif isinstance(result_data, dict):
            data_to_store = result_data
        
        # Fill in response fields
        target_exchange.response_content = response_content
        target_exchange.response_data = data_to_store
        target_exchange.responded_by = from_uid
        target_exchange.responded_at = datetime.now(timezone.utc).isoformat()
        # processed stays False - LLM needs to interpret
        
        target_item.mark_updated()
        return self.save_work_plan(plan)
    
    def atomic_update_work_item(
        self,
        thread_id: str,
        owner_uid: str,
        item_id: str,
        update_func: callable
    ) -> bool:
        """Atomically update a work item using the provided function."""
        with self._with_work_plan_lock(thread_id, owner_uid):
            plan = self.load_work_plan(thread_id, owner_uid)
            if not plan or item_id not in plan.items:
                return False
            
            item = plan.items[item_id]
            update_func(item, plan)
            item.mark_updated()
            return self.save_work_plan(plan)
    
    def get_all_work_plans(self, thread_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all work plans in workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.work_plans.copy()
    
    def remove_work_plan(self, thread_id: str, owner_uid: str) -> None:
        """Remove work plan from workspace."""
        workspace = self.get_workspace(thread_id)
        if owner_uid in workspace.context.work_plans:
            del workspace.context.work_plans[owner_uid]
            self.update_workspace(workspace)
    
    def work_plan_exists(self, thread_id: str, owner_uid: str) -> bool:
        """Check if work plan exists."""
        workspace = self.get_workspace(thread_id)
        return owner_uid in workspace.context.work_plans
