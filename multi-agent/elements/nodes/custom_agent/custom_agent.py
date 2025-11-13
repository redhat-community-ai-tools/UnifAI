from typing import Optional, Any, List, ClassVar, Set, Dict
from copy import deepcopy
from graph.state.state_view import StateView
from elements.llms.common.chat.message import ChatMessage, Role
from elements.tools.common.base_tool import BaseTool
from elements.nodes.common.base_node import BaseNode
from elements.nodes.common.capabilities.iem_capable import IEMCapableMixin
from elements.nodes.common.capabilities.llm_capable import LlmCapableMixin
from elements.nodes.common.capabilities.retriever_capable import RetrieverCapableMixin
from elements.nodes.common.capabilities.agent_capable import AgentCapableMixin
from elements.nodes.common.capabilities.workload_capable import WorkloadCapableMixin
from elements.nodes.common.workload import Task, AgentResult, WorkspaceContext
from elements.providers.mcp_server_client.mcp_provider import McpProvider
from elements.nodes.common.agent import AgentConfig
from elements.nodes.common.agent.execution import ExecutionMode
from elements.nodes.common.agent.constants import StrategyType
from elements.tools.common.execution.models import ExecutorConfig


class CustomAgentNode(
    WorkloadCapableMixin,
    IEMCapableMixin,
    AgentCapableMixin,
    LlmCapableMixin,
    RetrieverCapableMixin,
    BaseNode
):
    """
    CustomAgentNode with SOLID workload architecture integration.
    
    Features:
    - Uses new focused workload services (threads, workspaces, work_plans)
    - Processes work using workspace conversation context
    - Intelligent response routing based on task.should_respond
    - Clean service-based architecture for all workload operations
    - Comprehensive task and result tracking in workspace
    """

    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(
            self,
            *,
            llm: Any,
            retriever: Any = None,
            tools: List[BaseTool] = None,
            system_message: str = "",
            mcp_provider: McpProvider = None,
            max_rounds: Optional[int] = 15,
            strategy_type: str = StrategyType.REACT.value,
            **kwargs: Any
    ):
        super().__init__(
            llm=llm,
            retriever=retriever,
            system_message=system_message,
            **kwargs
        )
        self.mcp_provider = mcp_provider
        self.max_rounds = max_rounds
        self.strategy_type = strategy_type
        self.tools = tools or []

    def run(self, state: StateView) -> StateView:
        """Main entry point - process all incoming TaskPackets."""

        # Add MCP tools if available
        if self.mcp_provider:
            self.tools.extend(self.mcp_provider.get_tools())

        # Process all incoming packets
        self.process_packets(state)
        return state

    def handle_task_packet(self, packet) -> None:
        """
        Process work using workspace conversation context.
        
        SOLID Architecture Flow:
        1. Record task in workspace (self.workspaces.add_task)
        2. Build conversation context (self.workspaces.get_recent_messages + results)
        3. Process with LLM using agent execution system
        4. Add agent result to workspace (self.workspaces.add_result)
        5. Route response based on task.should_respond
        """
        try:
            # Extract and mark task as processed
            task = packet.extract_task()
            task.mark_processed(self.uid)
            
            # Record task in workspace for tracking
            if task.thread_id:
                self.workspaces.add_task(task.thread_id, task)

            # 1. Build conversation context
            conversation_context = self._build_conversation_context(task)

            # 2. Process with LLM - returns result dict
            execution_result = self._process_with_llm(conversation_context)

            # 3. Create agent result from execution result
            agent_result = self._create_agent_result(execution_result)

            # 4. Add agent result to workspace
            if task.thread_id:
                self._add_agent_result_to_workspace(task.thread_id, agent_result)

            # 5. Route response using agent result
            self._route_response(task, agent_result, packet)

            print(f"CustomAgent {self.uid}: Processed task, added result to workspace")

        except Exception as e:
            print(f"CustomAgent {self.uid}: Error processing task: {e}")
            # Create error agent result and send it
            error_result = AgentResult(
                content=f"Error processing task: {str(e)}",
                agent_id=self.uid,
                agent_name=self.display_name,
                success=False,
                error=str(e)
            )
            if task.thread_id:
                self._add_agent_result_to_workspace(task.thread_id, error_result)
            self._route_response(task, error_result, packet)

    def _build_conversation_context(self, task: Task) -> List[ChatMessage]:
        """
        Build conversation context:
        1. Get workspace conversation history
        2. Add system message if configured
        3. Add agent results context
        4. Add current task with retriever context if available
        """
        context_messages = []

        # 1. Get workspace conversation history
        if task.thread_id:
            workspace_messages = self.workspaces.get_recent_messages(task.thread_id, 20)
            context_messages.extend(deepcopy(workspace_messages))

        # 2. System message is now handled by strategy during creation
        # No longer adding system message to context here

        # 3. Add agent results context
        agent_results_context = self._build_agent_results_context(task.thread_id)
        if agent_results_context:
            context_messages.append(agent_results_context)

        # 4. Add current task with retriever context if available
        user_msg = ChatMessage(role=Role.USER, content=task.content)
        if self.retriever:
            user_msg = self.augment_with_context(user_msg)
        context_messages.append(user_msg)

        return context_messages

    def _build_agent_results_context(self, thread_id: str) -> Optional[ChatMessage]:
        """Build agent results context from workspace."""
        if not thread_id:
            return None

        workspace_results = self.workspaces.get_results(thread_id)

        if not workspace_results:
            return None

        # Focus on agent results - organized by agent name in order
        results_text = "PREVIOUS AGENT RESULTS:\n"
        for i, result in enumerate(workspace_results, 1):
            results_text += f"{i}. {result.agent_name}: {result.content}\n"

        return ChatMessage(role=Role.USER, content=results_text)

    def _process_with_llm(self, conversation_context: List[ChatMessage]) -> Dict[str, Any]:
        """
        Process conversation with LLM (with optional tools).
        
        Returns:
            Dict with keys: output, success, error, reasoning, metadata, metrics
        """
        if self.tools:
            # Use new agent execution system
            strategy = self.create_strategy(
                tools=self.tools,
                strategy_type=self.strategy_type,
                system_message=self.system_message,
                max_steps=self.max_rounds
            )

            config = AgentConfig(
                execution_mode=ExecutionMode.AUTO,
                executor_config=ExecutorConfig.create_balanced()
            )

            result = self.run_agent(
                messages=conversation_context,
                strategy=strategy,
                config=config
            )

            # Return result dict as-is (contains success, error, output, etc.)
            return result
        else:
            # No tools - use basic chat
            assistant_msg = self.chat(conversation_context)
            # Create a result dict that matches run_agent format
            return {
                "success": True,
                "output": assistant_msg.content,
                "error": None,
                "reasoning": "",
                "metadata": {},
                "metrics": {}
            }

    def _route_response(self, task: Task, agent_result: AgentResult, original_packet) -> None:
        """
        Agent Decision Logic:
        ┌─────────────────┐
        │ Custom Agent    │  IF task.should_respond == True:
        │                 │    
        │ ┌─────────────┐ │    Check adjacent nodes:
        │ │ Check       │ │    
        │ │ adjacent    │ │    IF original_requester in my_adjacent_nodes:
        │ │ nodes       │ │      → Respond directly
        │ │             │ │    
        │ │ IF requester│ │    ELSE:
        │ │ adjacent:   │ │      → Broadcast with response request
        │ │ → respond   │ │         (carry original requester info)
        │ │             │ │  
        │ │ ELSE:       │ │  ELSE (should_respond == False):
        │ │ → broadcast │ │    → Normal broadcast
        │ │ with        │ │
        │ │ response    │ │
        │ │ request     │ │
        │ └─────────────┘ │
        └─────────────────┘
        """
        if not task.should_respond:
            # Normal broadcast
            self._execute_normal_broadcast(task, agent_result)
        else:
            # Check if original requester is adjacent
            adjacent_nodes_uids = self._get_adjacent_nodes_uids()
            if task.response_to and task.response_to in adjacent_nodes_uids:
                # Direct response
                self._execute_direct_response(task, agent_result, original_packet)
            else:
                # Broadcast with response request
                self._execute_broadcast_with_response(task, agent_result)

    def _get_adjacent_nodes_uids(self) -> Set[str]:
        """Get adjacent node UIDs from network topology."""
        adjacent_nodes = self.get_adjacent_nodes()
        return set(adjacent_nodes.keys())

    def _execute_direct_response(self, task: Task, agent_result: AgentResult, original_packet) -> None:
        """Send direct response to requester - finished work."""
        response_task = Task.respond_success(
            original_task=task,
            result=agent_result,
            processed_by=self.uid
        )
        self.reply_task(original_packet, response_task)

    def _execute_broadcast_with_response(self, task: Task, agent_result: AgentResult) -> None:
        """Broadcast with response request - finished work."""
        response_task = task.fork(
            content="finished work",
            processed_by=self.uid,
            result=agent_result
        )
        response_task.should_respond = True
        response_task.response_to = task.response_to
        response_task.correlation_task_id = task.task_id  # Set correlation for response tracking

        self.broadcast_task(response_task)

    def _execute_normal_broadcast(self, task: Task, agent_result: AgentResult) -> None:
        """Normal broadcast - continue work."""
        forked_task = task.fork(
            content="continue work",
            processed_by=self.uid,
            result=agent_result
        )
        self.broadcast_task(forked_task)

    def _create_agent_result(self, execution_result: Dict[str, Any]) -> AgentResult:
        """
        Create AgentResult from execution result dict.
        
        Args:
            execution_result: Result dict from _process_with_llm with keys:
                - output: The content/response
                - success: Whether execution succeeded
                - error: Error message if failed
                - reasoning: Agent's reasoning process
                - metadata: Execution metadata
                - metrics: Performance metrics
        """
        # Extract output/content
        output = execution_result.get("output", "")
        if output is None:
            output = ""
        
        # If execution failed but no output, use error as content
        content = str(output) if output else execution_result.get("error", "No output produced")
        
        return AgentResult(
            content=content,
            agent_id=self.uid,
            agent_name=self.display_name,
            success=execution_result.get("success", True),
            error=execution_result.get("error"),
            reasoning=execution_result.get("reasoning", ""),
            execution_metadata=execution_result.get("metadata", {}),
            metrics=execution_result.get("metrics", {})
        )

    def _add_agent_result_to_workspace(self, thread_id: str, agent_result: AgentResult) -> None:
        """Add agent result to workspace using new service architecture."""
        self.workspaces.add_result(thread_id, agent_result)
    
    def get_thread_hierarchy_info(self, thread_id: str) -> str:
        """
        Example method showing clean usage of thread service.
        
        Demonstrates how to access thread hierarchy information
        using the new SOLID architecture.
        """
        if not thread_id:
            return "No thread ID provided"
        
        # Get thread hierarchy information
        thread = self.threads.get_thread(thread_id)
        if not thread:
            return f"Thread {thread_id} not found"
        
        # Get hierarchy path
        hierarchy_path = self.threads.get_hierarchy_path(thread_id)
        depth = self.threads.get_thread_depth(thread_id)
        root_thread = self.threads.find_root_thread(thread_id)
        
        info = [
            f"Thread: {thread.title} ({thread_id})",
            f"Initiator: {thread.initiator}",
            f"Hierarchy Depth: {depth}",
            f"Root Thread: {root_thread}",
            f"Hierarchy Path: {' → '.join(hierarchy_path)}"
        ]
        
        return "\n".join(info)
    
    def get_workspace_summary(self, thread_id: str) -> str:
        """
        Example method showing clean usage of workspace service.
        
        Demonstrates comprehensive workspace content access
        using the new SOLID architecture.
        """
        if not thread_id:
            return "No thread ID provided"
        
        # Get workspace content using focused services
        summary = self.workspaces.get_workspace_summary(thread_id)
        facts = self.workspaces.get_facts(thread_id)
        results = self.workspaces.get_results(thread_id)
        tasks = self.workspaces.get_tasks(thread_id)
        recent_messages = self.workspaces.get_recent_messages(thread_id, 5)
        
        info = [
            f"Workspace Summary for Thread: {thread_id}",
            f"Facts: {len(facts)} items",
            f"Results: {len(results)} items", 
            f"Tasks: {len(tasks)} items",
            f"Recent Messages: {len(recent_messages)} items",
            f"Last Updated: {summary.get('last_updated', 'Unknown')}"
        ]
        
        # Add recent facts if any
        if facts:
            info.append("\nRecent Facts:")
            for fact in facts[-3:]:  # Last 3 facts
                info.append(f"  - {fact}")
        
        return "\n".join(info)
