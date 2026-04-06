"""
Tool for reading workspace summary.
"""

from typing import Dict, Any, Callable
from pydantic import BaseModel, Field
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.nodes.common.agent.constants import ToolNames


class WorkspaceSummaryArgs(BaseModel):
    """Arguments for workspace summary."""
    max_messages: int = Field(10, description="Maximum number of recent messages to include")
    include_facts: bool = Field(True, description="Whether to include workspace facts")
    include_results: bool = Field(True, description="Whether to include agent results")


class ReadWorkspaceSummaryTool(BaseTool):
    """Read a summary of the current workspace state."""
    
    name = ToolNames.WORKSPACE_READ_SUMMARY
    description = "Get a summary of workspace contents including facts, recent messages, and results"
    args_schema = WorkspaceSummaryArgs
    
    def __init__(
        self,
        get_workspace: Callable[[], Any],
        get_thread_id: Callable[[], str]
    ):
        """
        Initialize with workspace accessor.
        
        Args:
            get_workspace: Function to get current workspace
            get_thread_id: Function to get current thread ID
        """
        self._get_workspace = get_workspace
        self._get_thread_id = get_thread_id
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """Read workspace summary."""
        args = WorkspaceSummaryArgs(**kwargs)
        workspace = self._get_workspace()
        
        summary = {
            "thread_id": self._get_thread_id(),
            "created_at": workspace.created_at.isoformat(),
            "last_updated": workspace.last_updated.isoformat()
        }
        
        # Include facts
        if args.include_facts and workspace.context.facts:
            summary["facts"] = workspace.context.facts[:20]  # Limit to 20 facts
            summary["total_facts"] = len(workspace.context.facts)
        
        # Include recent messages
        if workspace.context.conversation_history:
            recent_messages = workspace.context.conversation_history[-args.max_messages:]
            summary["recent_messages"] = [
                {
                    "role": msg.role.value,
                    "content": msg.content
                }
                for msg in recent_messages
            ]
            summary["total_messages"] = len(workspace.context.conversation_history)
        
        # Include agent results
        if args.include_results and workspace.context.results:
            recent_results = workspace.context.results[-5:]  # Last 5 results
            summary["recent_results"] = [
                {
                    "agent_name": result.agent_name,
                    "content": result.content
                }
                for result in recent_results
            ]
            summary["total_results"] = len(workspace.context.results)
        
        # Include variables keys (not values for privacy)
        if workspace.context.variables:
            summary["variable_keys"] = list(workspace.context.variables.keys())
        
        # Include artifacts summary
        if workspace.context.artifacts:
            summary["artifacts"] = [
                {
                    "name": name,
                    "type": ref.type,
                    "created_by": ref.created_by
                }
                for name, ref in list(workspace.context.artifacts.items())[:5]
            ]
            summary["total_artifacts"] = len(workspace.context.artifacts)
        
        return summary
