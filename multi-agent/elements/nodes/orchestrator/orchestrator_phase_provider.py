"""
Orchestrator-specific phase provider implementation.

Uses clean Pydantic models and enums to define orchestrator phases professionally.
"""

from enum import Enum
from typing import List, Callable, Any, Optional
from elements.tools.common.base_tool import BaseTool
from elements.llms.common.chat.message import ChatMessage
from elements.nodes.common.agent.phases.unified_phase_provider import PhaseProvider
from elements.nodes.common.agent.phases.phase_definition import PhaseSystem, PhaseDefinition
from elements.nodes.common.agent.phases.phase_protocols import PhaseState, create_phase_state
from elements.nodes.common.agent.phases.models import PhaseValidationContext
from .phases.models import PhaseIterationLimits, PhaseIterationState
from .phases.validators import (
    AllocationValidator, PlanningValidator, ExecutionValidator,
    MonitoringValidator, SynthesisValidator
)
from .context import OrchestratorContextBuilder
from .context.models import CycleTriggerReason

# Built-in orchestration tools
from elements.tools.builtin.workplan.create_or_update import CreateOrUpdateWorkPlanTool
from elements.tools.builtin.workplan.assign_item import AssignWorkItemTool
from elements.tools.builtin.workplan.mark_status import MarkWorkItemStatusTool
from elements.tools.builtin.workplan.record_execution import RecordLocalExecutionTool
from elements.tools.builtin.delegation.delegate_task import DelegateTaskTool
from elements.tools.builtin.topology.list_adjacent import ListAdjacentNodesTool
from elements.tools.builtin.topology.get_node_card import GetNodeCardTool
from elements.tools.builtin.time import GetCurrentTimeTool


class OrchestratorPhase(Enum):
    """
    Orchestrator execution phases.

    Defines the complete orchestrator workflow in execution order.
    """
    PLANNING = "planning"
    ALLOCATION = "allocation"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    SYNTHESIS = "synthesis"

    @classmethod
    def get_execution_order(cls) -> List['OrchestratorPhase']:
        """Get phases in their natural execution order."""
        return [
            cls.PLANNING,
            cls.ALLOCATION,
            cls.EXECUTION,
            cls.MONITORING,
            cls.SYNTHESIS
        ]

    @classmethod
    def get_phase_names(cls) -> List[str]:
        """Get phase names as strings in execution order."""
        return [phase.value for phase in cls.get_execution_order()]


class OrchestratorPhaseProvider(PhaseProvider):
    """
    Professional orchestrator phase provider using clean Pydantic models and enums.

    Defines orchestrator phases with proper separation of concerns:
    - Domain tools come from init parameter (orchestrator's capabilities)
    - Orchestration tools are built-in (work plan, delegation, etc.)
    - Phases are defined using enums (no hardcoding)
    - Iteration limits managed via Pydantic models in PhaseDefinition

    DESIGN NOTE:
    The phase provider receives already-filtered adjacent nodes from the orchestrator.
    It does NOT know about delegation policies - that's the orchestrator's responsibility.
    This ensures clean separation: orchestrator decides WHO is adjacent, provider uses it.
    """

    def __init__(
            self,
            domain_tools: List[BaseTool],
            get_adjacent_nodes: Callable[[], Any],
            send_task: Callable[..., Any],
            node_uid: str,
            thread_id: str,
            get_workload_service: Callable[[], Any],
            context_builder: Optional[OrchestratorContextBuilder] = None,
            iteration_limits: Optional[PhaseIterationLimits] = None
    ):
        """
        Initialize orchestrator phase provider.

        Args:
            domain_tools: Domain-specific tools that this orchestrator can use
            get_adjacent_nodes: Function to get adjacent nodes (already filtered by orchestrator)
            send_task: Function to send IEM tasks (dst_uid, task) -> packet_id
            node_uid: Node identifier
            thread_id: Current thread ID for context
            get_workload_service: Function to get workload service
            context_builder: OrchestratorContextBuilder for recording phase transitions (optional)
            iteration_limits: Custom iteration limits configuration (optional)

        Note:
            get_adjacent_nodes should return nodes that the orchestrator has already
            filtered according to its delegation policy. The provider doesn't apply
            any additional filtering - it trusts what the orchestrator gives it.
        """
        self._get_adjacent_nodes = get_adjacent_nodes
        self._send_task = send_task
        self._node_uid = node_uid
        self._thread_id = thread_id
        self._domain_tools = domain_tools
        self._get_workload_service = get_workload_service
        self._context_builder = context_builder

        # Configure iteration limits using Pydantic model
        self._iteration_limits = iteration_limits or PhaseIterationLimits()

        # Track iteration state using Pydantic model
        self._iteration_state = PhaseIterationState()

        # Private: Cascade safety limit
        self._max_cascade_transitions = 10

        # Orchestrator context (set by orchestrator_node before each cycle)
        self._current_orch_context = None

        # Track current user request for focused prompts
        self._current_user_request: Optional[str] = None

        super().__init__(domain_tools)  # This calls _create_phase_system()

    def _get_current_thread(self):
        """Get current thread for delegation context."""
        workload_service = self._get_workload_service()
        return workload_service.get_thread(self._thread_id)

    def set_current_user_request(self, request: str) -> None:
        """Set the current user request for building focused prompts."""
        self._current_user_request = request

    def _increment_phase_iteration(self, phase_name: str) -> None:
        """
        Private: Increment iteration count for the given phase.

        Args:
            phase_name: Name of the phase to increment
        """
        self._iteration_state = self._iteration_state.increment(phase_name)
        current = self._iteration_state.get_count(phase_name)
        limit = self._iteration_limits.get_limit(phase_name)

    def _is_phase_limit_exceeded(self, phase_name: str) -> bool:
        """
        Private: Check if phase iteration limit is exceeded.

        Args:
            phase_name: Name of the phase to check

        Returns:
            True if limit exceeded, False otherwise
        """
        return self._iteration_state.is_exceeded(phase_name, self._iteration_limits)

    def _reset_phase_iteration(self, phase_name: str) -> None:
        """
        Private: Reset iteration count for the given phase.

        Args:
            phase_name: Name of the phase to reset
        """
        old_count = self._iteration_state.get_count(phase_name)
        self._iteration_state = self._iteration_state.reset(phase_name)

    def _create_phase_system(self) -> PhaseSystem:
        """
        Create the orchestrator phase system.

        Tool separation:
        - Built-in tools: Initialize here (workplan, delegation, topology, etc.)
        - Domain tools: Already initialized, passed from constructor (execution tools)

        Adjacent Nodes:
        - Phase provider receives already-filtered adjacent nodes from orchestrator
        - No policy logic here - orchestrator has already applied its delegation policy
        - Provider simply uses the nodes it's given
        """
        # Clean SOLID dependencies
        get_tid = lambda: self._thread_id
        get_uid = lambda: self._node_uid

        # Get adjacent nodes (already filtered by orchestrator)
        adjacent_nodes = self._get_adjacent_nodes()

        # Initialize built-in orchestration tools with clean dependencies
        create_plan_tool = CreateOrUpdateWorkPlanTool(
            get_thread_id=get_tid,
            get_owner_uid=get_uid,
            get_workload_service=self._get_workload_service
        )
        assign_tool = AssignWorkItemTool(
            get_thread_id=get_tid,
            get_owner_uid=get_uid,
            get_workload_service=self._get_workload_service
        )
        mark_status_tool = MarkWorkItemStatusTool(
            get_thread_id=get_tid,
            get_owner_uid=get_uid,
            get_workload_service=self._get_workload_service
        )
        record_execution_tool = RecordLocalExecutionTool(
            get_thread_id=get_tid,
            get_owner_uid=get_uid,
            get_workload_service=self._get_workload_service
        )
        # Note: SummarizeWorkPlanTool removed - work plan is now provided via dynamic context

        # Tools use the adjacent nodes provided by orchestrator (already filtered)
        delegate_tool = DelegateTaskTool(
            send_task=self._send_task,
            get_owner_uid=get_uid,
            get_current_thread=lambda: self._get_current_thread(),
            get_thread_service=lambda: self._get_workload_service().get_thread_service(),
            get_workspace_service=lambda: self._get_workload_service().get_workspace_service(),
            check_adjacency=lambda uid: uid in adjacent_nodes  # Simple membership check
        )
        list_nodes_tool = ListAdjacentNodesTool(
            get_adjacent_nodes=self._get_adjacent_nodes  # Uses orchestrator-provided nodes
        )
        get_node_card_tool = GetNodeCardTool(
            get_adjacent_nodes=self._get_adjacent_nodes  # Uses orchestrator-provided nodes
        )
        time_tool = GetCurrentTimeTool()

        # Create phase definitions directly in execution order (no interim configs)
        domain_tools_list = list(self._domain_tools)

        # Create validators
        planning_validator = PlanningValidator()
        allocation_validator = AllocationValidator()
        execution_validator = ExecutionValidator()
        monitoring_validator = MonitoringValidator()
        synthesis_validator = SynthesisValidator()

        planning_phase = PhaseDefinition(
            name=OrchestratorPhase.PLANNING.value,
            description="Create or update work plan with dependencies and task breakdown",
            tools=[create_plan_tool, list_nodes_tool, get_node_card_tool, time_tool],
            guidance=(
                "PHASE: PLANNING - Create or update work plan based on new request.\n\n"
                "YOUR ROLE IN THIS PHASE:\n"
                "- ONLY create the work plan structure (items, dependencies, assignments)\n"
                "- DO NOT execute work or delegate tasks\n"
                "- DO NOT try to use delegation tools (not available in this phase)\n"
                "- Delegation happens automatically in ALLOCATION phase (next phase)\n\n"

                "MULTI-REQUEST WORKFLOW (Same Thread):\n"
                "1. FIRST: Check 'Current Work Plan' section above to see if work plan already exists\n\n"
                "2. IF NO PLAN EXISTS:\n"
                "   Create comprehensive work plan using CreateOrUpdateWorkPlanTool:\n"
                "   - Break down request into specific, actionable work items\n"
                "   - Give each item a descriptive snake_case ID (e.g., 'research_trends', 'analyze_data')\n"
                "   - Write clear title and detailed description for each item\n"
                "   - Identify dependencies between items (which must complete before others)\n"
                "   - Determine execution type:\n"
                "     * LOCAL: Tasks you can execute yourself (with or without domain tools)\n"
                "     * REMOTE: Tasks requiring specialized agents (check with ListAdjacentNodesTool)\n"
                "   - For REMOTE items: Set assigned_uid to target agent, but DO NOT delegate yet\n"
                "   - Write comprehensive summary describing overall goal\n"
                "   - Start simple: 3-5 well-defined items better than 20 vague ones\n\n"
                "3. IF PLAN EXISTS:\n"
                "   - Review existing items (DONE/IN_PROGRESS/PENDING/FAILED)\n"
                "   - Understand what work has been completed\n"
                "   - Determine how new request relates to existing work\n"
                "   - Update plan accordingly (add new items, update descriptions, adjust dependencies)\n\n"
                "HANDLING EXISTING WORK PLANS:\n"
                "- NEW independent work → Add new items to existing plan\n"
                "- FOLLOW-UP on completed work → Add items that depend on DONE items\n"
                "- CLARIFICATION → May not need new items, just check existing results\n"
                "- CONTINUATION → Add items that build on IN_PROGRESS work\n"
                "- RE-DO failed work → Can reuse failed item IDs with updated approach\n\n"
                "WORK ITEM BEST PRACTICES:\n"
                "- Dependencies: Use item IDs in dependencies list (e.g., dependencies: ['research_trends'])\n"
                "- Specificity: 'Research top 5 AI trends in 2024' > 'Research AI'\n"
                "- Granularity: Break complex tasks into smaller steps\n"
                "- Logical order: Arrange items in execution sequence\n\n"

                "WORK ITEM STRATEGY:\n"
                "- Consider information completeness requirements:\n"
                "  * If comprehensive coverage is valuable: Create work items for multiple agents\n"
                "  * Each agent searches their respective data domain in parallel\n"
                "  * Aggregate results to ensure no relevant information is missed\n"
                "- Consider specificity of target:\n"
                "  * If action requires specific capability: Create focused work item for that agent\n"
                "  * If information could exist in multiple sources: Query broadly\n\n"

                "PHASE SEPARATION (IMPORTANT):\n"
                "- PLANNING phase (you are here): Create work plan structure only\n"
                "- ALLOCATION phase (next): Delegate REMOTE items to agents\n"
                "- EXECUTION phase: Execute LOCAL items\n"
                "- MONITORING phase: Review responses and results\n"
                "- SYNTHESIS phase: Create final answer\n\n"

                "CRITICAL CONSTRAINTS:\n"
                "- DO NOT try to delegate tasks (happens in ALLOCATION phase)\n"
                "- DO NOT try to execute work (happens in EXECUTION phase)\n"
                "- ONLY use CreateOrUpdateWorkPlanTool, ListAdjacentNodesTool, GetNodeCardTool\n"
                "- Once plan is created, phase will automatically transition to ALLOCATION"
            ),
            max_iterations=self._iteration_limits.planning
        )
        planning_phase.add_validator(planning_validator)

        allocation_phase = PhaseDefinition(
            name=OrchestratorPhase.ALLOCATION.value,
            description="Assign work items to appropriate nodes and delegate tasks",
            tools=[assign_tool, delegate_tool, list_nodes_tool, get_node_card_tool, create_plan_tool, time_tool],
            guidance=(
                "PHASE: ALLOCATION - Assign REMOTE work items to appropriate agents and delegate tasks.\n\n"
                "WORKFLOW:\n"
                "1. Review work plan for PENDING items with kind=REMOTE\n"
                "2. For each REMOTE item:\n"
                "   a. Review 'Available Agents' section to see agent capabilities\n"
                "   b. Choose best agent based on task requirements and capabilities\n"
                "   c. Use AssignWorkItemTool to assign item to chosen agent\n"
                "   d. Use DelegateTaskTool to send task (MUST include work_item_id)\n"
                "3. Skip LOCAL items (handled in EXECUTION phase)\n\n"
                "ALLOCATION STRATEGY:\n"
                "- Review 'Available Agents for Delegation' section above\n"
                "- Use GetNodeCardTool only if you need more detailed capabilities\n"
                "- Match work item requirements to agent capabilities\n"
                "- For information gathering: Parallel delegation across relevant agents\n"
                "- For specific actions: Direct delegation to capable agent\n\n"
                "BEST PRACTICES:\n"
                "- All agents can be queried in parallel - leverage this for comprehensive results\n"
                "- Check agent is in adjacency list (can't delegate to non-adjacent nodes)\n"
                "- One work item → One agent (no multi-assignment yet)\n\n"
                "DELEGATION COORDINATION:\n"
                "- CRITICAL: Always assign BEFORE delegate\n"
                "  1. AssignWorkItemTool(item_id, agent_uid) - marks assigned_uid\n"
                "  2. DelegateTaskTool(dst_uid, content, work_item_id) - creates child thread\n"
                "- MUST include work_item_id in DelegateTaskTool (enables response tracking)\n"
                "- Child thread created automatically (context for agent)\n"
                "- Correlation ID tracked for linking responses back to work item\n\n"
                "WHAT TO DELEGATE:\n"
                "- Only REMOTE items (kind=REMOTE)\n"
                "- Only PENDING or ready items (dependencies satisfied)\n"
                "- Include clear instructions in task content\n"
                "- Include context and expected deliverables\n\n"
                "IMPORTANT:\n"
                "- Don't execute LOCAL items here - wait for EXECUTION phase\n"
                "- Don't skip REMOTE items - all must be delegated\n"
                "- Incomplete delegation → Infinite loop risk (validator catches this)\n"
                "- Status changes: PENDING → IN_PROGRESS (remote) after delegation"
            ),
            max_iterations=self._iteration_limits.allocation
        )
        allocation_phase.add_validator(allocation_validator)

        execution_phase = PhaseDefinition(
            name=OrchestratorPhase.EXECUTION.value,
            description="Execute local work items using domain capabilities",
            tools=[record_execution_tool, time_tool] + domain_tools_list,
            guidance=(
                "PHASE: EXECUTION - Execute LOCAL work items directly.\n\n"

                "🎯 WORKFLOW FOR EACH LOCAL ITEM:\n"
                "1. Identify PENDING items with kind=LOCAL\n"
                "2. Check dependencies are satisfied\n"
                "3. Execute the work:\n"
                "   - Use domain tools if appropriate for the task\n"
                "   - OR execute directly using your reasoning and knowledge\n"
                "4. Record your execution:\n"
                "   RecordLocalExecutionTool(item_id='...', outcome='...')\n"
                "   → This automatically marks the item as DONE\n\n"

                "🔧 EXECUTION APPROACHES:\n"
                "WITH TOOLS: Use domain tools for specialized tasks (search, analysis, etc.)\n"
                "WITHOUT TOOLS: Execute directly using your reasoning and knowledge\n\n"

                "📝 RECORDING OUTCOMES:\n"
                "Write naturally - describe execution as a complete narrative:\n"
                "- What approach you took and why\n"
                "- What steps or tools you used\n"
                "- What results, findings, or outputs you produced\n"
                "- Any insights or conclusions you reached\n\n"

                "⚡ ONE-STEP PROCESS:\n"
                "RecordLocalExecutionTool does it all:\n"
                "  ✓ Captures what you did\n"
                "  ✓ Automatically marks as DONE\n"
                "  ✓ Makes results available for SYNTHESIS\n\n"

                "🔗 DEPENDENCIES:\n"
                "- Only execute items whose dependencies are DONE\n"
                "- Blocked items will appear in next iteration once dependencies complete\n"
                "- You may need multiple iterations if dependencies resolve sequentially\n\n"

                "⚠️  DO NOT:\n"
                "- Mark items as IN_PROGRESS (not needed for local execution)\n"
                "- Use MarkWorkItemStatusTool (not available in this phase)\n"
                "- Attempt to execute REMOTE items (use ALLOCATION → MONITORING)\n"
            ),
            max_iterations=self._iteration_limits.execution
        )
        execution_phase.add_validator(execution_validator)

        monitoring_phase = PhaseDefinition(
            name=OrchestratorPhase.MONITORING.value,
            description="Interpret responses and execution results, manage work item lifecycle",
            tools=[mark_status_tool, delegate_tool, list_nodes_tool, time_tool],
            guidance=(
                "PHASE: MONITORING - Review completed work (both remote and local) and decide next actions.\n\n"
                "YOUR ROLE:\n"
                "- Review responses from REMOTE delegated agents\n"
                "- Review execution results from LOCAL work items\n"
                "- Evaluate quality and completeness of all work\n"
                "- Decide: accept, request follow-up, or mark failed\n"
                "- YOU CANNOT EXECUTE WORK YOURSELF (no direct searches, queries, or analysis)\n\n"

                "WHAT YOU MONITOR:\n"
                "1. REMOTE items: Responses from delegated agents\n"
                "   - Check work plan for items with new responses (needs your interpretation)\n"
                "   - Agent responses appear in work item conversation history\n"
                "   - Thread context preserved across multiple follow-ups\n\n"

                "2. LOCAL items: Execution results from local work\n"
                "   - Check work plan for LOCAL items marked DONE or IN_PROGRESS\n"
                "   - Review execution notes and outcomes\n"
                "   - Validate results meet requirements\n\n"

                "DECISION FRAMEWORK FOR REMOTE ITEMS:\n"
                "For each REMOTE item with a response:\n\n"

                "1. ACCEPT if response fully satisfies requirements:\n"
                "   - Complete information provided\n"
                "   - Quality is acceptable\n"
                "   - No clarification needed\n"
                "   Action: Use MarkWorkItemStatusTool to mark item as done\n\n"

                "2. REQUEST FOLLOW-UP if response needs improvement:\n"
                "   - Response is vague or incomplete\n"
                "   - Need specific clarification or detail\n"
                "   - Agent offered additional information\n"
                "   - Quality could be better\n"
                "   Action: Use DelegateTaskTool to continue conversation with same agent\n"
                "   Note: Agent sees full conversation history automatically\n\n"

                "3. MARK FAILED if work is impossible:\n"
                "   - Agent tried multiple times without success\n"
                "   - Required resources or data don't exist\n"
                "   - Task is fundamentally not achievable\n"
                "   Action: Use MarkWorkItemStatusTool to mark item as failed\n\n"

                "DECISION FRAMEWORK FOR LOCAL ITEMS:\n"
                "For each LOCAL item that was executed:\n\n"

                "1. VERIFY execution results:\n"
                "   - Read execution notes and outcomes\n"
                "   - Confirm results meet task requirements\n"
                "   - Check for errors or incomplete work\n\n"

                "2. ACCEPT if execution successful:\n"
                "   - Results satisfy requirements\n"
                "   - Execution completed without errors\n"
                "   - Item already marked DONE by execution phase (no action needed)\n\n"

                "FOLLOW-UP BEST PRACTICES (REMOTE ITEMS):\n"
                "- Ask specific questions, not generic requests\n"
                "- Reference specific parts of the response when seeking clarity\n"
                "- Use follow-ups for iterative quality improvement\n"
                "- Same work_item_id preserves conversation thread\n"
                "- Multiple follow-ups are acceptable for quality\n"
                "- Do NOT accept incomplete responses to move faster\n"
                "- Do NOT mark failed when you just need more information\n\n"

                "CRITICAL CONSTRAINTS:\n"
                "- You are a COORDINATOR, not an EXECUTOR\n"
                "- You cannot perform searches, queries, or domain operations\n"
                "- To get more information: Re-delegate to appropriate agent\n"
                "- Do NOT execute tools meant for specialized agents\n"
                "- Do NOT mark REMOTE items as IN_PROGRESS (they are already delegated)\n"
                "- Do NOT mark LOCAL items as IN_PROGRESS (they execute in EXECUTION phase)\n\n"

                "QUALITY STANDARDS:\n"
                "- Quality over speed: Multiple follow-ups better than poor results\n"
                "- Mark done only when truly satisfied\n"
                "- Clear, actionable, complete work deserves acceptance\n"
                "- Vague, incomplete, or ambiguous work deserves follow-up or rejection"
            ),
            max_iterations=self._iteration_limits.monitoring
        )
        monitoring_phase.add_validator(monitoring_validator)

        synthesis_phase = PhaseDefinition(
            name=OrchestratorPhase.SYNTHESIS.value,
            description="Create comprehensive answer from all work items regardless of status",
            tools=[],  # NO TOOLS - synthesis only produces text responses
            guidance=(
                "PHASE: SYNTHESIS - Answer user's question using ALL available information.\n\n"

                "⚠️  HOW TO DELIVER YOUR ANSWER:\n"
                "Your response must be DIRECT TEXT - no tool calls, no actions.\n"
                "You are in read-only analysis mode. Just think and write your answer.\n"
                "Your text response IS the final answer delivered to the user.\n\n"

                "YOUR MISSION:\n"
                "Extract value from EVERY work item regardless of status.\n"
                "Provide the most complete answer possible based on what was learned.\n\n"

                "SYNTHESIS WORKFLOW:\n"
                "1. Review ENTIRE work plan - all items, all statuses\n"
                "2. Extract information from each status:\n"
                "   - DONE: Use results and findings\n"
                "   - FAILED: What was learned? Why did it fail?\n"
                "   - IN_PROGRESS: Any partial results in conversation?\n"
                "   - PENDING: Why blocked? Still relevant?\n"
                "3. Construct answer that addresses user's original question\n\n"

                "ANSWER STRUCTURE:\n"
                "1. DIRECT ANSWER: Start with answer to user's question\n"
                "   - Use all available information\n"
                "   - Be specific and actionable\n\n"

                "2. SUPPORTING DETAILS:\n"
                "   - Key findings from completed work\n"
                "   - Insights from failures (negative results are valuable)\n"
                "   - Partial information if relevant\n\n"

                "3. TRANSPARENCY:\n"
                "   - State confidence level (complete/partial/uncertain)\n"
                "   - Explain limitations or gaps if any\n"
                "   - Note what worked and what didn't\n\n"

                "HANDLING DIFFERENT SCENARIOS:\n"
                "- All DONE: Comprehensive answer with full confidence\n"
                "- Mix DONE/FAILED: Answer using successes, explain what failures revealed\n"
                "- Mostly FAILED: Extract value from failures (error messages, patterns) and use reasoning\n"
                "- Still IN_PROGRESS: Use completed and partial results, note what's pending\n\n"

                "CRITICAL PRINCIPLES:\n"
                "- ALWAYS provide an answer, even if incomplete\n"
                "- Extract value from failures (they contain information)\n"
                "- Focus on answering the question, not reporting status\n"
                "- Be honest about confidence and completeness\n"
                "- Do NOT skip failed items - they tell us something\n"
                "- Do NOT apologize - deliver value from what exists\n"
                "- NO TOOL CALLS - your text response IS the final answer"
            ),
            max_iterations=self._iteration_limits.synthesis
        )
        synthesis_phase.add_validator(synthesis_validator)

        phases = [
            planning_phase,
            allocation_phase,
            execution_phase,
            monitoring_phase,
            synthesis_phase
        ]

        # Create the complete phase system
        return PhaseSystem(
            name="orchestrator",
            description="Complete orchestrator workflow: " + " → ".join(OrchestratorPhase.get_phase_names()),
            phases=phases
        )

    def get_phase_context(self) -> PhaseState:
        """
        Get orchestrator-specific phase context.

        Provides rich context including work plan status and node information.
        """
        try:
            workload_service = self._get_workload_service()
            workspace_service = workload_service.get_workspace_service()
            work_plan_status = workspace_service.get_work_plan_status(self._thread_id, self._node_uid)

            # No conversion needed - WorkPlanStatus is now the single source of truth
            return create_phase_state(
                work_plan_status=work_plan_status,
                thread_id=self._thread_id,
                node_uid=self._node_uid
            )

        except Exception as e:
            # Return minimal context on error
            return create_phase_state(
                thread_id=self._thread_id,
                node_uid=self._node_uid
            )

    def get_initial_phase(self) -> str:
        """
        Get the initial phase for orchestration.

        Orchestrator always starts with planning.
        """
        return OrchestratorPhase.PLANNING.value

    def is_terminal_phase(self, phase_name: str) -> bool:
        """
        Check if phase is terminal.

        SYNTHESIS is the only terminal phase - represents workflow completion.
        Other phases may stay in themselves temporarily (processing, waiting)
        but will eventually transition.

        Args:
            phase_name: Phase name to check

        Returns:
            True if terminal (SYNTHESIS), False otherwise
        """
        return phase_name == OrchestratorPhase.SYNTHESIS.value

    def update_phase(
            self,
            current_phase: str,
            observations: List[Any]
    ) -> str:
        """
        Update phase with orchestrator's internal cascade logic.

        PRIVATE IMPLEMENTATION:
        - Increment iteration
        - Cascade until stable
        - Reset iteration on transition
        - Safety limits and cycle detection

        Strategy doesn't see any of this - just gets final phase.

        Args:
            current_phase: Current phase name
            observations: Recent observations from execution

        Returns:
            Final stable phase name
        """
        # Increment iteration for current phase
        self._increment_phase_iteration(current_phase)

        # Get initial context
        context = self.get_phase_context()

        # Private cascade logic (internal to orchestrator)
        final_phase = self._cascade_to_stable(current_phase, context, observations)

        # Reset iteration if phase changed
        if final_phase != current_phase:
            self._reset_phase_iteration(current_phase)
            # Print work plan after phase change
            self._print_work_plan_after_phase(final_phase)

        return final_phase

    def can_finish_now(self, current_phase: str) -> bool:
        """
        Determine if orchestrator should finish THIS CYCLE now.

        Clean separation of concerns:
        - This method handles CYCLE finishing (waiting for external events)
        - Phase transitions handle moving between phases (EXECUTION → SYNTHESIS)

        Return True only when:
        1. In SYNTHESIS phase (terminal, work done)
        2. Waiting for responses with no actionable work (pause until responses arrive)

        Do NOT return True just because work is complete - let phase transition
        logic handle EXECUTION → SYNTHESIS. Only finish cycle when in SYNTHESIS.

        Args:
            current_phase: Current phase name

        Returns:
            True if should finish cycle, False if more work needed
        """
        try:
            # Get work plan status
            context = self.get_phase_context()
            if not context or not context.work_plan_status:
                # No work plan - allow finish (defensive)
                return True

            status = context.work_plan_status

            # Case 1: In SYNTHESIS phase (terminal - can always finish)
            try:
                current_phase_enum = OrchestratorPhase(current_phase)
                if current_phase_enum == OrchestratorPhase.SYNTHESIS:
                    return True
            except ValueError:
                pass  # Unknown phase, fall through

            # Case 2: Waiting for responses with no actionable work (router flow)
            # Allow finish if:
            # - We have remote items waiting (already delegated)
            # - No responses to process (has_responses=False)
            # - No local work ready to execute (has_local_ready=False)
            # - No remote work ready to delegate (has_remote_ready=False)
            #
            # This means we've delegated everything we can and are waiting
            # for the router to re-invoke us when responses arrive.
            if status.has_remote_waiting:
                if (not status.has_responses
                        and not status.has_local_ready
                        and not status.has_remote_ready):
                    return True

            # Otherwise, keep working (including transitioning to SYNTHESIS if complete)
            return False

        except Exception as e:
            # On error, allow finish (defensive - don't block forever)
            return True

    def _cascade_to_stable(
            self,
            current_phase: str,
            context: PhaseState,
            observations: List[Any]
    ) -> str:
        """
        Private: Cascade transitions until reaching stable phase.

        Keeps calling decide_next_phase() until phase is stable.
        Includes safety mechanisms: max transitions, cycle detection, validation.

        Args:
            current_phase: Starting phase
            context: Current phase state
            observations: Recent observations

        Returns:
            Final stable phase
        """
        transitions = [current_phase]
        visited = {current_phase}
        current = current_phase

        for cascade_num in range(self._max_cascade_transitions):
            # Decide next phase
            next_phase = self.decide_next_phase(current, context, observations)

            # Stable - done
            if next_phase == current:
                self._log_cascade(transitions, cascade_num, 'stable')
                return current

            # Validate transition
            if not self.validate_transition(current, next_phase):
                self._log_cascade(transitions, cascade_num, 'invalid')
                return current

            # Cycle detection - force to SYNTHESIS
            if next_phase in visited:
                self._log_cascade(transitions + [next_phase], cascade_num, 'cycle')
                return OrchestratorPhase.SYNTHESIS.value

            # Continue cascade
            transitions.append(next_phase)
            visited.add(next_phase)

            # Record phase transition in context builder if available
            if self._context_builder:
                self._context_builder.record_phase_transition(
                    from_phase=current,
                    to_phase=next_phase,
                    reason=f"Cascade transition (started from {transitions[0]})"
                )

            current = next_phase

            # Refresh context for next iteration
            context = self.get_phase_context()

        # Max transitions reached
        self._log_cascade(transitions, self._max_cascade_transitions, 'max_transitions')
        return current

    def _log_cascade(self, transitions: List[str], count: int, reason: str) -> None:
        """
        Private: Log cascade results.

        Args:
            transitions: List of phases visited
            count: Number of transitions
            reason: Why cascade stopped
        """
        if count == 0:
            return  # No cascade happened, no log needed

        path = " → ".join(transitions)

        if reason == 'stable':
            print(f"🔄 Phase Cascade: {path}")
        elif reason == 'cycle':
            print(f"⚠️  Cycle Detected: {path} (forcing SYNTHESIS)")
        elif reason == 'max_transitions':
            print(f"⚠️  Max Transitions: {path}")
        elif reason == 'invalid':
            print(f"⚠️  Invalid Transition: {path}")

    def decide_next_phase(
            self,
            current_phase: str,
            context: PhaseState,
            observations: List[Any]  # Not used but required by protocol
    ) -> str:
        """
        Decide next phase based on orchestrator-specific logic using enums.

        Professional phase transition rules using OrchestratorPhase enum.
        Enforces iteration limits to prevent infinite loops.
        """
        # Handle None context gracefully
        if not context or not context.work_plan_status:
            return OrchestratorPhase.PLANNING.value  # No context or work plan, start planning

        status = context.work_plan_status

        # Check iteration limits first
        if self._is_phase_limit_exceeded(current_phase):
            return self._handle_phase_limit_exceeded(current_phase, status)

        # Convert current_phase to enum for type-safe comparison
        try:
            current_phase_enum = OrchestratorPhase(current_phase)
        except ValueError:
            # Unknown phase, default to planning
            return OrchestratorPhase.PLANNING.value

        # Phase transition logic using enums
        if current_phase_enum == OrchestratorPhase.PLANNING:
            # Access orchestrator context for smart decisions
            orch_ctx = self._current_orch_context

            # 🔍 DEBUG: Print current status for diagnosis
            print(f"🔍 [PLANNING] decide_next_phase called:")
            print(f"   - Has orch_ctx: {orch_ctx is not None}")
            print(f"   - status.total_items: {status.total_items}")
            print(f"   - status.pending_items: {status.pending_items}")
            print(f"   - status.blocked_items: {status.blocked_items}")
            print(f"   - status.in_progress_items: {status.in_progress_items}")
            print(f"   - status.has_remote_ready: {status.has_remote_ready}")
            print(f"   - status.has_local_ready: {status.has_local_ready}")
            print(f"   - status.is_complete: {status.is_complete}")
            if orch_ctx:
                print(f"   - Trigger reason: {orch_ctx.trigger.reason}")

            # CASE 1: No plan exists - must stay in planning to create one
            if status.total_items == 0:
                print(f"   → Decision: STAY in PLANNING (no items)")
                return OrchestratorPhase.PLANNING.value

            # CASE 2: Plan exists - use trigger reason for smart transition
            if orch_ctx:
                trigger_reason = orch_ctx.trigger.reason
                print(f"   → Has orch_ctx, trigger_reason: {trigger_reason}")

                # CASE 2A: RESPONSE_ARRIVED - skip planning, go process responses
                if trigger_reason == CycleTriggerReason.RESPONSE_ARRIVED:
                    print(f"   → CASE 2A: RESPONSE_ARRIVED")
                    # Responses don't need new planning - just process them
                    if status.has_responses:
                        print(f"   → Decision: Go to MONITORING (has_responses)")
                        return OrchestratorPhase.MONITORING.value
                    elif status.is_complete:
                        print(f"   → Decision: Go to SYNTHESIS (is_complete)")
                        return OrchestratorPhase.SYNTHESIS.value
                    else:
                        print(f"   → Decision: Go to ALLOCATION (fallback)")
                        return OrchestratorPhase.ALLOCATION.value

                # CASE 2B: NEW_REQUEST with existing plan
                elif trigger_reason == CycleTriggerReason.NEW_REQUEST:
                    print(f"   → CASE 2B: NEW_REQUEST")
                    # Check if this is a fresh plan (nothing executed yet)
                    # Note: Don't check pending_items == total_items because blocked items
                    # are counted separately. A fresh plan with dependencies will have
                    # some items blocked, but that's still a fresh plan (no work done yet).
                    all_pending = (status.done_items == 0 and
                                   status.failed_items == 0 and
                                   status.in_progress_items == 0)
                    print(
                        f"   → Fresh plan check: {all_pending} (done={status.done_items}, failed={status.failed_items}, in_progress={status.in_progress_items})")

                    if all_pending:
                        print(f"   → Fresh plan detected")
                        # Fresh plan just created - determine next phase based on what's actionable
                        if status.has_remote_ready:
                            # Has REMOTE items ready - go delegate them
                            # (Will cascade to EXECUTION if also has_local_ready)
                            print(f"   → Decision: Go to ALLOCATION (has_remote_ready=True)")
                            return OrchestratorPhase.ALLOCATION.value
                        elif status.has_local_ready:
                            # Has LOCAL items ready but NO REMOTE ready
                            # Skip ALLOCATION, go straight to EXECUTION
                            print(f"   → Decision: Go to EXECUTION (has_local_ready=True)")
                            return OrchestratorPhase.EXECUTION.value
                        elif status.blocked_items == status.total_items:
                            # Everything is blocked by dependencies (bad plan)
                            # Force SYNTHESIS to report the issue
                            print(f"   → Decision: Go to SYNTHESIS (all blocked)")
                            return OrchestratorPhase.SYNTHESIS.value
                        else:
                            # Fallback: go to ALLOCATION
                            print(f"   → Decision: Go to ALLOCATION (fallback)")
                            return OrchestratorPhase.ALLOCATION.value

                    # Not a fresh plan - work is in progress
                    print(f"   → Not a fresh plan (work in progress)")
                    if status.is_complete:
                        # Complete plan + new request = LLM might add new work
                        # But check if new items were already added and are ready
                        print(f"   → Plan was complete, checking if new items added...")
                        if status.has_remote_ready or status.has_local_ready:
                            # New items added and ready - transition to handle them
                            if status.has_remote_ready:
                                print(f"   → Decision: Go to ALLOCATION (has_remote_ready=True)")
                                return OrchestratorPhase.ALLOCATION.value
                            else:
                                print(f"   → Decision: Go to EXECUTION (has_local_ready=True)")
                                return OrchestratorPhase.EXECUTION.value
                        else:
                            # No ready items yet - give LLM chance to plan
                            print(f"   → Decision: STAY in PLANNING (complete + new request)")
                            return OrchestratorPhase.PLANNING.value
                    elif orch_ctx.health.progress_metrics.is_stalled:
                        # Stalled work - may need replanning or pivot
                        print(f"   → Decision: STAY in PLANNING (stalled)")
                        return OrchestratorPhase.PLANNING.value
                    elif status.failed_items == status.total_items > 0:
                        # All items failed - definitely need replanning
                        print(f"   → Decision: STAY in PLANNING (all failed)")
                        return OrchestratorPhase.PLANNING.value
                    else:
                        # In-progress work with new request
                        # Check if new items are ready to execute/delegate
                        print(f"   → Checking readiness for follow-up items...")
                        if status.has_remote_ready:
                            print(f"   → Decision: Go to ALLOCATION (has_remote_ready=True)")
                            return OrchestratorPhase.ALLOCATION.value
                        elif status.has_local_ready:
                            print(f"   → Decision: Go to EXECUTION (has_local_ready=True)")
                            return OrchestratorPhase.EXECUTION.value
                        else:
                            # Nothing ready yet - stay in planning to add/update items
                            print(f"   → Decision: STAY in PLANNING (no ready items)")
                            return OrchestratorPhase.PLANNING.value

            # CASE 3: Fallback if no orchestrator context (shouldn't happen normally)
            print(f"   → CASE 3: No orch_ctx (fallback)")
            if status.total_items > 0:
                print(f"   → Decision: Go to ALLOCATION (fallback, has items)")
                return OrchestratorPhase.ALLOCATION.value
            else:
                print(f"   → Decision: STAY in PLANNING (fallback, no items)")
                return OrchestratorPhase.PLANNING.value

        elif current_phase_enum == OrchestratorPhase.ALLOCATION:
            # 🔍 DEBUG: Print current status for diagnosis
            print(f"🔍 [ALLOCATION] decide_next_phase called:")
            print(f"   - status.has_local_ready: {status.has_local_ready}")
            print(f"   - status.has_remote_ready: {status.has_remote_ready}")
            print(f"   - status.has_responses: {status.has_responses}")
            print(f"   - status.has_remote_waiting: {status.has_remote_waiting}")

            # Move to execution if we have local work ready
            if status.has_local_ready:
                print(f"   → Decision: Go to EXECUTION (has_local_ready)")
                return OrchestratorPhase.EXECUTION.value
            # Move to monitoring if we have responses to interpret
            elif status.has_responses:
                print(f"   → Decision: Go to MONITORING (has_responses)")
                return OrchestratorPhase.MONITORING.value
            # If just waiting (no responses yet), stay in allocation (will finish and wait for graph)
            elif status.has_remote_waiting:
                print(f"   → Decision: STAY in ALLOCATION (has_remote_waiting, will finish)")
                return OrchestratorPhase.ALLOCATION.value  # Stay → finish
            else:
                print(f"   → Decision: STAY in ALLOCATION (default)")
                return OrchestratorPhase.ALLOCATION.value  # Stay in allocation

        elif current_phase_enum == OrchestratorPhase.EXECUTION:
            # 🔍 DEBUG: Print current status for diagnosis
            print(f"🔍 [EXECUTION] decide_next_phase called:")
            print(f"   - status.is_complete: {status.is_complete}")
            print(f"   - status.has_local_ready: {status.has_local_ready}")

            # Check if work is complete
            if status.is_complete:
                print(f"   → Decision: Go to SYNTHESIS (is_complete)")
                return OrchestratorPhase.SYNTHESIS.value
            # If still have local ready items, stay in execution (LLM may need multiple iterations)
            elif status.has_local_ready:
                print(f"   → Decision: STAY in EXECUTION (has_local_ready)")
                return OrchestratorPhase.EXECUTION.value
            # Otherwise move to monitoring
            else:
                print(f"   → Decision: Go to MONITORING (no local ready)")
                return OrchestratorPhase.MONITORING.value

        elif current_phase_enum == OrchestratorPhase.MONITORING:
            # 🔍 DEBUG: Print current status for diagnosis
            print(f"🔍 [MONITORING] decide_next_phase called:")
            print(f"   - status.total_items: {status.total_items}")
            print(f"   - status.pending_items: {status.pending_items}")
            print(f"   - status.in_progress_items: {status.in_progress_items}")
            print(f"   - status.waiting_items: {status.waiting_items}")
            print(f"   - status.done_items: {status.done_items}")
            print(f"   - status.failed_items: {status.failed_items}")
            print(f"   - status.blocked_items: {status.blocked_items}")
            print(f"   - status.has_responses: {status.has_responses}")
            print(f"   - status.has_local_ready: {status.has_local_ready}")
            print(f"   - status.has_remote_ready: {status.has_remote_ready}")
            print(f"   - status.has_remote_waiting: {status.has_remote_waiting}")
            print(f"   - status.is_complete: {status.is_complete}")

            # Check if work is complete
            if status.is_complete:
                print(f"   → Decision: Go to SYNTHESIS (is_complete)")
                return OrchestratorPhase.SYNTHESIS.value
            # PRIORITY: Stay in monitoring if we still have responses to interpret
            # (Process responses BEFORE transitioning to handle new pending work)
            elif status.has_responses:
                print(f"   → Decision: STAY in MONITORING (has_responses=True)")
                return OrchestratorPhase.MONITORING.value
            # Check for all-blocked scenario (no actionable work)
            # If all remaining items are blocked and we can't make progress, force SYNTHESIS
            elif (status.blocked_items > 0 and
                  status.pending_items == 0 and
                  not status.has_local_ready and
                  not status.has_remote_waiting):
                print(f"⚠️  All Items Blocked ({status.blocked_items}) - Forcing SYNTHESIS")
                print(f"   → Decision: Go to SYNTHESIS (all blocked)")
                return OrchestratorPhase.SYNTHESIS.value
            # Go back to execution if we have local ready items
            # (Check this BEFORE pending items to prioritize actual work over allocation)
            elif status.has_local_ready:
                print(f"   → Decision: Go to EXECUTION (has_local_ready=True)")
                return OrchestratorPhase.EXECUTION.value
            # Go back to allocation if we have pending items (and no responses)
            # Note: blocked items (pending=0, blocked>0) will NOT trigger this
            elif status.pending_items > 0:
                print(f"   → Decision: Go to ALLOCATION (pending_items={status.pending_items})")
                return OrchestratorPhase.ALLOCATION.value
            else:
                # No responses, no ready work, no pending work
                # Either waiting for delegated responses or all items blocked/complete
                print(f"   → Decision: STAY in MONITORING (waiting for responses or no actionable work)")
                return OrchestratorPhase.MONITORING.value  # Stay in monitoring

        elif current_phase_enum == OrchestratorPhase.SYNTHESIS:
            # Terminal phase - stay here
            return OrchestratorPhase.SYNTHESIS.value

        else:
            # Fallback (should not reach here with enum validation above)
            return OrchestratorPhase.PLANNING.value

    def _handle_phase_limit_exceeded(self, current_phase: str, status) -> str:
        """
        Private: Handle when a phase exceeds its iteration limit.

        Args:
            current_phase: Phase that exceeded limit
            status: Current work plan status

        Returns:
            Next phase to transition to (or synthesis for terminal)
        """
        print(f"⚠️  Phase Limit Exceeded: {current_phase}")

        try:
            current_phase_enum = OrchestratorPhase(current_phase)
        except ValueError:
            # Unknown phase, go to synthesis
            return OrchestratorPhase.SYNTHESIS.value

        # Phase-specific limit handling
        if current_phase_enum == OrchestratorPhase.PLANNING:
            # If planning stuck, try allocation anyway (maybe partial plan is enough)
            if status and status.total_items > 0:
                return OrchestratorPhase.ALLOCATION.value
            else:
                # No plan at all - terminal failure, go to synthesis
                return OrchestratorPhase.SYNTHESIS.value

        elif current_phase_enum == OrchestratorPhase.ALLOCATION:
            # If allocation stuck, try execution with what we have
            if status and status.has_local_ready:
                return OrchestratorPhase.EXECUTION.value
            else:
                # Skip to monitoring or synthesis
                return OrchestratorPhase.MONITORING.value

        elif current_phase_enum == OrchestratorPhase.EXECUTION:
            # If execution stuck, move to monitoring
            return OrchestratorPhase.MONITORING.value

        elif current_phase_enum == OrchestratorPhase.MONITORING:
            # If monitoring stuck (waiting too long), force synthesis
            return OrchestratorPhase.SYNTHESIS.value

        else:
            # For synthesis or unknown phases, stay in synthesis
            return OrchestratorPhase.SYNTHESIS.value

    def _build_validation_context(self, phase_name: str) -> PhaseValidationContext:
        """
        Build orchestrator-specific validation context.

        Extends base context with orchestrator-specific data:
        - Work plan for validation
        - Adjacent nodes for assignment validation

        Args:
            phase_name: Name of the phase to validate

        Returns:
            PhaseValidationContext with orchestrator-specific data
        """
        # Get base phase state
        phase_state = self.get_phase_context()

        # Enrich with orchestrator-specific data
        try:
            from graph.models import AdjacentNodes

            workload_service = self._get_workload_service()
            workspace_service = workload_service.get_workspace_service()
            plan = workspace_service.load_work_plan(self._thread_id, self._node_uid)

            # Get adjacent nodes (already an AdjacentNodes model)
            adjacent_nodes = self._get_adjacent_nodes()

            return PhaseValidationContext(
                phase_state=phase_state,
                thread_id=self._thread_id,
                node_uid=self._node_uid,
                plan=plan,
                adjacent_nodes=adjacent_nodes
            )
        except Exception as e:
            # Return minimal context on error
            return PhaseValidationContext(
                phase_state=phase_state,
                thread_id=self._thread_id,
                node_uid=self._node_uid
            )

    def _print_work_plan_after_phase(self, phase: str) -> None:
        """Print work plan status after phase transition."""
        try:
            from elements.nodes.common.workload import WorkItemStatus, WorkItemKind

            workspace_service = self._get_workload_service()
            plan = workspace_service.load_work_plan(self._thread_id, self._node_uid)

            if not plan or not plan.items:
                return

            status = workspace_service.get_work_plan_status(self._thread_id, self._node_uid)

            # Compact one-line status
            status_parts = []
            if status.pending_items > 0:
                status_parts.append(f"⏸️ {status.pending_items} Pending")
            if status.in_progress_items > 0:
                status_parts.append(f"🔄 {status.in_progress_items} In Progress")
            if status.done_items > 0:
                status_parts.append(f"✅ {status.done_items} Done")
            if status.failed_items > 0:
                status_parts.append(f"❌ {status.failed_items} Failed")

            extras = []
            if status.blocked_items > 0:
                extras.append(f"🚫 {status.blocked_items} Blocked")
            if status.waiting_items > 0:
                extras.append(f"⏳ {status.waiting_items} Waiting")

            extra_str = f" [{', '.join(extras)}]" if extras else ""

            # Print header with one-line status
            print(f"\n{'=' * 80}")
            print(f"📋 WORK PLAN after {phase.upper()} ({status.total_items} items)")
            print(f"={'=' * 80}")
            print(f"Status: {' | '.join(status_parts)}{extra_str}")

            # Show items compactly
            for item_status in [WorkItemStatus.PENDING, WorkItemStatus.IN_PROGRESS, WorkItemStatus.DONE,
                                WorkItemStatus.FAILED]:
                items = plan.get_items_by_status(item_status)
                if not items:
                    continue

                for item in items:
                    status_icon = {
                        WorkItemStatus.PENDING: "⏸️",
                        WorkItemStatus.IN_PROGRESS: "🔄",
                        WorkItemStatus.DONE: "✅",
                        WorkItemStatus.FAILED: "❌"
                    }.get(item_status, "❓")

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

                    # Show delegation conversation if present
                    if item.result and item.result.delegations:
                        delegation_count = len(item.result.delegations)
                        processed_count = sum(1 for d in item.result.delegations if d.processed)
                        pending_count = sum(1 for d in item.result.delegations if d.is_pending)
                        unprocessed_count = sum(1 for d in item.result.delegations if d.needs_attention)

                        if delegation_count == 1:
                            # Single delegation - show content with status
                            latest = item.result.delegations[0]
                            if latest.is_pending:
                                item_line += f"\n      ⏳ Waiting for response from {latest.delegated_to}"
                            elif latest.needs_attention:
                                resp_preview = latest.response_content[:100].replace('\n',
                                                                                     ' ') if latest.response_content else "No content"
                                item_line += f"\n      ⚡ NEW: {resp_preview}..."
                            else:
                                resp_preview = latest.response_content[:100].replace('\n',
                                                                                     ' ') if latest.response_content else "No content"
                                item_line += f"\n      ✓ Processed: {resp_preview}..."
                        else:
                            # Multiple delegations - show count summary
                            item_line += f"\n      💬 {delegation_count} turns ({processed_count}✓ processed, {unprocessed_count}⚡ pending, {pending_count}⏳ waiting)"
                            # Show latest exchange
                            latest = item.result.delegations[-1]
                            if latest.is_pending:
                                item_line += f"\n      ⏳ Latest: Waiting for {latest.delegated_to}"
                            elif latest.needs_attention:
                                resp_preview = latest.response_content[:100].replace('\n',
                                                                                     ' ') if latest.response_content else "No content"
                                item_line += f"\n      ⚡ Latest: {resp_preview}..."
                            else:
                                resp_preview = latest.response_content[:100].replace('\n',
                                                                                     ' ') if latest.response_content else "No content"
                                item_line += f"\n      ✓ Latest: {resp_preview}..."

                    print(f"   {item_line}")

            print(f"{'=' * 80}\n")
        except Exception as e:
            pass

    def get_dynamic_context_messages(self, phase_name: str) -> List["ChatMessage"]:
        """
        Provide fresh orchestrator context and work plan before each LLM call.

        This ensures the LLM always sees the current state:
        - Why this cycle is running (trigger)
        - User intent classification
        - Work plan health and progress
        - Phase history
        - Complete work plan with all items and responses

        All combined into ONE coherent message for better context.

        Called by strategy before each LLM interaction.

        Args:
            phase_name: Current phase name (unused, but kept for consistency)

        Returns:
            List of ChatMessage with fresh context (single combined message)
        """
        from elements.llms.common.chat.message import ChatMessage, Role

        messages = []

        try:
            workspace_service = self._get_workload_service().get_workspace_service()
            plan = workspace_service.load_work_plan(self._thread_id, self._node_uid)

            # Build work plan snapshot (full version for LLM)
            plan_snapshot = ""
            if plan:
                plan_snapshot = self._build_plan_snapshot_internal(plan, workspace_service, truncate_for_console=False)
            else:
                plan_snapshot = "No work plan exists yet."

            # If we have orchestrator context, format it with work plan in ONE message
            if self._current_orch_context:
                combined_context = self._current_orch_context.format_context(plan_snapshot)

                # Build truncated version for console printing
                plan_snapshot_console = ""
                if plan:
                    plan_snapshot_console = self._build_plan_snapshot_internal(plan, workspace_service, truncate_for_console=True)
                else:
                    plan_snapshot_console = "No work plan exists yet."
                combined_context_console = self._current_orch_context.format_context(plan_snapshot_console)

                # Print truncated context for debugging
                print(f"\n{'=' * 80}")
                print(f"📤 DYNAMIC CONTEXT PROVIDED TO LLM - Phase: {phase_name.upper()}")
                print(f"{'=' * 80}")
                print(combined_context_console)
                print(f"{'=' * 80}\n")

                # Send FULL context to LLM
                messages.append(ChatMessage(
                    role=Role.USER,
                    content=combined_context
                ))
            else:
                # Fallback: just show work plan (backward compatibility)
                fallback_context = f"Current Work Plan:\n{plan_snapshot}"

                # Build truncated version for console
                plan_snapshot_console = ""
                if plan:
                    plan_snapshot_console = self._build_plan_snapshot_internal(plan, workspace_service, truncate_for_console=True)
                else:
                    plan_snapshot_console = "No work plan exists yet."
                fallback_context_console = f"Current Work Plan:\n{plan_snapshot_console}"

                # Print truncated fallback context for debugging
                print(f"\n{'=' * 80}")
                print(f"📤 DYNAMIC CONTEXT PROVIDED TO LLM - Phase: {phase_name.upper()} (FALLBACK)")
                print(f"{'=' * 80}")
                print(fallback_context_console)
                print(f"{'=' * 80}\n")

                # Send FULL context to LLM
                messages.append(ChatMessage(
                    role=Role.USER,
                    content=fallback_context
                ))

        except Exception as e:
            # Fail gracefully - don't break execution if context building fails
            print(f"⚠️  Error building dynamic context: {e}")

        return messages

    def _build_workspace_summary_internal(self, workspace_service) -> str:
        """
        Build workspace summary (facts, results, variables).

        Note: Responses are no longer in facts - they're in work items.
        """
        lines = []

        # Key facts
        facts = workspace_service.get_facts(self._thread_id)
        if facts:
            lines.append(f"Facts ({len(facts)}):")
            for fact in facts[:5]:
                lines.append(f"  - {fact}")

        # Recent results
        results = workspace_service.get_results(self._thread_id)
        if results:
            lines.append(f"\nResults ({len(results)}):")
            for result in results[-3:]:
                lines.append(f"  - {result.agent_name}: {result.content[:50]}...")

        # Key variables (optional context)
        variables = workspace_service.get_all_variables(self._thread_id)
        if variables:
            # Only show non-internal variables
            public_vars = {k: v for k, v in variables.items()
                           if not k.startswith('_') and k not in ['orchestrator_uid', 'original_task_id']}
            if public_vars:
                lines.append(f"\nVariables ({len(public_vars)}):")
                for key, value in list(public_vars.items())[:3]:
                    lines.append(f"  - {key}: {str(value)[:30]}...")

        return "\n".join(lines) if lines else ""

    def _build_plan_snapshot_internal(self, plan, workspace_service, truncate_for_console: bool = False) -> str:
        """Build comprehensive work plan snapshot with responses."""
        from elements.nodes.common.workload import WorkItemStatus, WorkItemKind

        status = workspace_service.get_work_plan_status(self._thread_id, self._node_uid)

        lines = [
            f"Work Plan: {status.total_items} items total",
            f"Status: pending={status.pending_items}, in_progress={status.in_progress_items} (waiting={status.waiting_items}), done={status.done_items}, failed={status.failed_items}",
            f"Complete: {status.is_complete}"
        ]

        if plan:
            lines.append(f"\nPlan Summary: {plan.summary}")

            # Show ALL items by status - LLM needs full context
            for status in [WorkItemStatus.PENDING, WorkItemStatus.IN_PROGRESS, WorkItemStatus.DONE]:
                items = plan.get_items_by_status(status)
                if items:
                    lines.append(f"\n{status.value.upper()} ({len(items)}):")
                    for item in items:  # Show all items
                        status_info = f"  - {item.title} (ID: {item.id})"

                        # Show dependencies first (important for understanding blockers)
                        if item.dependencies:
                            status_info += f"\n    Dependencies: {item.dependencies}"

                        # Show assignment type
                        if item.kind == WorkItemKind.REMOTE:
                            status_info += f" → {item.assigned_uid}"
                        else:
                            status_info += " [LOCAL]"

                        if item.retry_count > 0:
                            status_info += f" [retries: {item.retry_count}/{item.max_retries}]"

                        lines.append(status_info)

                        # Show conversation for REMOTE items with delegation history
                        if item.result and item.result.delegations:
                            conv_summary = item.result.conversation_summary(truncate=truncate_for_console, max_chars=250)
                            for line in conv_summary.split('\n'):
                                lines.append(f"    {line}")

                        # Show local execution for LOCAL items
                        elif item.result and item.result.local_execution:
                            exec_info = item.result.local_execution
                            if exec_info.outcome:
                                outcome_text = exec_info.outcome
                                # Truncate for console readability
                                if truncate_for_console:
                                    # Handle multi-line outcomes by truncating and showing first portion
                                    outcome_lines = outcome_text.split('\n')
                                    if len(outcome_text) > 250:
                                        # Show first 250 chars across lines
                                        char_count = 0
                                        truncated_lines = []
                                        for oline in outcome_lines:
                                            if char_count + len(oline) > 250:
                                                remaining = 250 - char_count
                                                if remaining > 0:
                                                    truncated_lines.append(oline[:remaining] + "...")
                                                break
                                            truncated_lines.append(oline)
                                            char_count += len(oline)
                                        outcome_text = ' '.join(truncated_lines)  # Join with space for console
                                    else:
                                        # If short, still flatten to single line for console
                                        outcome_text = ' '.join(outcome_lines)

                                lines.append(f"    Execution: {outcome_text}")

        return "\n".join(lines)

    def get_phase_static_context(self, phase_name: str) -> List[ChatMessage]:
        """
        Get phase-specific static context (reference material).

        Returns SYSTEM messages with stable reference information
        that doesn't change during the cycle.

        Different phases need different static context:
        - PLANNING: Optional adjacent nodes for capability checking
        - ALLOCATION: Required adjacent nodes for delegation
        - EXECUTION: None (executes locally)
        - MONITORING: Required adjacent nodes for re-delegation
        - SYNTHESIS: None (read-only)

        Args:
            phase_name: Current phase name

        Returns:
            List of SYSTEM ChatMessage with phase-specific context
        """
        from elements.llms.common.chat.message import Role

        try:
            phase_enum = OrchestratorPhase(phase_name)
        except ValueError:
            return []

        messages = []

        # Phases that need adjacent nodes information
        if phase_enum in [
            OrchestratorPhase.PLANNING,    # Optional - for checking capabilities
            OrchestratorPhase.ALLOCATION,  # Required - for delegation
            OrchestratorPhase.MONITORING   # Required - for re-delegation
        ]:
            adjacent_nodes = self._build_adjacent_nodes_context()
            if adjacent_nodes:
                messages.append(ChatMessage(
                    role=Role.SYSTEM,
                    content=adjacent_nodes
                ))

        return messages

    def _build_adjacent_nodes_context(self) -> Optional[str]:
        """Build adjacent nodes reference context."""
        try:
            adjacent_nodes = self._get_adjacent_nodes()
            if not adjacent_nodes:
                return None

            lines = ["## Available Agents for Delegation\n"]

            for uid, card in adjacent_nodes.items():
                lines.append(f"**{card.name}** (uid: `{uid}`)")
                lines.append(f"  • Type: {card.type_key}")
                lines.append(f"  • Description: {card.description}")

                if card.skills:
                    lines.append(f"  • Skills: {card.skills}")

                lines.append("")

            return "\n".join(lines)
        except Exception:
            return None

    def build_focused_prompt(self, phase: str, phase_changed: bool) -> str:
        """
        Build comprehensive focused prompt for ALL scenarios.

        Handles every possible situation in each phase:
        - Different triggers (NEW_REQUEST, RESPONSE_ARRIVED, etc.)
        - Phase transitions vs continuations
        - Work plan states (empty, partial, complete)
        - Item states (pending, blocked, waiting, etc.)

        Returns clear, actionable instruction for THIS specific situation.

        Args:
            phase: Current phase name
            phase_changed: Whether we just transitioned to this phase

        Returns:
            Focused prompt string
        """
        try:
            phase_enum = OrchestratorPhase(phase)
        except ValueError:
            return ""

        # Get current context and state
        context = self._current_orch_context
        workspace_service = self._get_workload_service().get_workspace_service()
        plan = workspace_service.load_work_plan(self._thread_id, self._node_uid)
        status = workspace_service.get_work_plan_status(self._thread_id, self._node_uid)

        # Dispatch to phase-specific builder
        if phase_enum == OrchestratorPhase.PLANNING:
            return self._focused_prompt_planning(context, plan, status, phase_changed)
        elif phase_enum == OrchestratorPhase.ALLOCATION:
            return self._focused_prompt_allocation(context, plan, status, phase_changed)
        elif phase_enum == OrchestratorPhase.EXECUTION:
            return self._focused_prompt_execution(context, plan, status, phase_changed)
        elif phase_enum == OrchestratorPhase.MONITORING:
            return self._focused_prompt_monitoring(context, plan, status, phase_changed)
        elif phase_enum == OrchestratorPhase.SYNTHESIS:
            return self._focused_prompt_synthesis(context, plan, status, phase_changed)

        return ""

    def _focused_prompt_planning(self, context, plan, status, phase_changed: bool) -> str:
        """Planning phase prompts for ALL scenarios."""
        from .context.models import CycleTriggerReason

        trigger_reason = context.trigger.reason if context else None
        user_request = self._current_user_request or "the request"

        # Scenario 1: Brand new request, no plan
        if trigger_reason == CycleTriggerReason.NEW_REQUEST and status.total_items == 0:
            return (
                "🆕 **NEW REQUEST - CREATE WORK PLAN**\n\n"
                f"User asked: \"{user_request}\"\n\n"
                "**Your task:** Create a comprehensive work plan.\n\n"
                "**Steps:**\n"
                "1. Analyze the request to understand information needs\n"
                "2. Review 'Available Agents' section above to see agent capabilities\n"
                "3. For each work item, determine:\n"
                "   • Type: LOCAL (you execute) or REMOTE (delegate to agent)\n"
                "   • Dependencies: Which items must complete first\n"
                "   • Assignment: For REMOTE items, which agent based on their capabilities\n"
                "4. **COMPREHENSIVE COVERAGE:** When information completeness is important,\n"
                "   create work items for multiple agents rather than assuming which source\n"
                "   is best. Information is often distributed across multiple data sources.\n"
                "5. Use `CreateOrUpdateWorkPlanTool` with all items\n\n"
                "**Remember:** Create the structure now, delegation happens in ALLOCATION phase."
            )

        # Scenario 2: Follow-up request with completed plan
        elif trigger_reason == CycleTriggerReason.NEW_REQUEST and status.is_complete:
            return (
                "🆕 **FOLLOW-UP REQUEST - EXTEND PLAN**\n\n"
                f"User's follow-up: \"{user_request}\"\n\n"
                f"**Context:** Existing plan has {status.total_items} items (all complete).\n\n"
                "**Your task:** Add new work items to address this follow-up.\n\n"
                "**Steps:**\n"
                "1. Review what was already done (check DONE items above)\n"
                "2. Determine what new work is needed\n"
                "3. Add new items that build on or extend previous work\n"
                "4. Set dependencies on completed items if needed\n"
                "5. Use `CreateOrUpdateWorkPlanTool` with updated plan"
            )

        # Scenario 3: Follow-up request with in-progress plan
        elif trigger_reason == CycleTriggerReason.NEW_REQUEST and status.total_items > 0:
            in_progress_count = status.in_progress_items + status.pending_items + status.waiting_items
            return (
                "🆕 **FOLLOW-UP REQUEST - UPDATE PLAN**\n\n"
                f"User's follow-up: \"{user_request}\"\n\n"
                f"**Context:** Plan has {status.total_items} items "
                f"({status.done_items} done, {in_progress_count} in-progress, {status.failed_items} failed).\n\n"
                "**Your task:** Update plan to incorporate new request.\n\n"
                "**Steps:**\n"
                "1. Review current plan status (above)\n"
                "2. Determine if new request:\n"
                "   • Adds new independent work → Add new items\n"
                "   • Clarifies existing work → Update descriptions\n"
                "   • Depends on in-progress work → Add items with dependencies\n"
                "3. Use `CreateOrUpdateWorkPlanTool` with updated plan"
            )

        # Scenario 4: Responses arrived (replanning needed?)
        elif trigger_reason == CycleTriggerReason.RESPONSE_ARRIVED:
            return (
                "📥 **RESPONSES ARRIVED - REVIEW PLAN**\n\n"
                "New responses have been received. You're in PLANNING phase, which means\n"
                "the system detected that the plan might need updates.\n\n"
                "**Your task:** Review the plan and decide:\n"
                "• Are new work items needed based on responses?\n"
                "• Should failed items be retried with different approach?\n"
                "• Is the plan still appropriate?\n\n"
                "Update plan if needed, or finish to proceed to next phase."
            )

        # Scenario 5: Continuation (refining)
        elif not phase_changed:
            return (
                "⏭️ **CONTINUE PLANNING**\n\n"
                "You're still in PLANNING phase.\n\n"
                "**Options:**\n"
                "• Refine work items if needed\n"
                "• Update dependencies or assignments\n"
                "• Finish to proceed to ALLOCATION phase"
            )

        # Fallback
        return "Review and create/update the work plan as needed."

    def _focused_prompt_allocation(self, context, plan, status, phase_changed: bool) -> str:
        """Allocation phase prompts with detailed assignment/delegation tracking."""
        from elements.nodes.common.workload import WorkItemKind, WorkItemStatus

        if not plan:
            return "Delegate pending REMOTE work items to appropriate agents."

        # Get all REMOTE items
        all_remote = [item for item in plan.items.values() if item.kind == WorkItemKind.REMOTE]
        total_remote = len(all_remote)

        if total_remote == 0:
            return "✅ No REMOTE items in work plan. Finish to proceed to next phase."

        # ========== CATEGORIZE BY STATE ==========
        # State 1: Unassigned (need both assign + delegate)
        unassigned = [
            item for item in all_remote
            if item.status == WorkItemStatus.PENDING and not item.assigned_uid
        ]

        # State 2: Assigned but not delegated (need delegate only)
        assigned_not_delegated = [
            item for item in all_remote
            if item.status == WorkItemStatus.PENDING
               and item.assigned_uid
               and (not item.result or not item.result.delegations)
        ]

        # State 3: Delegated (in progress)
        delegated = [
            item for item in all_remote
            if item.status == WorkItemStatus.IN_PROGRESS
        ]

        # State 4: Completed (done or failed)
        completed = [
            item for item in all_remote
            if item.status in [WorkItemStatus.DONE, WorkItemStatus.FAILED]
        ]

        # State 5: Blocked by dependencies
        ready_items = plan.get_ready_items()
        blocked_items = plan.get_blocked_items()

        unassigned_ready = [item for item in unassigned if item in ready_items]
        unassigned_blocked = [item for item in unassigned if item in blocked_items]
        assigned_ready = [item for item in assigned_not_delegated if item in ready_items]
        assigned_blocked = [item for item in assigned_not_delegated if item in blocked_items]

        # Total actionable items (ready for assign or delegate)
        actionable = len(unassigned_ready) + len(assigned_ready)

        # ========== BUILD PROMPT BASED ON STATE ==========

        # Scenario 1: First iteration, items need action
        if phase_changed and actionable > 0:
            lines = [f"🎯 **ALLOCATE {total_remote} REMOTE ITEM(S)**\n"]

            # Show detailed breakdown
            lines.append("**Current Status:**")
            lines.append(f"  • Unassigned: {len(unassigned)} ({len(unassigned_ready)} ready, {len(unassigned_blocked)} blocked)")
            lines.append(f"  • Assigned (not delegated): {len(assigned_not_delegated)} ({len(assigned_ready)} ready, {len(assigned_blocked)} blocked)")
            lines.append(f"  • Delegated: {len(delegated)}")
            lines.append(f"  • Completed: {len(completed)}")
            lines.append("")

            # Case A: Items need assignment
            if unassigned_ready:
                lines.append(f"**STEP 1: ASSIGN {len(unassigned_ready)} ITEM(S)**")
                item_list = ", ".join([f"'{item.id}'" for item in unassigned_ready[:3]])
                if len(unassigned_ready) > 3:
                    item_list += f" (+{len(unassigned_ready) - 3} more)"
                lines.append(f"Items: {item_list}")
                lines.append("• Use AssignWorkItemTool to assign each item to an agent")
                lines.append("")

            # Case B: Items need delegation
            if assigned_ready:
                lines.append(f"**STEP 2: DELEGATE {len(assigned_ready)} ITEM(S)**")
                item_list = ", ".join([f"'{item.id}' → {item.assigned_uid}" for item in assigned_ready[:3]])
                if len(assigned_ready) > 3:
                    item_list += f" (+{len(assigned_ready) - 3} more)"
                lines.append(f"Items: {item_list}")
                lines.append("• Use DelegateTaskTool to send task to assigned agent")
                lines.append("  ⚠️ Must include work_item_id for response tracking")
                lines.append("")

            lines.append("**Tips:**")
            lines.append("• Review capabilities of all agents shown in 'Available Agents' section above")
            lines.append("• Use GetNodeCardTool only if you need more details about an agent")
            lines.append("• Match task intent to agent domain expertise")
            lines.append("• Parallel delegation enables comprehensive coverage across data sources")
            lines.append("• Provide clear, specific instructions in each delegation")

            return "\n".join(lines)

        # Scenario 2: First iteration, nothing actionable
        elif phase_changed and actionable == 0:
            if len(delegated) + len(completed) == total_remote:
                return (
                    "✅ **ALL REMOTE ITEMS ALLOCATED**\n\n"
                    f"Status: {len(delegated)} delegated, {len(completed)} completed.\n\n"
                    "Finish to proceed to next phase."
                )
            else:
                blocked_count = len(unassigned_blocked) + len(assigned_blocked)
                return (
                    f"🚫 **{blocked_count} REMOTE ITEMS BLOCKED**\n\n"
                    "All REMOTE items are blocked by dependencies.\n\n"
                    "Finish to proceed (will return when dependencies resolve)."
                )

        # Scenario 3: Continuation, items still need action
        elif not phase_changed and actionable > 0:
            lines = [f"⏭️ **CONTINUE ALLOCATION** ({actionable} items need action)\n"]
            lines.append("**Progress:**")
            lines.append(f"  • {len(unassigned_ready)} need assignment")
            lines.append(f"  • {len(assigned_ready)} need delegation")
            lines.append(f"  • {len(delegated)} delegated (in progress)")
            lines.append(f"  • {len(completed)} completed")
            lines.append("")

            if unassigned_ready:
                lines.append(f"**NEXT: Assign {len(unassigned_ready)} item(s) using AssignWorkItemTool**")
            elif assigned_ready:
                lines.append(f"**NEXT: Delegate {len(assigned_ready)} item(s) using DelegateTaskTool**")

            return "\n".join(lines)

        # Scenario 4: Continuation, all done
        elif not phase_changed and actionable == 0:
            return (
                "✅ **ALLOCATION COMPLETE**\n\n"
                f"All {total_remote} REMOTE items allocated.\n\n"
                f"Status: {len(delegated)} in progress, {len(completed)} completed.\n\n"
                "Finish to proceed to next phase."
            )

        # Fallback
        return "Allocate pending REMOTE work items to appropriate agents."

    def _focused_prompt_execution(self, context, plan, status, phase_changed: bool) -> str:
        """Execution phase prompts for ALL scenarios."""
        from elements.nodes.common.workload import WorkItemKind

        if not plan:
            return "Execute pending LOCAL work items."

        # Use WorkPlan helper methods for clean, consistent logic
        ready_items = plan.get_ready_items()
        blocked_items = plan.get_blocked_items()

        # Filter by kind
        pending_local = [item for item in ready_items if item.kind == WorkItemKind.LOCAL]
        blocked_local = [item for item in blocked_items if item.kind == WorkItemKind.LOCAL]

        total_local = len([
            item for item in plan.items.values()
            if item.kind == WorkItemKind.LOCAL
        ])

        # Scenario 1: First iteration with items to execute
        if phase_changed and pending_local:
            item_details = []
            for item in pending_local[:3]:
                item_details.append(f"  • `{item.id}`: {item.title}")
            if len(pending_local) > 3:
                item_details.append(f"  • (+{len(pending_local) - 3} more items)")

            items_str = "\n".join(item_details)

            return (
                f"⚡ **EXECUTE {len(pending_local)} LOCAL ITEM(S)**\n\n"
                f"Items ready to execute:\n{items_str}\n\n"
                "**For EACH item:**\n"
                "1. Read the item description carefully\n"
                "2. Execute using your capabilities and available tools\n"
                "3. `RecordLocalExecutionTool(item_id, outcome)`\n"
                "   → This automatically marks the item as DONE\n\n"
                "**Outcome format:** Describe what you did and the results."
            )

        # Scenario 2: First iteration, nothing to execute
        elif phase_changed and not pending_local and not blocked_local:
            if total_local == 0:
                reason = "No LOCAL items in plan."
            else:
                reason = "All LOCAL items already executed."

            return (
                "✅ **NO LOCAL ITEMS TO EXECUTE**\n\n"
                f"{reason}\n\n"
                "**Your task:** Finish to proceed to next phase."
            )

        # Scenario 3: First iteration with blocked items
        elif phase_changed and blocked_local and not pending_local:
            blocked_names = ", ".join([f"'{item.id}'" for item in blocked_local[:2]])
            if len(blocked_local) > 2:
                blocked_names += f" (+{len(blocked_local) - 2} more)"

            return (
                "🚫 **LOCAL ITEMS BLOCKED**\n\n"
                f"{len(blocked_local)} items blocked by dependencies: {blocked_names}\n\n"
                "Cannot execute until dependencies complete.\n\n"
                "**Your task:** Finish to proceed (will return when unblocked)."
            )

        # Scenario 4: Continuation with items remaining
        elif not phase_changed and pending_local:
            return (
                f"⏭️ **CONTINUE EXECUTION** ({len(pending_local)} remaining)\n\n"
                "Continue executing pending LOCAL items."
            )

        # Scenario 5: Continuation, all done
        elif not phase_changed and not pending_local:
            return (
                "✅ **EXECUTION COMPLETE**\n\n"
                "All LOCAL items executed.\n\n"
                "Finish to proceed to next phase."
            )

        # Fallback
        return "Execute pending LOCAL work items."

    def _focused_prompt_monitoring(self, context, plan, status, phase_changed: bool) -> str:
        """Monitoring phase prompts for ALL scenarios."""
        from .context.models import CycleTriggerReason

        trigger_reason = context.trigger.reason if context else None
        changed_items = context.trigger.changed_items if context else []

        if not plan:
            return "Review work plan and update item statuses."

        # Find items with unprocessed responses
        items_need_attention = []
        items_waiting = []

        for item in plan.items.values():
            if item.result and item.result.delegations:
                for exchange in item.result.delegations:
                    if exchange.needs_attention:
                        items_need_attention.append(item)
                        break
                    elif exchange.is_pending:
                        items_waiting.append(item)
                        break

        # Scenario 1: Single response just arrived
        if trigger_reason == CycleTriggerReason.RESPONSE_ARRIVED and len(changed_items) == 1:
            item_id = changed_items[0]
            return (
                "📥 **RESPONSE RECEIVED**\n\n"
                f"Agent responded to work item: `{item_id}`\n\n"
                "**Your task:** Review the response (marked 🔔 or ⚡ in work plan).\n\n"
                "**Decision:**\n"
                f"• **Acceptable?** → `MarkWorkItemStatusTool('{item_id}', 'done')`\n"
                f"• **Needs follow-up?** → `DelegateTaskTool(same agent, clarification, work_item_id)`\n"
                "  ↳ Use same work_item_id to continue conversation\n"
                f"• **Failed/impossible?** → `MarkWorkItemStatusTool('{item_id}', 'failed')`\n\n"
                "**Quality bar:** Mark DONE only if response truly addresses the requirement."
            )

        # Scenario 2: Multiple responses arrived
        elif trigger_reason == CycleTriggerReason.RESPONSE_ARRIVED and len(changed_items) > 1:
            items_list = ", ".join([f"`{item}`" for item in changed_items[:4]])
            if len(changed_items) > 4:
                items_list += f" (+{len(changed_items) - 4} more)"

            return (
                f"📥 **{len(changed_items)} RESPONSES RECEIVED**\n\n"
                f"Items: {items_list}\n\n"
                "**Your task:** Process ALL responses in this iteration.\n\n"
                "**For each response:**\n"
                "1. Review quality and completeness\n"
                "2. Decide: Mark DONE, request follow-up, or mark FAILED\n"
                "3. Use appropriate tool for each decision\n\n"
                "Responses marked 🔔 or ⚡ in work plan above."
            )

        # Scenario 3: Entered from EXECUTION (checking state)
        elif phase_changed and trigger_reason != CycleTriggerReason.RESPONSE_ARRIVED:
            if items_need_attention:
                return (
                    f"🔍 **REVIEW {len(items_need_attention)} RESPONSE(S)**\n\n"
                    "Local execution complete. Now review responses from delegated work.\n\n"
                    "Process items marked 🔔 or ⚡ in the work plan above."
                )
            elif items_waiting:
                return (
                    f"⏳ **WAITING FOR {len(items_waiting)} RESPONSE(S)**\n\n"
                    "All actionable work complete. Waiting for agents to respond.\n\n"
                    "**Your task:** Finish to pause (will resume when responses arrive)."
                )
            else:
                # All work complete or ready to synthesize
                return (
                    "✅ **NO PENDING RESPONSES**\n\n"
                    "All work items processed.\n\n"
                    "**Your task:** Finish to proceed to SYNTHESIS."
                )

        # Scenario 4: Continuation with unprocessed responses
        elif not phase_changed and items_need_attention:
            return (
                f"⏭️ **CONTINUE MONITORING** ({len(items_need_attention)} items need attention)\n\n"
                "Continue processing remaining responses."
            )

        # Scenario 5: Continuation, all processed
        elif not phase_changed and not items_need_attention:
            if items_waiting:
                return (
                    f"⏳ **WAITING FOR RESPONSES** ({len(items_waiting)} items)\n\n"
                    "All available responses processed.\n\n"
                    "Finish to pause until more responses arrive."
                )
            else:
                return (
                    "✅ **MONITORING COMPLETE**\n\n"
                    "All work items reviewed and processed.\n\n"
                    "Finish to proceed to SYNTHESIS."
                )

        # Fallback
        return "Review responses and update work item statuses."

    def _focused_prompt_synthesis(self, context, plan, status, phase_changed: bool) -> str:
        """Synthesis phase prompts for ALL scenarios."""
        from .context.models import CycleTriggerReason

        trigger_reason = context.trigger.reason if context else None
        user_request = self._current_user_request or "the request"

        # Calculate work stats for context
        total_items = status.total_items
        done_items = status.done_items
        failed_items = status.failed_items

        # Scenario 1: All work complete, first synthesis
        if phase_changed and status.is_complete and failed_items == 0:
            return (
                "✨ **SYNTHESIZE COMPLETE RESULTS**\n\n"
                f"All {total_items} work items completed successfully!\n\n"
                f"Original request: \"{user_request}\"\n\n"
                "**Your task:** Create comprehensive final response.\n\n"
                "**Include:**\n"
                "1. Direct answer to user's request\n"
                "2. Summary of what was accomplished\n"
                "3. Key findings or results from work items\n"
                "4. Any important details or context\n\n"
                "**Then:** Finish to return response to user."
            )

        # Scenario 2: Partial completion with failures
        elif phase_changed and (done_items > 0 or failed_items > 0):
            return (
                "⚠️ **SYNTHESIZE PARTIAL RESULTS**\n\n"
                f"Work summary: {done_items}/{total_items} done, {failed_items} failed.\n\n"
                f"Original request: \"{user_request}\"\n\n"
                "**Your task:** Create honest, transparent response.\n\n"
                "**Include:**\n"
                "1. What was successfully accomplished (from DONE items)\n"
                "2. What couldn't be completed and why (from FAILED items)\n"
                "3. Whether partial results answer the request\n"
                "4. Suggestions for next steps if applicable\n\n"
                "**Be transparent about limitations.**\n\n"
                "**Then:** Finish to return response to user."
            )

        # Scenario 3: No work completed (edge case)
        elif phase_changed and done_items == 0 and total_items > 0:
            if failed_items == total_items:
                return (
                    "❌ **SYNTHESIZE FAILURE RESULTS**\n\n"
                    f"Unable to complete any of {total_items} work items.\n\n"
                    f"Original request: \"{user_request}\"\n\n"
                    "**Your task:** Explain what went wrong.\n\n"
                    "**Include:**\n"
                    "1. Clear explanation of why work couldn't be completed\n"
                    "2. What was attempted\n"
                    "3. Suggestions for alternative approaches\n\n"
                    "**Then:** Finish to return response to user."
                )
            else:
                # All items still in progress/waiting (shouldn't normally happen)
                return (
                    "🔄 **EARLY SYNTHESIS**\n\n"
                    "Entered SYNTHESIS but work is still in progress.\n\n"
                    "**Options:**\n"
                    "• Provide interim update if user needs it now\n"
                    "• Explain current status and what's pending\n\n"
                    "**Then:** Finish to return response."
                )

        # Scenario 4: Follow-up request during synthesis
        elif trigger_reason == CycleTriggerReason.NEW_REQUEST:
            return (
                "🆕 **USER FOLLOW-UP IN SYNTHESIS**\n\n"
                f"User asked: \"{user_request}\"\n\n"
                "You're in SYNTHESIS phase (typically read-only).\n\n"
                "**Options:**\n"
                "• If follow-up is clarification → Answer directly and finish\n"
                "• If follow-up needs new work → Suggest returning to PLANNING\n"
                "  (Note: Phase will transition automatically if needed)\n\n"
                "Respond to the follow-up appropriately."
            )

        # Scenario 5: Continuation in synthesis
        elif not phase_changed:
            return (
                "⏭️ **CONTINUE SYNTHESIS**\n\n"
                "You're still in SYNTHESIS phase.\n\n"
                "**Options:**\n"
                "• Refine your response\n"
                "• Add more context or details\n"
                "• Finish when response is complete\n\n"
                f"Original request: \"{user_request}\""
            )

        # Fallback
        return (
            "Synthesize results and create final response for the user. "
            "Review completed work items and formulate a comprehensive answer."
        )
