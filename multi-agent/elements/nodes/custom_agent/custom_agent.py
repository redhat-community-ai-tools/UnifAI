from typing import Optional, Any, List, ClassVar, Set
from copy import deepcopy
from graph.state.state_view import StateView
from elements.llms.common.chat.message import ChatMessage, Role
from elements.nodes.common.base_node import BaseNode
from elements.nodes.common.capabilities.iem_capable import IEMCapableMixin
from elements.nodes.common.capabilities.llm_capable import LlmCapableMixin
from elements.nodes.common.capabilities.retriever_capable import RetrieverCapableMixin
from elements.nodes.common.capabilities.tool_capable import ToolCapableMixin
from elements.nodes.common.capabilities.workload_capable import WorkloadCapableMixin
from elements.nodes.common.workload import Task, AgentResult, WorkspaceContext
from elements.providers.mcp_server_client.mcp_provider import McpProvider


class CustomAgentNode(
    WorkloadCapableMixin,
    IEMCapableMixin,
    LlmCapableMixin,
    RetrieverCapableMixin,
    ToolCapableMixin,
    BaseNode
):
    """
    Enhanced CustomAgentNode with workload integration.
    
    Features:
    - Processes work using workspace conversation context
    - Intelligent response routing based on task.should_respond
    - Adds agent results to workspace
    - Clean SOLID architecture with simple methods
    """

    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(
            self,
            *,
            llm: Any,
            retriever: Any = None,
            tools: List[Any] = None,
            system_message: str = "",
            mcp_provider: McpProvider = None,
            max_rounds: Optional[int] = 15,
            **kwargs: Any
    ):
        super().__init__(
            llm=llm,
            retriever=retriever,
            tools=tools or [],
            system_message=system_message,
            **kwargs
        )
        self.mcp_provider = mcp_provider
        self.max_rounds = max_rounds

    def run(self, state: StateView) -> StateView:
        """Main entry point - process all incoming TaskPackets."""
        # Initialize MCP tools if available
        if self.mcp_provider:
            # Add MCP tools using the proper tool management API
            for tool in self.mcp_provider.get_tools():
                self.add_tool(tool)

        if self.tools:
            self._bind_tools(self.tools)

        # Process all incoming packets
        self.process_packets(state)
        return state

    def handle_task_packet(self, packet) -> None:
        """
        Process work using workspace conversation context.
        
        Flow:
        1. Build conversation context (workspace + system + task)
        2. Process with LLM
        3. Add agent result to workspace
        4. Route response based on task.should_respond
        """
        try:
            # Extract and mark task as processed
            task = packet.extract_task()
            task.mark_processed(self.uid)

            # 1. Build conversation context
            conversation_context = self._build_conversation_context(task)

            # 2. Process with LLM
            assistant_response = self._process_with_llm(conversation_context)

            # 3. Create agent result
            agent_result = self._create_agent_result(assistant_response)

            # 4. Add agent result to workspace
            if task.thread_id:
                self._add_agent_result_to_workspace(task.thread_id, agent_result)

            # 5. Route response using agent result
            self._route_response(task, agent_result, packet)

            print(f"CustomAgent {self.uid}: Processed task, added result to workspace")

        except Exception as e:
            print(f"CustomAgent {self.uid}: Error processing task: {e}")

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
            workspace_messages = self.get_recent_workspace_messages(task.thread_id, 20)
            context_messages.extend(deepcopy(workspace_messages))
        
        # 2. Add system message at the start if configured
        if self.system_message:
            system_msg = ChatMessage(role=Role.SYSTEM, content=self.system_message)
            if not context_messages or context_messages[0].role != Role.SYSTEM:
                context_messages.insert(0, system_msg)
            else:
                context_messages[0] = system_msg
        
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
        
        workspace_context = self.get_workspace_context(thread_id)
        
        if not workspace_context.results:
            return None
        
        # Focus on agent results - organized by agent name in order
        results_text = "PREVIOUS AGENT RESULTS:\n"
        for i, result in enumerate(workspace_context.results, 1):
            results_text += f"{i}. {result.agent_name}: {result.content}\n"
        
        return ChatMessage(role=Role.USER, content=results_text)

    def _process_with_llm(self, conversation_context: List[ChatMessage]) -> ChatMessage:
        """Process conversation with LLM (with optional tools)."""
        if self.tools:
            return self._execute_tool_cycle(
                initial_history=conversation_context,
                chat_function=self._chat,
                max_rounds=self.max_rounds
            )
        else:
            return self._chat(conversation_context)

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
        
        self.broadcast_task(response_task)

    def _execute_normal_broadcast(self, task: Task, agent_result: AgentResult) -> None:
        """Normal broadcast - continue work."""
        forked_task = task.fork(
            content="continue work",
            processed_by=self.uid,
            result=agent_result
        )
        self.broadcast_task(forked_task)

    def _create_agent_result(self, assistant_response: ChatMessage) -> AgentResult:
        """Create AgentResult from assistant response."""
        return AgentResult(
            content=assistant_response.content,
            agent_id=self.uid,
            agent_name=self.display_name
        )
    
    def _add_agent_result_to_workspace(self, thread_id: str, agent_result: AgentResult) -> None:
        """Add agent result to workspace."""
        self.add_result_to_workspace(thread_id, agent_result)

