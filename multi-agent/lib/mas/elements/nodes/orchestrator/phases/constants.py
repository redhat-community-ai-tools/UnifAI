"""
Single source of truth for orchestrator phase names.

Every module that needs phase names imports from here.
No more duplicate definitions.
"""

from enum import Enum
from typing import List


class OrchestratorPhase(str, Enum):
    """Orchestrator execution phases (4-phase model)."""
    PLANNING = "planning"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    SYNTHESIS = "synthesis"

    @classmethod
    def ordered(cls) -> List["OrchestratorPhase"]:
        return [cls.PLANNING, cls.EXECUTION, cls.MONITORING, cls.SYNTHESIS]

    @classmethod
    def terminal(cls) -> "OrchestratorPhase":
        return cls.SYNTHESIS
