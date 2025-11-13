"""
Orchestrator node implementation.

This node coordinates work execution by:
1. Creating work plans from incoming tasks
2. Delegating work items to adjacent nodes
3. Monitoring responses and updating plan status
4. Synthesizing results when complete
"""

from typing import Optional, Any, List, ClassVar, Dict
from graph.state.state_view import StateView
from elements.llms.common.chat.message import ChatMessage, Role
from elements.tools.common.base_tool import BaseTool
from elements.nodes.common.base_node import BaseNode
from elements.nodes.common.capabilities.iem_capable import IEMCapableMixin
from elements.nodes.common.capabilities.llm_capable import LlmCapableMixin
from elements.nodes.common.capabilities.agent_capable import AgentCapableMixin
from elements.nodes.common.capabilities.workload_capable import WorkloadCapableMixin
from elements.nodes.common.agent import AgentConfig
from elements.nodes.common.agent.execution import ExecutionMode
from elements.nodes.common.agent.constants import StrategyType
from elements.nodes.common.agent.delegation_policy import DelegationPolicy, PermissiveDelegationPolicy
from elements.tools.common.execution.models import ExecutorConfig
from elements.nodes.common.workload import Task, WorkItemStatus, WorkItemKind, AgentResult
from .orchestrator_phase_provider import OrchestratorPhaseProvider
from .delegation_policy import OrchestratorDelegationPolicy
from .context import PendingCycle, CycleTrigger, CycleTriggerReason, OrchestratorContextBuilder, OrchestratorCycle
from elements.tools.builtin import (
    CreateOrUpdateWorkPlanTool,
    AssignWorkItemTool,
    MarkWorkItemStatusTool,
    ListAdjacentNodesTool,
    GetNodeCardTool,
    DelegateTaskTool
)


# ExecutionPhase import removed as it's not used in this file


class OrchestratorNode(
    WorkloadCapableMixin,
    IEMCapableMixin,
    AgentCapableMixin,
    LlmCapableMixin,
    BaseNode
):
    """
    Orchestrator node that plans and delegates work.
    
    Uses PlanAndExecuteStrategy to:
    - Decompose tasks into work items
    - Delegate to adjacent nodes based on capabilities
    - Monitor execution progress
    - Handle responses and update plans
    
    Key features:
    - Re-entrant: maintains state in workspace between visits
    - Flexible: can execute local work or delegate
    - Generic: any node can use orchestration with appropriate tools
    """

    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(
            self,
            *,
            llm: Any,
            tools: List[BaseTool] = None,
            system_message: str = "",
            max_rounds: int = 20,
            **kwargs: Any
    ):
        """
        Initialize orchestrator node.
        
        Args:
            llm: Language model for planning and decision making
            tools: Domain-specific tools (orchestration tools added automatically)
            system_message: Custom system message for the orchestrator
            max_rounds: Maximum planning/execution rounds
            **kwargs: Additional arguments for parent classes
        """
        # Store domain specialization separately for adjacency info
        self.domain_specialization = system_message

        super().__init__(
            llm=llm,
            system_message=self._build_complete_system_message(),
            **kwargs
        )
        self.max_rounds = max_rounds
        self.base_tools = tools or []
        
        # Orchestration cycles (one per thread, accumulates triggers)
        self._orchestration_cycles: Dict[str, OrchestratorCycle] = {}
        
        # Context builder for rich orchestration context (lazy init per thread)
        self._context_builders: Dict[str, OrchestratorContextBuilder] = {}

    def run(self, state: StateView) -> StateView:
        """
        Main orchestrator execution.
        
        Process:
        1. Handle incoming task packets (batch processing)
        2. Update work plan based on responses
        3. Run planning/execution if needed (once per thread)
        """
        # Process all incoming packets with batching
        self.process_packets_batched(state)

        return state

    def process_packets_batched(self, state: StateView) -> None:
        """
        Process all incoming packets with intelligent batching.
        
        Benefits of batching:
        1. Ingest all responses before planning - better decision making
        2. Accumulate all triggers per thread into one cycle
        3. Run orchestration cycle once per thread - reduces redundant cycles
        4. Better resource utilization and lower latency
        
        Key improvement: Multiple events for same thread automatically merge
        into one cycle via dict key uniqueness. LLM sees ALL triggers.
        """
        # Clear orchestration cycles from previous batch
        self._orchestration_cycles.clear()

        # Process all packets first (ingest phase - accumulates triggers)
        packets = list(self.inbox_packets())

        if not packets:
            return

        for i, packet in enumerate(packets):
            try:
                self.handle_task_packet(packet)
            finally:
                self.acknowledge(packet.id)

        # Execute one cycle per thread (handles all accumulated triggers)
        for cycle in self._orchestration_cycles.values():
            self._execute_cycle(cycle)

    def handle_task_packet(self, packet) -> None:
        """
        Handle task packet - designed for batch processing.
        
        This method is called by process_packets_batched() for each packet.
        It extracts and processes the task, updating the work plan as needed.
        Orchestration cycles are accumulated in self._orchestration_cycles.
        
        Args:
            packet: Task packet to handle
        """
        task = packet.extract_task()
        task.mark_processed(self.uid)

        if task.is_response():
            # This is a response to delegated work
            print(f"📨 [ORCH:{self.uid}] Processing RESPONSE packet")
            self._handle_task_response(task)
        else:
            # This is a new work request
            print(f"📬 [ORCH:{self.uid}] Processing NEW WORK packet")
            self._handle_new_work(task)

    def _record_trigger(
        self,
        thread_id: str,
        reason: CycleTriggerReason,
        changed_items: List[str] = None
    ) -> None:
        """
        Record a trigger event for a thread's orchestration cycle.
        
        Automatically creates cycle if it doesn't exist. This is the clean
        high-level API - callers don't need to think about cycle management.
        
        Design:
        - One cycle per thread (dict key ensures uniqueness)
        - Multiple triggers accumulate into same cycle
        - LLM sees all triggers for complete context awareness
        - No prioritization - LLM decides what matters
        
        Args:
            thread_id: Thread that needs orchestration
            reason: Why orchestration is needed
            changed_items: Work items affected by this trigger (optional)
        
        Example:
            # Two responses arrive for same thread in one batch:
            self._record_trigger(tid, RESPONSE_ARRIVED, ["jira_search"])
            self._record_trigger(tid, RESPONSE_ARRIVED, ["confluence_search"])
            # Result: One cycle with summary "2 responses arrived for: jira_search, confluence_search"
        """
        # Create cycle if doesn't exist (dict key ensures one per thread)
        if thread_id not in self._orchestration_cycles:
            self._orchestration_cycles[thread_id] = OrchestratorCycle(thread_id=thread_id)
        
        # Add this trigger event
        self._orchestration_cycles[thread_id].add_trigger(reason, changed_items)

    def _execute_cycle(self, cycle: OrchestratorCycle) -> None:
        """
        Execute one orchestration cycle.
        
        The cycle contains all accumulated triggers. The LLM sees
        complete context: "2 responses arrived + new request".
        
        Design:
        - Converts OrchestratorCycle to PendingCycle for backward compatibility
        - Prints clear summary of all triggers for debugging
        - Runs orchestration with full trigger context
        - Finalizes work if complete
        
        Args:
            cycle: OrchestratorCycle with accumulated triggers
        """
        print(f"\n{'='*80}")
        print(f"🎯 ORCHESTRATOR CYCLE START - Thread: {cycle.thread_id}")
        print(f"   Triggers: {cycle.get_trigger_summary()}")
        if cycle.all_changed_items:
            items_str = ', '.join(list(cycle.all_changed_items)[:5])
            if len(cycle.all_changed_items) > 5:
                items_str += f" (+{len(cycle.all_changed_items) - 5} more)"
            print(f"   Changed Items: {items_str}")
        print(f"{'='*80}\n")
        
        # Get current status
        status = self.workspaces.get_work_plan_status(cycle.thread_id, self.uid)
        
        # Resolve content for cycle (user message or guidance)
        content = self._resolve_cycle_content(cycle.thread_id)
        
        # Convert to PendingCycle for backward compatibility with strategy
        pending_cycle = cycle.to_pending_cycle()
        
        # Run orchestration (uses PendingCycle internally for now)
        self._run_orchestration_cycle(pending_cycle, content)
        
        # Re-check status after orchestration
        status = self.workspaces.get_work_plan_status(cycle.thread_id, self.uid)
        final_result = self._get_final_orchestration_result(cycle.thread_id)
        
        # Finalize if orchestrator produced a result AND:
        # 1. Work is complete (all items DONE/FAILED), OR
        # 2. Work incomplete but no delegation packets sent (error/partial result case)
        #
        # If we have outgoing packets, let the router handle routing to delegated nodes.
        # The graph will re-invoke us when responses arrive.
        if final_result:
            if status.is_complete or not self.has_outgoing_packets():
                self._finalize_completed_work(cycle.thread_id, final_result)

    def _handle_task_response(self, task: Task) -> Optional[str]:
        """
        Handle response from delegated work.
        
        Enhanced to handle child thread responses:
        - If response comes from child thread, updates parent thread's work plan
        - Stores response as context for LLM interpretation instead of auto-marking DONE
        - Only auto-marks for explicit success/error structures
        Returns thread_id if work plan was updated.
        """
        # Find correlation in task data
        correlation_task_id = task.correlation_task_id
        if not correlation_task_id:
            print(f"⚠️ [ORCH:{self.uid}] Response has no correlation_task_id - skipping")
            return None

        print(f"\n🔍 [ORCH:{self.uid}] Handling response:")
        print(f"   - correlation_task_id: {correlation_task_id}")
        print(f"   - from thread: {task.thread_id}")
        print(f"   - created_by: {task.created_by}")

        # Determine which thread to update (parent vs child thread handling)
        target_thread_id = self._resolve_target_thread_for_response(task)
        print(f"   - target_thread_id (resolved): {target_thread_id}")

        # Update work plan and workspace context
        service = self.workspaces

        # Extract response content for storage in work item
        response_content = ""
        if task.result:
            # Handle AgentResult properly (use .content field, not str())
            if isinstance(task.result, AgentResult):
                response_content = task.result.content
                
                # Append error information if present and execution failed
                # Only add error indicator if:
                # 1. Execution was not successful
                # 2. Error message exists
                # 3. Error is not exactly the same as content (avoid duplication)
                if not task.result.success and task.result.error:
                    # Only skip if error exactly equals content (case insensitive with strip)
                    if task.result.error.lower().strip() != response_content.lower().strip():
                        # If content is empty, use error as content
                        if not response_content.strip():
                            response_content = f"ERROR: {task.result.error}"
                        else:
                            # Append error to existing content
                            response_content += f"\nERROR: {task.result.error}"
            else:
                response_content = str(task.result)
        elif task.error:
            response_content = f"ERROR: {task.error}"
        elif task.content:
            response_content = task.content
        else:
            response_content = "Empty response"

        # NOTE: Responses are stored in DelegationExchange within WorkItem.result
        # They will be shown in the work plan snapshot automatically
        # No need to duplicate them in facts

        # Determine sender: task.created_by (properly set in Task.respond_success/error)
        # Fallback to assigned_uid if needed (defensive programming)
        from_uid = task.created_by
        if not from_uid:
            # Defensive fallback: find work item by delegation exchange
            plan = service.load_work_plan(target_thread_id, self.uid)
            if plan:
                for item in plan.items.values():
                    if item.result and item.result.delegations:
                        for exchange in item.result.delegations:
                            if exchange.task_id == correlation_task_id:
                                from_uid = item.assigned_uid or "unknown"
                                break
                        if from_uid and from_uid != "unknown":
                            break
            if not from_uid:
                from_uid = "unknown"
        
        # Store response in delegation exchange
        success = service.store_task_response_for_work_item(
            thread_id=target_thread_id,
            owner_uid=self.uid,
            correlation_task_id=correlation_task_id,
            response_content=response_content,
            from_uid=from_uid,
            result_data=task.result
        )
        
        if success:
            print(f"✅ [ORCH:{self.uid}] Response stored successfully - will trigger orchestration cycle")
            
            # Find which work items got responses
            changed_item_ids = self._find_items_for_task(target_thread_id, correlation_task_id)
            
            # Record trigger (automatically accumulates into existing cycle if one exists)
            self._record_trigger(
                thread_id=target_thread_id,
                reason=CycleTriggerReason.RESPONSE_ARRIVED,
                changed_items=changed_item_ids
            )
            print(f"✅ [ORCH:{self.uid}] Recorded response trigger for thread {target_thread_id[:8]}...")
        else:
            print(f"❌ [ORCH:{self.uid}] Failed to store response - NO orchestration cycle will run!")
            print(f"   This means delegation exchange not found")

        # Return thread_id if we updated the work plan
        return target_thread_id if success else None

    def _resolve_target_thread_for_response(self, task: Task) -> str:
        """
        Resolve the target thread for updating work plan from a response.
        
        Enhanced to handle nested thread hierarchies by using ThreadService.
        Walks up the thread hierarchy to find where this orchestrator's work plan lives.
        
        Args:
            task: Response task (may be from deeply nested child thread)
            
        Returns:
            Thread ID where this orchestrator's work plan is stored
        """
        response_thread_id = task.thread_id
        if not response_thread_id:
            # No thread context, use current orchestrator thread
            print(f"⚠️ [ORCH:{self.uid}] No thread_id in response - using default")
            return getattr(self, '_current_thread_id', None) or 'default'

        try:
            # Use thread service to find where THIS orchestrator's work plan is
            print(f"🔍 [ORCH:{self.uid}] Resolving work plan owner for thread {response_thread_id[:8]}...")
            target_thread_id = self.threads.find_work_plan_owner(response_thread_id, self.uid)
            if target_thread_id:
                if target_thread_id != response_thread_id:
                    print(f"   ↪️ Found in parent thread: {target_thread_id[:8]}...")
                else:
                    print(f"   ✓ Found in same thread: {target_thread_id[:8]}...")
            else:
                print(f"   ⚠️ Not found, falling back to response thread")
            return target_thread_id or response_thread_id
        except Exception as e:
            print(f"   ❌ Error during resolution: {e}")
            return response_thread_id

    def _find_items_for_task(self, thread_id: str, correlation_task_id: str) -> List[str]:
        """
        Find work item IDs that match the given correlation task ID.
        
        Args:
            thread_id: Thread containing the work plan
            correlation_task_id: Task ID to search for
        
        Returns:
            List of work item IDs that have delegations matching the task ID
        """
        changed_item_ids = []
        plan = self.workspaces.load_work_plan(thread_id, self.uid)
        
        if plan:
            for item in plan.items.values():
                if item.result and item.result.delegations:
                    for exchange in item.result.delegations:
                        if exchange.task_id == correlation_task_id:
                            changed_item_ids.append(item.id)
                            break  # Found match, move to next item
        
        return changed_item_ids

    def _handle_new_work(self, task: Task) -> None:
        """
        Handle new work request.
        
        Sets up thread and workspace context. Orchestration runs in batch processing phase.
        This ensures all packets are processed before orchestration begins.
        """
        # Processing new work request

        # Ensure we have a thread
        thread_id = task.thread_id
        if not thread_id:
            thread = self.threads.create_root_thread(
                title="Orchestrated Work",
                objective=task.content[:100],
                initiator=self.uid
            )
            thread_id = thread.thread_id
            # Update task with the new thread_id
            task.thread_id = thread_id

        # Record the new task for response tracking
        self.workspaces.add_task(thread_id, task)

        # Store current request for orchestration cycle (will be used once)
        self.workspaces.set_variable(thread_id, "_current_request", task.content)
        self.workspaces.set_variable(thread_id, "orchestrator_uid", self.uid)
        self.workspaces.set_variable(thread_id, "original_task_id", task.task_id)

        # Record trigger (automatically accumulates into existing cycle if one exists)
        self._record_trigger(
            thread_id=thread_id,
            reason=CycleTriggerReason.NEW_REQUEST,
            changed_items=[]  # No specific items for new requests
        )

        # ✅ Orchestration will run in the batch processing loop
        # This ensures:
        # 1. Consistent behavior: 1 cycle per thread (new work OR responses)
        # 2. Better batching: All packets processed before orchestration
        # 3. Correct context: LLM sees all available information
        # 4. Trigger accumulation: Multiple events for same thread merge into one cycle

    def _resolve_cycle_content(self, thread_id: str) -> str:
        """
        Get the original user request for reference across all cycles.
        
        With focused prompts now handling cycle-specific instructions,
        this method preserves the original request for context.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            Original user request or empty string
        """
        # Return the original request (don't clear it - keep for all cycles)
        return self.workspaces.get_variable(thread_id, "_current_request", "") or ""

    def _run_orchestration_cycle(self, cycle: PendingCycle, content: str) -> AgentResult:
        """
        Run a planning and execution cycle.
        
        Uses PlanAndExecuteStrategy with orchestration tools.
        Returns AgentResult with the orchestration outcome.
        
        Args:
            cycle: PendingCycle containing thread_id, reason, and changed_items
            content: Orchestration content (user request or guidance message)
        """
        print(f"\n{'='*80}")
        print(f"🎯 ORCHESTRATOR CYCLE START - Thread: {cycle.thread_id}")
        print(f"   Trigger: {cycle.reason.value}")
        if cycle.changed_items:
            print(f"   Changed items: {', '.join(cycle.changed_items)}")
        print(f"{'='*80}")

        # Build conversation context
        messages = self._build_context_messages(cycle.thread_id, content)

        # Build domain tools only (provider will build built-ins)
        tools = list(self.base_tools)

        # Apply orchestrator's delegation policy to filter adjacent nodes
        delegation_policy = self._create_delegation_policy()
        all_adjacent = self.get_adjacent_nodes()
        delegable_adjacent = delegation_policy.filter_delegable_nodes(all_adjacent)

        # Get or create context builder (needed by phase provider for recording transitions)
        context_builder = self._get_or_create_context_builder(cycle.thread_id)

        # Create orchestrator phase provider with clean SOLID dependencies
        # NOTE: We pass filtered nodes - provider doesn't know about delegation policy
        phase_provider = OrchestratorPhaseProvider(
            domain_tools=tools,  # These are the domain tools this orchestrator can use
            get_adjacent_nodes=lambda: delegable_adjacent,  # Pass filtered nodes!
            send_task=self.send_task,  # Inject IEM sender for delegation tool
            node_uid=self.uid,
            thread_id=cycle.thread_id,
            get_workload_service=self.get_workload_service,  # Clean dependency injection
            context_builder=context_builder  # For recording phase transitions
            # Uses default PhaseIterationLimits (all phases = 10 iterations)
        )
        
        # Build rich orchestrator context with trigger information
        trigger = CycleTrigger(
            reason=cycle.reason,
            description=f"Orchestration cycle: {cycle.reason.value}",
            new_user_message=content if cycle.reason == CycleTriggerReason.NEW_REQUEST else None,
            response_task_ids=[],  # Task IDs not needed currently
            changed_items=cycle.changed_items
        )
        orch_context = context_builder.build_context(
            trigger=trigger,
            phase_state=phase_provider.get_phase_context()
        )
        
        # Store context for phase provider to access via dynamic context messages
        phase_provider._current_orch_context = orch_context
        
        # Store user request for focused prompts
        phase_provider.set_current_user_request(content)

        # Create strategy with unified provider
        strategy = self.create_strategy(
            tools=tools,
            strategy_type=StrategyType.PLAN_AND_EXECUTE.value,
            system_message=self._build_complete_system_message(),
            max_steps=self.max_rounds,
            phase_provider=phase_provider
        )

        # Configure execution
        config = AgentConfig(
            execution_mode=ExecutionMode.AUTO,
            executor_config=ExecutorConfig.create_balanced()
        )

        # Ensure all phase provider tools are available to the executor
        all_phase_tools = set()
        for phase_name in phase_provider.get_supported_phases():
            phase_tools = phase_provider.get_tools_for_phase(phase_name)
            all_phase_tools.update(phase_tools)

        # Add all phase tools to strategy's tool registry so they're available to executor
        for tool in all_phase_tools:
            strategy.all_tools[tool.name] = tool

        # Run agent
        result = self.run_agent(
            messages=messages,
            strategy=strategy,
            config=config
        )

        # Create AgentResult directly with the information we need
        agent_result = AgentResult(
            content=str(result.get("output", "")),
            agent_id=self.uid,
            agent_name=self.display_name,
            success=result.get("success", False),
            error=result.get("error"),
            reasoning=result.get("reasoning", ""),
            execution_metadata=result.get("metadata", {}),
            artifacts=result.get("artifacts", []) if isinstance(result.get("artifacts"), list) else [],
            metrics=result.get("metrics", {})
        )

        # Add agent result to workspace
        self.workspaces.add_result(cycle.thread_id, agent_result)

        # Display work plan snapshot
        self._print_work_plan_snapshot(cycle.thread_id)

        print(f"{'='*80}")
        print(f"✅ ORCHESTRATOR CYCLE END - Thread: {cycle.thread_id}")
        print(f"{'='*80}\n")

        return agent_result

    def _build_context_messages(self, thread_id: str, content: str) -> List[ChatMessage]:
        """
        Build STATIC context messages (set once per orchestration cycle).
        
        With the focused prompt system, this now provides minimal static context:
        - Conversation history: Public user messages from graph state
        - Original user request: For reference across all cycles
        
        Phase-specific context is now handled by the phase provider:
        - Adjacent nodes: Added per phase by get_phase_static_context()
        - Work plan: Added dynamically by get_dynamic_context_messages()
        - Focused prompts: Added by build_focused_prompt()
        
        Returns:
            List of static ChatMessage objects
        """
        messages = []

        # Conversation history (public messages from graph state)
        conversation_history = self.workspaces.get_conversation_history(thread_id)
        if conversation_history:
            messages.extend(conversation_history)

        # Original user request (if exists) - preserved for all cycles
        if content:
            messages.append(ChatMessage(
                role=Role.USER,
                content=content
            ))

        return messages

    def _build_adjacency_summary(self) -> str:
        """
        Build a comprehensive summary of delegable adjacent nodes.
        
        Respects orchestrator's delegation policy - only shows nodes that
        can receive delegated work (excludes finalization path nodes).
        
        Provides enough detail for informed delegation decisions.
        Shows description and raw skills data without parsing.
        
        Returns:
            Formatted string with node info and skills
        """
        try:
            # Get orchestrator's delegation policy
            delegation_policy = self._create_delegation_policy()
            
            # Get all adjacent nodes and filter by policy
            all_adjacent = self.get_adjacent_nodes()
            delegable_nodes = delegation_policy.filter_delegable_nodes(all_adjacent)
            
            if not delegable_nodes:
                return "No delegable nodes available."

            lines = ["Available nodes for delegation:\n"]
            
            for uid, card in delegable_nodes.items():
                lines.append(f"## {card.name} (uid: {uid})")
                lines.append(f"   Type: {card.type_key}")
                lines.append(f"   Description: {card.description}")
                
                # Skills - Show raw data as-is
                if card.skills:
                    lines.append(f"   Skills: {card.skills}")
                
                lines.append("")  # Blank line between nodes
            
            return "\n".join(lines)
            
        except Exception as e:
            print(f"⚠️ [ORCHESTRATOR] Error building adjacency summary: {e}")
            # Fallback: show all adjacent nodes
            adjacent_nodes = self.get_adjacent_nodes()
            if not adjacent_nodes:
                return "No adjacent nodes available."
            
            lines = ["Available nodes (fallback - all adjacent):\n"]
            for uid, card in adjacent_nodes.items():
                lines.append(f"## {card.name} (uid: {uid})")
                lines.append("")
            
            return "\n".join(lines)

    # NOTE: _build_workspace_summary and _build_plan_snapshot moved to
    # OrchestratorPhaseProvider as _build_workspace_summary_internal and
    # _build_plan_snapshot_internal to support dynamic context refresh

    def _get_final_orchestration_result(self, thread_id: str) -> Optional[AgentResult]:
        """
        Get the final orchestration result from the completed synthesis phase.
        
        The synthesis phase should have:
        1. Called workplan.summarize tool
        2. Returned AgentFinish with the LLM's summary
        3. Created an AgentResult with that summary as content
        
        We retrieve the most recent successful result from this orchestrator.
        """
        results = self.workspaces.get_results(thread_id)
        
        # Find the most recent result from this orchestrator
        for result in reversed(results):
            if result.agent_id == self.uid:
                return result
        
        return None

    def _finalize_completed_work(self, thread_id: str, agent_result: AgentResult) -> None:
        """
        Finalize completed orchestration work.
        
        Args:
            thread_id: Thread ID
            agent_result: Final orchestration result to route
        
        Note:
            No idempotency check needed - caller (batch processing) already
            ensures this is called once per thread per batch, and only when
            status.is_complete is True. Multi-request flows naturally
            work because the work plan status is checked fresh each time.
        """
        # Check if response is required
        original_task = self._get_original_task(thread_id)

        if original_task and original_task.should_respond:
            self._send_response(thread_id, agent_result, original_task)
        else:
            self._route_to_finalizer(thread_id, agent_result)

    def _send_response(self, thread_id: str, agent_result: AgentResult, original_task: Task) -> None:
        """Send response using original task info."""
        response_task = Task.respond_success(
            original_task=original_task,
            result=agent_result,
            processed_by=self.uid
        )

        destination = original_task.response_to or original_task.created_by
        if destination:
            self.send_task(destination, response_task)
        else:
            self._route_to_finalizer(thread_id, agent_result)

    def _route_to_finalizer(self, thread_id: str, agent_result: AgentResult) -> None:
        """Route result to nearest finalizer node."""
        try:
            topology = getattr(self.get_context(), "topology", None)
            if not topology or not topology.has_finalizer_path():
                return

            next_hop_uid = topology.get_nearest_finalizer_node()
            if not next_hop_uid:
                return

            # Create task with agent result
            task = Task(
                content="Orchestration synthesis result",
                result=agent_result,
                should_respond=False,
                thread_id=thread_id,
                created_by=self.uid,
                processed_by=self.uid
            )

            self.send_task(next_hop_uid, task)
        except Exception as e:
            pass

    def _print_work_plan_snapshot(self, thread_id: str) -> None:
        """Print a compact snapshot of the current work plan."""
        service = self.workspaces
        plan = service.load_work_plan(thread_id, self.uid)
        
        if not plan or not plan.items:
            return
        
        status = service.get_work_plan_status(thread_id, self.uid)
        
        print(f"\n{'='*80}")
        print(f"📋 WORK PLAN FINAL ({status.total_items} items)")
        print(f"{'='*80}")
        
        # Compact status line
        status_parts = []
        if status.pending_items > 0:
            status_parts.append(f"⏸️ {status.pending_items} Pending")
        if status.in_progress_items > 0:
            status_parts.append(f"🔄 {status.in_progress_items} In Progress")
        if status.done_items > 0:
            status_parts.append(f"✅ {status.done_items} Done")
        if status.failed_items > 0:
            status_parts.append(f"❌ {status.failed_items} Failed")
        print(f"Status: {' | '.join(status_parts)}")
        
        if status.blocked_items > 0 or status.waiting_items > 0:
            extras = []
            if status.blocked_items > 0:
                extras.append(f"🚫 {status.blocked_items} Blocked")
            if status.waiting_items > 0:
                extras.append(f"⏳ {status.waiting_items} Waiting")
            print(f"        {' | '.join(extras)}")
        
        # Show ALL items compactly
        for status in [WorkItemStatus.PENDING, WorkItemStatus.IN_PROGRESS, WorkItemStatus.DONE, WorkItemStatus.FAILED]:
            items = plan.get_items_by_status(status)
            if not items:
                continue
            
            for item in items:
                status_icon = {
                    WorkItemStatus.PENDING: "⏸️",
                    WorkItemStatus.IN_PROGRESS: "🔄",
                    WorkItemStatus.DONE: "✅",
                    WorkItemStatus.FAILED: "❌"
                }.get(status, "❓")
                
                # Compact one-line per item
                kind = "local" if item.kind == WorkItemKind.LOCAL else f"→{item.assigned_uid}"
                item_line = f"{status_icon} {item.title[:50]}"
                if len(item.title) > 50:
                    item_line += "..."
                item_line += f" ({kind})"
                
                # Add dependency info
                if item.dependencies:
                    completed_deps = plan.get_completed_item_ids()
                    dep_status = []
                    for dep_id in item.dependencies:
                        dep_item = plan.items.get(dep_id)
                        if dep_item:
                            dep_title = dep_item.title[:20] + "..." if len(dep_item.title) > 20 else dep_item.title
                            if dep_id in completed_deps:
                                dep_status.append(f"✓{dep_title}")
                            else:
                                dep_status.append(f"✗{dep_title}")
                        else:
                            # Fallback if dependency not found
                            dep_status.append(f"?{dep_id}")
                    item_line += f" [depends on: {', '.join(dep_status)}]"
                
                # Show delegation history if present
                if item.result and item.result.delegations:
                    delegation_count = len(item.result.delegations)
                    pending_count = sum(1 for ex in item.result.delegations if ex.is_pending)
                    unprocessed_count = sum(1 for ex in item.result.delegations if ex.needs_attention)
                    
                    if delegation_count == 1:
                        # Single exchange - show query and response
                        ex = item.result.delegations[0]
                        query_preview = ex.query[:80].replace('\n', ' ')
                        item_line += f"\n      📤 Q: {query_preview}{'...' if len(ex.query) > 80 else ''}"
                        
                        if ex.is_pending:
                            item_line += f"\n      ⏳ Waiting for response from {ex.delegated_to}"
                        elif ex.needs_attention:
                            resp_preview = ex.response_content[:100].replace('\n', ' ')
                            item_line += f"\n      🔔 A: {resp_preview}{'...' if len(ex.response_content) > 100 else ''}"
                        else:
                            resp_preview = ex.response_content[:100].replace('\n', ' ')
                            item_line += f"\n      ✓ A: {resp_preview}{'...' if len(ex.response_content) > 100 else ''}"
                    else:
                        # Multiple exchanges - show summary and each turn
                        item_line += f"\n      💬 {delegation_count} turns ({unprocessed_count}🔔 need attention, {pending_count}⏳ pending)"
                        for i, ex in enumerate(item.result.delegations):
                            query_preview = ex.query[:60].replace('\n', ' ')
                            item_line += f"\n      [{i}] Q: {query_preview}{'...' if len(ex.query) > 60 else ''}"
                            
                            if ex.is_pending:
                                item_line += f"\n          ⏳ Waiting for {ex.delegated_to}"
                            elif ex.needs_attention:
                                resp_preview = ex.response_content[:80].replace('\n', ' ')
                                item_line += f"\n          🔔 A: {resp_preview}{'...' if len(ex.response_content) > 80 else ''}"
                            else:
                                resp_preview = ex.response_content[:80].replace('\n', ' ')
                                item_line += f"\n          ✓ A: {resp_preview}{'...' if len(ex.response_content) > 80 else ''}"
                
                print(f"   {item_line}")
        
        print(f"{'='*80}")

    @staticmethod
    def _get_orchestrator_behavior_message() -> str:
        """Compact orchestrator behavior instructions."""
        return """You are an orchestrator agent that coordinates work execution.

Core responsibilities:
1. Create detailed work plans with dependencies
2. Delegate work to appropriate adjacent nodes
3. Monitor progress and interpret responses
4. Synthesize results when complete

Key principles:
- Break tasks into manageable work items
- Match work to node capabilities  
- Track delegated work via correlation IDs
- Interpret responses carefully before marking status
- Respect retry limits (check item retry_count vs max_retries)
- Always explain reasoning for status changes"""

    def _build_complete_system_message(self) -> str:
        """Build complete system message combining behavior + specialization."""
        behavior_msg = self._get_orchestrator_behavior_message()

        if self.domain_specialization:
            # User provided domain specialization
            return f"{behavior_msg}\n\nDomain Specialization:\n{self.domain_specialization}"
        else:
            # No specialization provided
            return behavior_msg
    
    def _get_or_create_context_builder(self, thread_id: str) -> OrchestratorContextBuilder:
        """
        Lazy initialization of context builder per thread.
        
        Context builder maintains state (progress tracking, history) across cycles,
        so we create one per thread and reuse it.
        
        Args:
            thread_id: Thread identifier
        
        Returns:
            OrchestratorContextBuilder for this thread
        """
        if thread_id not in self._context_builders:
            self._context_builders[thread_id] = OrchestratorContextBuilder(
                get_workload_service=lambda: self.workspaces,
                node_uid=self.uid,
                thread_id=thread_id
            )
        return self._context_builders[thread_id]

    def _create_delegation_policy(self) -> DelegationPolicy:
        """
        Create orchestrator's delegation policy.
        
        ORCHESTRATOR'S CHOICE: Exclude finalization path nodes from delegation.
        
        This is where the orchestrator makes the decision about which nodes
        can receive delegated work. The policy encapsulates the business rule:
        "Don't delegate to finalization path nodes because I route to them
        programmatically when work completes."
        
        Returns:
            OrchestratorDelegationPolicy or fallback to permissive policy
        """
        try:
            # Get context and topology
            context = self.get_context()
            topology = context.topology if context else None
            adjacent_nodes = self.get_adjacent_nodes()
            
            # Create orchestrator-specific policy
            return OrchestratorDelegationPolicy(
                topology=topology,
                adjacent_nodes=adjacent_nodes
            )
            
        except Exception as e:
            print(f"⚠️ [ORCHESTRATOR] Error creating delegation policy: {e}")
            print(f"⚠️ [ORCHESTRATOR] Falling back to permissive policy (all nodes delegable)")
            
            # Fallback: Allow all adjacent nodes
            return PermissiveDelegationPolicy(self.get_adjacent_nodes())

    def _get_original_task(self, thread_id: str) -> Optional[Task]:
        """
        Get the original task that started this orchestration thread.
        
        Args:
            thread_id: Thread ID to get original task for
            
        Returns:
            Original task or None if not found
        """
        try:
            # Get all tasks from workspace
            tasks = self.workspaces.get_tasks(thread_id)
            if tasks:
                # Return the first task (chronologically first)
                return tasks[0]

            # Fallback: try to get from workspace variable
            original_task_id = self.workspaces.get_variable(thread_id, "original_task_id")
            if original_task_id:
                # Would need a task registry to lookup by ID, for now return None
                pass

            return None
        except Exception as e:
            return None
