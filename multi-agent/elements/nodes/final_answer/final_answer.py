from typing import List, ClassVar, Dict, Any
from elements.nodes.common.base_node import BaseNode
from elements.nodes.common.capabilities.iem_capable import IEMCapableMixin
from graph.state.graph_state import Channel
from graph.state.state_view import StateView
from elements.nodes.common.workload import AgentResult


class FinalAnswerNode(IEMCapableMixin, BaseNode):
    """
    Enhanced final node that collects task results and creates final output.
    
    Behavior:
    - Processes TaskPackets and extracts task results
    - Collects all AgentResults from tasks
    - Merges them into one final message
    - Promotes to messages and sets Channel.OUTPUT
    """
    
    READS: ClassVar[set[str]] = {Channel.MESSAGES}
    WRITES: ClassVar[set[str]] = {Channel.MESSAGES, Channel.OUTPUT}

    def __init__(self, *, name: str = "final_answer", **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self._collected_results: List[AgentResult] = []

    def run(self, state: StateView) -> StateView:
        """Process all incoming TaskPackets and create final answer."""
        # Process all incoming task packets
        self.process_packets(state)
        
        # Create final answer if we have collected results
        if self._collected_results:
            final_answer = self._merge_results()
            self.promote_to_messages(final_answer)
            state[Channel.OUTPUT] = final_answer
            
            # Clear collected results
            self._collected_results.clear()
        
        return state

    def handle_task_packet(self, packet) -> None:
        """
        Collect task results from TaskPackets.
        
        Extracts task from packet and collects AgentResult if present.
        """
        try:
            task = packet.extract_task()

            # Extract AgentResult from task if present
            if task.result and isinstance(task.result, AgentResult):
                self._collected_results.append(task.result)
                print(f"FinalAnswerNode {self.uid}: Collected result from {task.result.agent_name}")
                
        except Exception as e:
            print(f"FinalAnswerNode {self.uid}: Error collecting task result: {e}")

    def _merge_results(self) -> str:
        """
        Merge all collected AgentResult objects into one final message.
        
        Handles both successful results and errors, ensuring errors are
        clearly communicated to the user.
        """
        if not self._collected_results:
            return "I apologize, but I don't have any information to provide."
        
        # Single result case
        if len(self._collected_results) == 1:
            result = self._collected_results[0]
            content = result.content
            
            # Check if execution failed and append error if not already the same as content
            if not result.success and result.error:
                # Only skip if error exactly equals content (avoid duplication)
                if result.error.lower().strip() != content.lower().strip():
                    # If content is empty, use error as the main content
                    if not content or content.strip() == "":
                        content = f"ERROR: {result.error}"
                    else:
                        # Append error to existing content
                        content += f"\nERROR: {result.error}"
            
            return content
        
        # Multiple results case - separate successful results from errors
        successful_contents = []
        error_messages = []
        seen_success = set()
        seen_errors = set()
        
        for result in self._collected_results:
            content = result.content.strip()
            
            if result.success:
                # Collect successful results (deduplicate)
                if content and content not in seen_success:
                    successful_contents.append(content)
                    seen_success.add(content)
            else:
                # Collect error information
                error_info = content
                # Only append error if it's not exactly the same as content
                if result.error and result.error.lower().strip() != content.lower().strip():
                    error_info = f"{content}\nERROR: {result.error}" if content else f"ERROR: {result.error}"
                
                if error_info and error_info not in seen_errors:
                    error_messages.append(error_info)
                    seen_errors.add(error_info)
        
        # Build final message
        parts = []
        
        # Add successful results
        if successful_contents:
            if len(successful_contents) == 1:
                parts.append(successful_contents[0])
            else:
                parts.append("\n\n".join(successful_contents))
        
        # Add errors if any
        if error_messages:
            if successful_contents:
                # Separate errors from successful content
                parts.append("\n\nErrors encountered:")
            for error in error_messages:
                parts.append(error)
        
        # If nothing at all, return default message
        if not parts:
            return "I apologize, but I don't have any information to provide."
        
        return "\n\n".join(parts)