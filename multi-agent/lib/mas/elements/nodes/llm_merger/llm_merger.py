import logging
from typing import List, Dict, Any, Optional, ClassVar
from copy import deepcopy
from global_utils.utils.logging_config import emit
from mas.elements.nodes.common.base_node import BaseNode
from mas.elements.nodes.common.capabilities.iem_capable import IEMCapableMixin
from mas.elements.nodes.common.capabilities.llm_capable import LlmCapableMixin
from mas.elements.nodes.common.capabilities.workload_capable import WorkloadCapableMixin
from mas.elements.nodes.common.workload import Task, AgentResult
from mas.graph.state.graph_state import Channel
from mas.graph.state.state_view import StateView
from mas.elements.llms.common.chat.message import ChatMessage, Role

logger = logging.getLogger(__name__)


class LLMMergerNode(WorkloadCapableMixin, IEMCapableMixin, LlmCapableMixin, BaseNode):
    """
    Enhanced LLM Merger with workspace integration.
    
    Features:
    - Merges latest task results from workspace
    - Uses workspace conversation history for context
    - Creates comprehensive merged responses
    - Broadcasts task with merged result
    """
    
    # Channel permissions
    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(
        self,
        *,
        llm: Any,
        system_message: str = "",
        **kwargs
    ):
        super().__init__(llm=llm, system_message=system_message, **kwargs)
        self._collected_results: Dict[str, List[AgentResult]] = {}  # thread_id -> results

    def run(self, state: StateView) -> StateView:
        """Process incoming TaskPackets, collect results, then merge and broadcast."""
        # First, collect all incoming task results
        self.process_packets(state)
        
        # Then, merge collected results for each thread
        merged_results_by_thread = self._merge_all_collected_results()
        
        # Finally, broadcast all merged results
        self._broadcast_all_merged_results(merged_results_by_thread)
        
        return state

    def handle_task_packet(self, packet) -> None:
        """
        Collect task results for later merging.
        
        This phase just collects - merging happens in _merge_all_collected_results()
        """
        try:
            # Extract task
            task = packet.extract_task()
            
            if not task.thread_id:
                emit(logger, logging.WARNING, "merge.thread_missing", node_uid=self.uid)
                return
            
            # Extract result from task (if it has one)
            if task.result:
                agent_result = task.result
                
                # Collect the result
                if task.thread_id not in self._collected_results:
                    self._collected_results[task.thread_id] = []
                
                self._collected_results[task.thread_id].append(agent_result)
                emit(
                    logger, logging.INFO, "merge.result_collected",
                    node_uid=self.uid, agent_name=agent_result.agent_name, thread_id=task.thread_id,
                )

        except Exception as e:
            emit(logger, logging.ERROR, "merge.collect_error", node_uid=self.uid, error=str(e))

    def _merge_all_collected_results(self) -> Dict[str, AgentResult]:
        """Merge all collected results for each thread. Returns merged results by thread_id."""
        merged_results_by_thread = {}
        threads_to_merge = list(self._collected_results.keys())
        
        for thread_id in threads_to_merge:
            results = self._collected_results.get(thread_id, [])
            if len(results) >= 2:  # Only merge if we have multiple results
                merged_result = self._merge_results_for_thread(thread_id, results)
                merged_results_by_thread[thread_id] = merged_result
                # Clean up after merging
                self._collected_results.pop(thread_id, None)
        
        return merged_results_by_thread

    def _broadcast_all_merged_results(self, merged_results_by_thread: Dict[str, AgentResult]) -> None:
        """Broadcast all merged results."""
        for thread_id, merged_result in merged_results_by_thread.items():
            try:
                self._broadcast_merged_task_for_thread(thread_id, merged_result)
                emit(
                    logger, logging.INFO, "merge.broadcast_completed",
                    node_uid=self.uid, thread_id=thread_id,
                )
            except Exception as e:
                emit(
                    logger, logging.ERROR, "merge.broadcast_error",
                    node_uid=self.uid, thread_id=thread_id, error=str(e),
                )

    def _merge_results_for_thread(self, thread_id: str, results: List[AgentResult]) -> AgentResult:
        """Complete merge logic for results - returns merged AgentResult."""
        # Get conversation history from workspace
        conversation_history = self.workspaces.get_conversation_history(thread_id)
        
        # Build conversation context for merging
        conversation_context = self._build_conversation_context_for_merge(conversation_history, results)
        
        # Process with LLM
        assistant_response = self._process_with_llm(conversation_context)
        
        # Create merged agent result
        agent_result = self._create_agent_result(assistant_response, results)
        
        # Add to workspace
        # self._add_agent_result_to_workspace(thread_id, agent_result)
        
        emit(
            logger, logging.INFO, "merge.completed",
            node_uid=self.uid, result_count=len(results), thread_id=thread_id,
        )

        return agent_result

    def _build_conversation_context_for_merge(self, conversation_history: List[ChatMessage], results: List[AgentResult]) -> List[ChatMessage]:
        """
        Build conversation context for merging:
        1. Get workspace conversation history
        2. Add system message if configured
        3. Add agent results context for merging
        4. Add merge instruction
        """
        context_messages = []
        
        # 1. Get workspace conversation history
        # if conversation_history:
        #     context_messages.extend(deepcopy(conversation_history[-10:]))  # Last 10 messages
        
        # 2. Add system message at the start if configured
        if self.system_message:
            system_msg = ChatMessage(role=Role.SYSTEM, content=self.system_message)
            if not context_messages or context_messages[0].role != Role.SYSTEM:
                context_messages.insert(0, system_msg)
            else:
                context_messages[0] = system_msg
        
        # 3. Add agent results context for merging
        results_context = self._build_results_merge_context(results)
        
        # 4. Add merge instruction
        user_msg = ChatMessage(role=Role.USER, content=f"{results_context}\n\nPlease merge the agent responses above into a single, comprehensive answer according to the system message.")
        context_messages.append(user_msg)
        
        return context_messages

    def _build_results_merge_context(self, results: List[AgentResult]) -> Optional[ChatMessage]:
        """Build context message with agent results to merge."""
        if not results:
            return None
        
        # Format results for merging
        merge_text = "AGENT RESPONSES TO MERGE:\n\n"
        for i, result in enumerate(results, 1):
            merge_text += f"**{result.agent_name}:**\n{result.content}\n\n"

        return merge_text

    def _process_with_llm(self, conversation_context: List[ChatMessage]) -> ChatMessage:
        """Process conversation with LLM."""
        return self.chat(conversation_context)

    def _create_agent_result(self, assistant_response: ChatMessage, original_results: List[AgentResult]) -> AgentResult:
        """Create AgentResult from merged response."""
        return AgentResult(
            content=assistant_response.content,
            agent_id=self.uid,
            agent_name=getattr(self, 'name', self.uid),
            artifacts=[],  # No artifact files produced by merger
            execution_metadata={
                "merged_count": len(original_results),
                "source_agents": [result.agent_name for result in original_results],
                "merge_type": "llm_merge"
            },
            metrics={
                "input_results": len(original_results),
                "input_length": sum(len(result.content) for result in original_results),
                "output_length": len(assistant_response.content)
            }
        )

    def _add_agent_result_to_workspace(self, thread_id: str, agent_result: AgentResult) -> None:
        """Add merged agent result to workspace."""
        self.workspaces.add_result(thread_id, agent_result)

    def _broadcast_merged_task_for_thread(self, thread_id: str, agent_result: AgentResult) -> None:
        """Broadcast merged task for a specific thread."""
        # Create a new task for the merged result
        merged_task = Task.create(
            content="Merged agent responses - continue work",
            thread_id=thread_id,
            created_by=self.uid
        )
        # Add the merged result to the task
        merged_task.result = agent_result
        
        self.broadcast_task(merged_task)

    def _broadcast_merged_task(self, original_task: Task, agent_result: AgentResult) -> None:
        """Broadcast task with merged result."""
        merged_task = original_task.fork(
            content="Merged agent responses - continue work",
            processed_by=self.uid,
            result=agent_result
        )
        
        self.broadcast_task(merged_task)

        emit(
            logger, logging.INFO, "merge.task_broadcasted",
            node_uid=self.uid, task_id=merged_task.task_id,
        )