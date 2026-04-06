"""
Pydantic models for orchestrator context.

Defines structured data models for context-aware orchestration including
cycle triggers, intent classification, health metrics, and history tracking.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class CycleTriggerReason(Enum):
    """Why an orchestration cycle was triggered."""
    NEW_REQUEST = "new_request"           # User sent a message (new or follow-up)
    RESPONSE_ARRIVED = "response_arrived" # Agent(s) responded to delegated work
    
    # Reserved for future use
    RETRY = "retry"                       # Automatic retry after failure
    MANUAL = "manual"                     # Manual trigger for testing/debugging


class PendingCycle(BaseModel):
    """
    Information about a pending orchestration cycle.
    
    DEPRECATED: Use OrchestratorCycle instead for better multi-trigger support.
    Kept for backward compatibility with existing code.
    """
    thread_id: str = Field(..., description="Thread that needs orchestration")
    reason: CycleTriggerReason = Field(..., description="Why this cycle is triggered")
    changed_items: List[str] = Field(default_factory=list, description="Work item IDs that were affected (for RESPONSE_ARRIVED)")


class TriggerEvent(BaseModel):
    """
    A single trigger event that occurred for an orchestration cycle.
    
    Each event represents one reason why orchestration was triggered
    (e.g., one response arrival, one new request).
    """
    reason: CycleTriggerReason = Field(..., description="Why this trigger occurred")
    changed_items: List[str] = Field(default_factory=list, description="Work items affected by this trigger")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_summary(self) -> str:
        """Format this trigger event as a string."""
        if self.reason == CycleTriggerReason.RESPONSE_ARRIVED:
            if self.changed_items:
                items = ', '.join(self.changed_items[:2])
                if len(self.changed_items) > 2:
                    items += f" (+{len(self.changed_items) - 2} more)"
                return f"Response arrived for: {items}"
            return "Response arrived"
        elif self.reason == CycleTriggerReason.NEW_REQUEST:
            return "New user request"
        elif self.reason == CycleTriggerReason.RETRY:
            return "Retry requested"
        elif self.reason == CycleTriggerReason.MANUAL:
            return "Manual trigger"
        return self.reason.value


class OrchestratorCycle(BaseModel):
    """
    Represents an orchestration cycle for a single thread.
    
    Created once per thread, accumulates all trigger events that occur
    during packet processing. When executed, the LLM sees ALL triggers
    for complete context awareness.
    
    Design:
    - One cycle per thread (enforced by dict key in OrchestratorNode)
    - Accumulates multiple trigger events
    - Preserves all information for LLM context
    - No prioritization - LLM decides what to do
    """
    thread_id: str = Field(..., description="Thread being orchestrated")
    triggers: List[TriggerEvent] = Field(default_factory=list, description="All trigger events")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def add_trigger(
        self, 
        reason: CycleTriggerReason, 
        changed_items: List[str] = None
    ) -> None:
        """
        Add a trigger event to this cycle.
        
        Args:
            reason: Why this trigger occurred
            changed_items: Work items affected by this trigger
        """
        event = TriggerEvent(
            reason=reason,
            changed_items=changed_items or []
        )
        self.triggers.append(event)
    
    @property
    def all_changed_items(self) -> Set[str]:
        """Get all unique work items affected across all triggers."""
        items = set()
        for trigger in self.triggers:
            items.update(trigger.changed_items)
        return items
    
    @property
    def has_new_requests(self) -> bool:
        """Check if any trigger is a new user request."""
        return any(t.reason == CycleTriggerReason.NEW_REQUEST for t in self.triggers)
    
    @property
    def has_responses(self) -> bool:
        """Check if any trigger is a response arrival."""
        return any(t.reason == CycleTriggerReason.RESPONSE_ARRIVED for t in self.triggers)
    
    @property
    def response_count(self) -> int:
        """Count how many response events occurred."""
        return sum(1 for t in self.triggers if t.reason == CycleTriggerReason.RESPONSE_ARRIVED)
    
    def get_trigger_summary(self) -> str:
        """
        Format all triggers as a clear summary for LLM context.
        
        Examples:
        - "2 responses arrived for: jira_search, confluence_search"
        - "New request + 1 response arrived for: data_fetch"
        - "3 responses arrived"
        """
        if not self.triggers:
            return "Cycle triggered"
        
        # Group by reason
        by_reason: Dict[CycleTriggerReason, List[str]] = {}
        for trigger in self.triggers:
            if trigger.reason not in by_reason:
                by_reason[trigger.reason] = []
            by_reason[trigger.reason].extend(trigger.changed_items)
        
        parts = []
        
        # Format each reason group
        if CycleTriggerReason.NEW_REQUEST in by_reason:
            parts.append("New request")
        
        if CycleTriggerReason.RESPONSE_ARRIVED in by_reason:
            response_items = by_reason[CycleTriggerReason.RESPONSE_ARRIVED]
            count = self.response_count
            if count == 1:
                if response_items:
                    parts.append(f"Response arrived for: {', '.join(response_items[:3])}")
                else:
                    parts.append("Response arrived")
            else:
                # Multiple responses
                unique_items = set(response_items)
                if unique_items:
                    items_str = ', '.join(list(unique_items)[:3])
                    if len(unique_items) > 3:
                        items_str += f" (+{len(unique_items) - 3} more)"
                    parts.append(f"{count} responses arrived for: {items_str}")
                else:
                    parts.append(f"{count} responses arrived")
        
        if CycleTriggerReason.RETRY in by_reason:
            parts.append("Retry requested")
        
        if CycleTriggerReason.MANUAL in by_reason:
            parts.append("Manual trigger")
        
        return " + ".join(parts) if parts else "Multiple triggers"
    
    def to_pending_cycle(self) -> 'PendingCycle':
        """
        Convert to PendingCycle for backward compatibility.
        
        Uses the FIRST trigger's reason as primary, includes all changed items.
        """
        primary_reason = self.triggers[0].reason if self.triggers else CycleTriggerReason.NEW_REQUEST
        
        return PendingCycle(
            thread_id=self.thread_id,
            reason=primary_reason,
            changed_items=list(self.all_changed_items)
        )


class CycleTrigger(BaseModel):
    """Context about why this orchestration cycle is running."""
    reason: CycleTriggerReason
    description: str = Field(..., description="Human-readable explanation")
    
    # Context-specific details
    new_user_message: Optional[str] = Field(None, description="For NEW_REQUEST")
    response_task_ids: List[str] = Field(default_factory=list, description="Task IDs for RESPONSE_ARRIVED")
    changed_items: List[str] = Field(default_factory=list, description="Work item IDs affected")
    
    def to_summary(self) -> str:
        """Format trigger as string for context display."""
        if self.reason == CycleTriggerReason.NEW_REQUEST:
            return f"🆕 NEW REQUEST: {self.new_user_message}"
        elif self.reason == CycleTriggerReason.RESPONSE_ARRIVED:
            count = len(self.changed_items)
            if count == 0:
                return "📥 RESPONSES ARRIVED"
            items = ', '.join(self.changed_items[:3])
            more = f" (+{count - 3} more)" if count > 3 else ""
            return f"📥 RESPONSES ARRIVED for: {items}{more}"
        elif self.reason == CycleTriggerReason.RETRY:
            return f"🔁 RETRY: {self.description}"
        elif self.reason == CycleTriggerReason.MANUAL:
            return f"🔧 MANUAL: {self.description}"
        else:
            return f"🔔 {self.reason.value.upper()}: {self.description}"


class FutilityIndicator(BaseModel):
    """Detects repeated failures and futility patterns."""
    item_id: str
    issue_type: str = Field(..., description="repeated_failure, stuck_delegation, circular_dependency")
    occurrences: int
    description: str
    suggested_action: str


class ProgressMetrics(BaseModel):
    """Progress tracking across orchestration cycles."""
    total_cycles: int = 0
    cycles_without_completion: int = 0
    items_completed_this_cycle: int = 0
    items_blocked: int = 0
    
    # Trend indicators
    is_stalled: bool = Field(default=False, description="No progress for N cycles")
    is_regressing: bool = Field(default=False, description="Failed items increasing")
    
    def to_summary(self) -> str:
        """Format progress metrics as string."""
        if self.is_stalled:
            return f"⚠️ STALLED: No progress for {self.cycles_without_completion} cycles"
        if self.is_regressing:
            return f"📉 REGRESSING: Items failing, may need pivot"
        if self.items_completed_this_cycle > 0:
            return f"✅ PROGRESSING: {self.items_completed_this_cycle} item(s) completed this cycle"
        return f"🔄 WORKING: {self.total_cycles} cycle(s) so far"


class WorkPlanHealth(BaseModel):
    """Health and progress indicators for work plan."""
    futility_indicators: List[FutilityIndicator] = Field(default_factory=list)
    progress_metrics: ProgressMetrics
    blocked_items_analysis: List[str] = Field(
        default_factory=list,
        description="Human-readable explanations of blocked items"
    )
    
    # Quick flags
    has_critical_issues: bool = False
    needs_pivot: bool = False
    needs_user_input: bool = False
    
    def to_summary(self) -> str:
        """Format health status as string."""
        lines = []
        
        # Progress
        lines.append(f"Progress: {self.progress_metrics.to_summary()}")
        
        # Critical issues
        if self.has_critical_issues:
            lines.append("\n⚠️ CRITICAL ISSUES DETECTED:")
            for indicator in self.futility_indicators[:3]:
                lines.append(f"  - {indicator.item_id}: {indicator.description}")
                lines.append(f"    Suggestion: {indicator.suggested_action}")
        
        # Blocked items
        if self.blocked_items_analysis:
            lines.append("\n🚫 BLOCKED ITEMS:")
            for analysis in self.blocked_items_analysis[:3]:
                lines.append(f"  - {analysis}")
        
        # Recommendations
        if self.needs_pivot:
            lines.append("\n💡 RECOMMENDATION: Consider pivoting strategy or marking futile items as FAILED")
        if self.needs_user_input:
            lines.append("\n💡 RECOMMENDATION: May need to ask user for clarification or additional information")
        
        return "\n".join(lines) if lines else "✅ No health issues detected"


class PhaseTransition(BaseModel):
    """Record of a phase transition."""
    from_phase: str
    to_phase: str
    timestamp: str
    reason: str = ""
    actions_taken: List[str] = Field(default_factory=list)


class PhaseHistory(BaseModel):
    """History of recent phase activity."""
    current_cycle_transitions: List[PhaseTransition] = Field(default_factory=list)
    phase_iteration_counts: Dict[str, int] = Field(default_factory=dict)
    last_n_cycles: List[dict] = Field(
        default_factory=list,
        description="Last 3 cycles summary"
    )
    
    def to_summary(self) -> str:
        """Format history as string."""
        if not self.current_cycle_transitions and not self.phase_iteration_counts:
            return "Starting first cycle"
        
        lines = ["Recent Phase Activity:"]
        
        # Current cycle path
        if self.current_cycle_transitions:
            path = " → ".join([t.to_phase for t in self.current_cycle_transitions])
            lines.append(f"  Current cycle path: {path}")
        
        # Iteration counts (only show phases with >1 iteration)
        if self.phase_iteration_counts:
            counts = ', '.join([f"{p}={c}" for p, c in self.phase_iteration_counts.items() if c > 1])
            if counts:
                lines.append(f"  Phase iterations: {counts}")
        
        return "\n".join(lines)


class OrchestratorContext(BaseModel):
    """Complete context for orchestrator cycle execution."""
    
    # Why are we running?
    trigger: CycleTrigger
    
    # How's the work plan doing?
    health: WorkPlanHealth
    
    # What happened before?
    history: PhaseHistory
    
    # Current state (from existing PhaseState)
    phase_state: Any = Field(None, description="PhaseState from existing system")
    
    def format_context(self, work_plan_snapshot: str) -> str:
        """
        Format compact context: trigger line + plan snapshot.

        Health and history are omitted — the plan snapshot already contains
        status counts, and the focused prompt provides situation-specific guidance.
        """
        trigger_line = self.trigger.to_summary()

        # Only include health alerts when something is actually wrong
        health_line = ""
        if self.health.has_critical_issues or self.health.needs_pivot:
            health_line = f"\n{self.health.to_summary()}\n"

        return f"[Trigger] {trigger_line}{health_line}\n\n{work_plan_snapshot}"

