"""
Orchestrator context builder - composes rich context from specialized analyzers.

Follows SOLID principles:
- Single Responsibility: Only composes context, delegates analysis to specialists
- Open/Closed: Extensible via analyzer injection
- Dependency Inversion: Depends on abstractions (callable interfaces)
"""

from typing import Optional, Callable
from datetime import datetime, timezone

from mas.elements.llms.common.chat.file_attachment import filter_active_attachments
from .models import (
    OrchestratorContext,
    CycleTrigger,
    CycleTriggerReason,
    PhaseHistory,
    PhaseTransition
)
from .analyzers import HealthAnalyzer, ProgressTracker


class OrchestratorContextBuilder:
    """
    Composes orchestrator context from specialized analyzers.
    
    Design:
    - Builder is stateless except for history tracking
    - Analysis delegated to injected services
    - All state (progress, etc.) managed by analyzer instances
    - Created once in orchestrator __init__, persists across cycles
    """
    
    def __init__(
        self,
        get_workload_service: Callable,
        node_uid: str,
        thread_id: str,
        health_analyzer: Optional[HealthAnalyzer] = None,
        progress_tracker: Optional[ProgressTracker] = None
    ):
        """
        Initialize context builder with dependencies.
        
        Args:
            get_workload_service: Function to get workload service
            node_uid: Node identifier
            thread_id: Thread identifier
            health_analyzer: Optional custom health analyzer
            progress_tracker: Optional custom progress tracker
        """
        self._get_workload_service = get_workload_service
        self._node_uid = node_uid
        self._thread_id = thread_id
        
        # Inject or use defaults
        self._health_analyzer = health_analyzer or HealthAnalyzer()
        self._progress_tracker = progress_tracker or ProgressTracker()
        
        # Minimal state: history tracking
        self._history = PhaseHistory()
    
    def build_context(
        self, 
        trigger: CycleTrigger, 
        phase_state: any
    ) -> OrchestratorContext:
        """
        Build complete orchestrator context.
        
        Composes context from specialized analyzers with no business logic here.
        Pure composition - all analysis delegated to specialists.
        
        Args:
            trigger: Why this cycle is running
            phase_state: Current phase state from phase system
        
        Returns:
            Complete OrchestratorContext
        """
        # Load work plan
        # Note: self._get_workload_service() already returns the workspace service
        workspace_service = self._get_workload_service()
        plan = workspace_service.load_work_plan(self._thread_id, self._node_uid)
        
        # Delegate to specialists
        health = self._health_analyzer.analyze(plan)
        
        # Update progress metrics
        progress = self._progress_tracker.update(plan)
        health.progress_metrics = progress  # Enrich health with progress
        
        # Get current history
        history = self._history
        
        raw_attachments = workspace_service.get_variable(
            self._thread_id, "file_attachments", []
        ) or []
        
        return OrchestratorContext(
            trigger=trigger,
            health=health,
            history=history,
            phase_state=phase_state,
            file_attachments=filter_active_attachments(raw_attachments),
        )
    
    def record_phase_transition(
        self, 
        from_phase: str, 
        to_phase: str, 
        reason: str = ""
    ):
        """
        Record a phase transition for history tracking.
        
        Args:
            from_phase: Phase transitioning from
            to_phase: Phase transitioning to
            reason: Reason for the transition
        """
        transition = PhaseTransition(
            from_phase=from_phase,
            to_phase=to_phase,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            actions_taken=[]
        )
        
        self._history.current_cycle_transitions.append(transition)
        
        # Update iteration counts
        if to_phase not in self._history.phase_iteration_counts:
            self._history.phase_iteration_counts[to_phase] = 0
        self._history.phase_iteration_counts[to_phase] += 1
    
    def reset_for_new_cycle(self):
        """Reset cycle-specific state (call at cycle start)."""
        self._history.current_cycle_transitions = []

