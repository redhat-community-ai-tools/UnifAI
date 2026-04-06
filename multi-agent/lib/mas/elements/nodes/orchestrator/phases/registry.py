"""
Ordered, immutable collection of initialized Phase objects.

The registry is the single container that the provider, machine, and
formatter use to look up phase-specific behaviour.
"""

from typing import Dict, List, Optional, Set

from mas.elements.tools.common.base_tool import BaseTool
from .base import Phase, PhaseDependencies


class OrchestratorPhaseRegistry:
    """
    Ordered collection of phases, initialized with shared dependencies.

    Created once per orchestration cycle. Immutable after construction.
    """

    def __init__(self, phases: List[Phase], deps: PhaseDependencies):
        for phase in phases:
            phase.initialize(deps)
        self._ordered = phases
        self._by_name: Dict[str, Phase] = {p.name: p for p in phases}

    def get(self, name: str) -> Optional[Phase]:
        return self._by_name.get(name)

    def names(self) -> List[str]:
        return [p.name for p in self._ordered]

    def initial(self) -> Phase:
        return self._ordered[0]

    def terminal(self) -> Phase:
        for p in self._ordered:
            if p.is_terminal:
                return p
        return self._ordered[-1]

    def all_tools(self) -> Set[BaseTool]:
        """All tools across all phases (for executor registration)."""
        tools: Set[BaseTool] = set()
        for p in self._ordered:
            tools.update(p.tools)
        return tools
