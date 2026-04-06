"""
Orchestrator context system for rich, context-aware orchestration.

Provides specialized analyzers and models for understanding:
- Why cycles are triggered
- User intent (new task vs follow-up)
- Work plan health (futility, stalls, blocked items)
- Progress metrics across cycles
- Phase transition history
"""

from .models import (
    CycleTriggerReason,
    CycleTrigger,
    PendingCycle,
    TriggerEvent,
    OrchestratorCycle,
    FutilityIndicator,
    ProgressMetrics,
    WorkPlanHealth,
    PhaseTransition,
    PhaseHistory,
    OrchestratorContext
)

from .analyzers import (
    HealthAnalyzer,
    ProgressTracker
)

from .builder import OrchestratorContextBuilder
from .snapshot import IterationSnapshot

__all__ = [
    # Enums
    'CycleTriggerReason',
    
    # Models
    'CycleTrigger',
    'PendingCycle',
    'TriggerEvent',
    'OrchestratorCycle',
    'FutilityIndicator',
    'ProgressMetrics',
    'WorkPlanHealth',
    'PhaseTransition',
    'PhaseHistory',
    'OrchestratorContext',
    
    # Analyzers
    'HealthAnalyzer',
    'ProgressTracker',
    
    # Builder
    'OrchestratorContextBuilder',

    # Snapshot
    'IterationSnapshot',
]

