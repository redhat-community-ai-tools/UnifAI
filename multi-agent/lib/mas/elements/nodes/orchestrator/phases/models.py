"""
Generic phase iteration models.

Dict-based so adding a new phase never requires changing these classes.
"""

from pydantic import BaseModel, Field
from typing import Dict


_DEFAULT_LIMIT = 10


class PhaseIterationLimits(BaseModel):
    """Max iterations allowed per phase. Generic dict — any phase name works."""
    limits: Dict[str, int] = Field(
        default_factory=lambda: {
            "planning": _DEFAULT_LIMIT,
            "execution": _DEFAULT_LIMIT,
            "monitoring": _DEFAULT_LIMIT,
            "synthesis": _DEFAULT_LIMIT,
        }
    )
    default_limit: int = _DEFAULT_LIMIT

    def get_limit(self, phase_name: str) -> int:
        return self.limits.get(phase_name, self.default_limit)


class PhaseIterationState(BaseModel):
    """Current iteration counts per phase. Immutable-update pattern."""
    counts: Dict[str, int] = Field(default_factory=dict)

    def get_count(self, name: str) -> int:
        return self.counts.get(name, 0)

    def increment(self, name: str) -> "PhaseIterationState":
        new = dict(self.counts)
        new[name] = new.get(name, 0) + 1
        return PhaseIterationState(counts=new)

    def reset(self, name: str) -> "PhaseIterationState":
        new = dict(self.counts)
        new[name] = 0
        return PhaseIterationState(counts=new)

    def is_exceeded(self, name: str, limits: PhaseIterationLimits) -> bool:
        return self.get_count(name) >= limits.get_limit(name)
