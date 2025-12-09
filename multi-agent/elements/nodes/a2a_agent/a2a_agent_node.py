"""
A2A Agent Node - Delegates work to remote agent via A2A protocol
"""

from typing import Optional, Any, List, ClassVar, Dict
from copy import deepcopy
from pydantic import HttpUrl
from a2a.types import AgentCard
from graph.state.state_view import StateView
from elements.llms.common.chat.message import ChatMessage, Role
from elements.nodes.common.base_node import BaseNode
from elements.nodes.common.capabilities.iem_capable import IEMCapableMixin
from elements.nodes.common.capabilities.retriever_capable import RetrieverCapableMixin
from elements.nodes.common.capabilities.workload_capable import WorkloadCapableMixin
from elements.nodes.common.workload import Task, AgentResult
from elements.providers.a2a_client import A2AProvider


class A2AAgentNode(
    WorkloadCapableMixin,
    IEMCapableMixin,
    RetrieverCapableMixin,
    BaseNode
):
    """
    A2A Agent Node - Delegates work to remote agent via A2A protocol.
    
    SOLID Design:
    - Single Responsibility: Context building + remote delegation + routing
    - Open/Closed: Extensible via retriever and workspace services
    - Liskov Substitution: Can replace CustomAgent in workflows
    - Interface Segregation: Only uses needed mixins (no LLM/Agent)
    - Dependency Inversion: Creates A2AProvider internally from config
    
    Architecture:
    - Creates A2A Provider from base_url and agent_card
    - Builds context from workspace + retriever (like CustomAgent)
    - No local LLM/tools/strategy (remote agent handles execution)
    - Same routing logic as CustomAgent (should_respond)
    - Tracks tasks/results in workspace
    - Supports streaming: streams llm_token events in real-time
    
    Context Flow:
    1. Get workspace conversation history
    2. Build agent results context
    3. Add current task with retriever augmentation
    4. Send complete context to remote agent (streaming or non-streaming)
    5. Get response and route appropriately
    """

    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(
            self,
            *,
            base_url: HttpUrl,
            agent_card: Optional[AgentCard] = None,
            bearer_token: Optional[str] = None,
            retriever: Any = None,
            **kwargs: Any
    ):
        """
        Initialize A2A Agent Node.
        
        Args:
            base_url: A2A agent endpoint URL
            agent_card: Optional pre-fetched agent card
            bearer_token: Optional bearer token for authentication
            retriever: Optional retriever for context augmentation
        """
        super().__init__(
            retriever=retriever,
            **kwargs
        )

        # Build headers from bearer_token if provided
        headers = None
        if bearer_token:
            headers = {"Authorization": f"Bearer {bearer_token}"}

        # Create A2A provider from config
        self.a2a_provider = A2AProvider.create_sync(
            base_url=base_url,
            agent_card=agent_card,
            headers=headers
        )

        # Sensible defaults for context and polling
        self._max_context_messages = 20
        self._wait_for_completion = True
        self._poll_interval = 0.5
        self._max_poll_attempts = 60

    def run(self, state: StateView) -> StateView:
        """Main entry point - process all incoming TaskPackets."""
        self.process_packets(state)
        return state

    # ========== TASK PROCESSING ==========

    def handle_task_packet(self, packet) -> None:
        """
        Process task by delegating to remote agent via A2A.
        
        SOLID Architecture Flow:
        1. Extract and record task in workspace
        2. Build conversation context (workspace + retriever)
        3. Send to remote agent via A2A Provider (streaming or non-streaming)
        4. Create agent result from response
        5. Add result to workspace
        6. Route response based on task.should_respond
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

            # 2. Delegate to remote agent (handles streaming automatically)
            remote_response, metadata = self._delegate_to_remote_agent(
                conversation_context,
                task
            )

            # 3. Create agent result from remote response
            agent_result = self._create_agent_result(
                remote_response,
                metadata
            )

            # 4. Add agent result to workspace
            if task.thread_id:
                self.workspaces.add_result(task.thread_id, agent_result)

            # 5. Route response
            self._route_response(task, agent_result, packet)

            print(f"A2AAgent {self.uid}: Delegated task to remote agent, received response")

        except Exception as e:
            print(f"A2AAgent {self.uid}: Error processing task: {e}")
            # Create error agent result
            error_result = AgentResult(
                content=f"Error delegating to remote agent: {str(e)}",
                agent_id=self.uid,
                agent_name=self.display_name,
                success=False,
                error=str(e)
            )
            if task.thread_id:
                self.workspaces.add_result(task.thread_id, error_result)
            self._route_response(task, error_result, packet)

    # ========== CONTEXT BUILDING ==========

    def _build_conversation_context(self, task: Task) -> List[ChatMessage]:
        """
        Build conversation context for remote agent.
        
        Similar to CustomAgent but simpler:
        1. Get workspace conversation history
        2. Add agent results context
        3. Add current task with retriever context
        
        No system message (remote agent has its own configuration).
        
        Args:
            task: Current task to process
            
        Returns:
            List of ChatMessage for remote agent
        """
        context_messages = []

        # 1. Get workspace conversation history
        if task.thread_id:
            workspace_messages = self.workspaces.get_recent_messages(
                task.thread_id,
                self._max_context_messages
            )
            context_messages.extend(deepcopy(workspace_messages))

        # 2. Add agent results context
        if task.thread_id:
            agent_results_context = self._build_agent_results_context(task.thread_id)
            if agent_results_context:
                context_messages.append(agent_results_context)

        # 3. Add current task with retriever context if available
        user_msg = ChatMessage(role=Role.USER, content=task.content)
        if self.retriever:
            user_msg = self.augment_with_context(user_msg)
        context_messages.append(user_msg)

        return context_messages

    def _build_agent_results_context(self, thread_id: str) -> Optional[ChatMessage]:
        """
        Build agent results context from workspace.
        
        Same pattern as CustomAgent for consistency.
        """
        if not thread_id:
            return None

        workspace_results = self.workspaces.get_results(thread_id)

        if not workspace_results:
            return None

        # Format agent results
        results_text = "PREVIOUS AGENT RESULTS:\n"
        for i, result in enumerate(workspace_results, 1):
            results_text += f"{i}. {result.agent_name}: {result.content}\n"

        return ChatMessage(role=Role.USER, content=results_text)

    # ========== REMOTE AGENT DELEGATION ==========

    def _delegate_to_remote_agent(
            self,
            context_messages: List[ChatMessage],
            task: Task
    ) -> tuple[ChatMessage, Dict[str, Any]]:
        """
        Delegate task to remote agent via A2A Provider.
        
        Handles both streaming and non-streaming modes:
        - Checks if node is streaming AND remote agent supports streaming
        - Streaming: Uses stream_message_sync() and streams llm_token events
        - Non-streaming: Uses send_message_sync() for direct response
        
        Remote agent streaming support is checked via agent_card.capabilities.streaming
        
        Combines all context messages into single message for remote agent.
        Uses task.thread_id as context_id for multi-turn support.
        
        Args:
            context_messages: Full conversation context
            task: Current task (used for thread_id as context_id)
            
        Returns:
            Tuple of (response ChatMessage, metadata dict)
        """
        # Combine context into single message for remote agent
        combined_content = self._combine_context_messages(context_messages)

        message_to_send = ChatMessage(
            role=Role.USER,
            content=combined_content
        )

        # Choose delegation method based on streaming capabilities
        # Both node AND remote agent must support streaming
        if self._should_use_streaming():
            return self._delegate_with_streaming(message_to_send, task)
        else:
            return self._delegate_without_streaming(message_to_send, task)

    def _should_use_streaming(self) -> bool:
        """
        Determine if streaming should be used for delegation.
        
        Streaming is used only if BOTH conditions are met:
        1. Node is in streaming mode (self.is_streaming())
        2. Remote agent supports streaming (agent_card.capabilities.streaming)
        
        SOLID Design:
        - Single Responsibility: Check streaming capability
        - Encapsulates capability check logic
        
        Returns:
            True if streaming should be used, False otherwise
        """
        # Check if node is in streaming mode
        if not self.is_streaming():
            return False

        # Check if remote agent supports streaming
        agent_card = self.a2a_provider.agent_card
        if not agent_card:
            # No agent card means we can't verify capabilities
            # Fall back to non-streaming for safety
            return False

        # Check capabilities field
        if not hasattr(agent_card, 'capabilities') or not agent_card.capabilities:
            # No capabilities field - assume no streaming support
            return False

        # Check streaming capability
        streaming_supported = getattr(agent_card.capabilities, 'streaming', False)

        if not streaming_supported:
            # Log that we're falling back to non-streaming
            print(
                f"A2AAgent {self.uid}: Node is streaming but remote agent doesn't support streaming. Using non-streaming mode.")

        return streaming_supported

    def _delegate_without_streaming(
            self,
            message: ChatMessage,
            task: Task
    ) -> tuple[ChatMessage, Dict[str, Any]]:
        """
        Delegate to remote agent without streaming (direct response).
        
        Uses send_message_sync() with polling for completion.
        
        Args:
            message: Message to send
            task: Current task for context
            
        Returns:
            Tuple of (response ChatMessage, metadata dict)
        """
        response, metadata = self.a2a_provider.send_message_sync(
            message=message,
            context_id=task.thread_id,
            wait_for_completion=self._wait_for_completion,
            poll_interval=self._poll_interval,
            max_poll_attempts=self._max_poll_attempts
        )

        return response, metadata

    def _delegate_with_streaming(
            self,
            message: ChatMessage,
            task: Task
    ) -> tuple[ChatMessage, Dict[str, Any]]:
        """
        Delegate to remote agent with streaming support.
        
        SOLID Design:
        - Single Responsibility: Handle streaming delegation and token forwarding
        - Follows same pattern as LlmCapableMixin._stream_chat()
        
        Prerequisites:
        - Node must be in streaming mode (self.is_streaming())
        - Remote agent must support streaming (verified by _should_use_streaming())
        
        Process:
        1. Stream message to remote agent
        2. Accumulate chunks into final content
        3. Stream each chunk as llm_token event (for UI updates)
        4. Extract metadata from final state
        5. Return complete message
        
        Pattern matches LlmCapableMixin._stream_chat():
        - Accumulate text from chunks
        - Call self._stream() for each token
        - Return final message
        
        Args:
            message: Message to send
            task: Current task for context
            
        Returns:
            Tuple of (final ChatMessage, metadata dict)
        """
        accumulated_content = ""

        # Stream chunks from remote agent
        for chunk in self.a2a_provider.stream_message_sync(
                message=message,
                context_id=task.thread_id
        ):
            # Accumulate content from chunk
            if chunk.content:
                accumulated_content += chunk.content

                # Stream token event (same pattern as LlmCapableMixin)
                # This allows UI to display tokens in real-time
                self._stream({
                    "type": "llm_token",
                    "chunk": chunk.content
                })

        # Create final message from accumulated content
        final_message = ChatMessage(
            role=Role.ASSISTANT,
            content=accumulated_content
        )

        # Create metadata for streaming response
        # Note: A2A streaming doesn't provide task_id/status in chunks
        # We assume success if streaming completed without error
        metadata = {
            "task_id": None,  # Not available in streaming mode
            "context_id": task.thread_id,
            "status": "completed",
            "status_message": "Streaming completed successfully"
        }

        return final_message, metadata

    def _combine_context_messages(self, messages: List[ChatMessage]) -> str:
        """
        Combine context messages into single formatted string.
        
        Formats conversation history in a clear way for remote agent.
        Remote agent sees the full context as one message.
        """
        if not messages:
            return ""

        # If only one message (the current task), return it directly
        if len(messages) == 1:
            return messages[0].content

        # Format conversation history
        parts = ["CONVERSATION CONTEXT:\n"]

        for i, msg in enumerate(messages[:-1], 1):  # All but last message
            role_label = msg.role.value.upper()
            parts.append(f"[{role_label}]: {msg.content}\n")

        # Add current task separately
        parts.append("\nCURRENT TASK:")
        parts.append(messages[-1].content)

        return "\n".join(parts)

    # ========== RESULT HANDLING ==========

    def _create_agent_result(
            self,
            response: ChatMessage,
            metadata: Dict[str, Any]
    ) -> AgentResult:
        """
        Create AgentResult from remote agent response.
        
        Args:
            response: ChatMessage from remote agent
            metadata: A2A metadata (task_id, status, etc.)
            
        Returns:
            AgentResult with remote agent response
        """
        # Check if remote task succeeded
        task_status = metadata.get("status", "unknown")
        success = task_status in ["completed", "success"]

        return AgentResult(
            content=response.content,
            agent_id=self.uid,
            agent_name=self.display_name,
            success=success,
            error=None if success else metadata.get("status_message"),
            reasoning="",  # Remote agent reasoning not exposed
            execution_metadata={
                "remote_agent": True,
                "a2a_task_id": metadata.get("task_id"),
                "a2a_context_id": metadata.get("context_id"),
                "a2a_status": task_status,
                "a2a_status_message": metadata.get("status_message"),
                "streaming": self.is_streaming()
            },
            metrics={}
        )

    # ========== RESPONSE ROUTING ==========

    def _route_response(
            self,
            task: Task,
            agent_result: AgentResult,
            original_packet
    ) -> None:
        """
        Route response based on task.should_respond.
        
        Same routing logic as CustomAgent:
        - If should_respond: Check if requester is adjacent
          - Adjacent: Direct response
          - Not adjacent: Broadcast with response request
        - Else: Normal broadcast
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

    def _get_adjacent_nodes_uids(self) -> set[str]:
        """Get adjacent node UIDs from network topology."""
        adjacent_nodes = self.get_adjacent_nodes()
        return set(adjacent_nodes.keys())

    def _execute_direct_response(
            self,
            task: Task,
            agent_result: AgentResult,
            original_packet
    ) -> None:
        """Send direct response to requester - finished work."""
        response_task = Task.respond_success(
            original_task=task,
            result=agent_result,
            processed_by=self.uid
        )
        self.reply_task(original_packet, response_task)

    def _execute_broadcast_with_response(
            self,
            task: Task,
            agent_result: AgentResult
    ) -> None:
        """Broadcast with response request - finished work."""
        response_task = task.fork(
            content="finished work",
            processed_by=self.uid,
            result=agent_result
        )
        response_task.should_respond = True
        response_task.response_to = task.response_to
        response_task.correlation_task_id = task.task_id

        self.broadcast_task(response_task)

    def _execute_normal_broadcast(
            self,
            task: Task,
            agent_result: AgentResult
    ) -> None:
        """Normal broadcast - continue work."""
        forked_task = task.fork(
            content="continue work",
            processed_by=self.uid,
            result=agent_result
        )
        self.broadcast_task(forked_task)
