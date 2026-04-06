"""
Phase abstraction for the orchestrator.

Each orchestrator phase is a class that encapsulates ALL per-phase knowledge:
identity, tools, guidance, validation, routing, focused prompts, and
context preferences.

Adding a new phase = adding one new class. No other files need changing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional

from mas.elements.tools.common.base_tool import BaseTool


class PlanSnapshotMode(str, Enum):
    """Declares what plan data a phase needs in its LLM context."""
    FULL = "full"
    LOCAL_ONLY = "local"
    ATTENTION = "attention"


@dataclass(frozen=True)
class PhaseDependencies:
    """Injected dependencies for phase tool creation. Built once per cycle."""
    get_thread_id: Callable[[], str]
    get_owner_uid: Callable[[], str]
    get_workload_service: Callable[[], Any]
    send_task: Callable[..., Any]
    get_current_thread: Callable[[], Any]
    get_thread_service: Callable[[], Any]
    get_workspace_service: Callable[[], Any]
    check_adjacency: Callable[[str], bool]
    get_adjacent_nodes: Callable[[], Any]
    domain_tools: List[BaseTool] = field(default_factory=list)


@dataclass(frozen=True)
class PromptContext:
    """Everything a phase needs to build its focused prompt."""
    trigger_reason: Any  # CycleTriggerReason or None
    changed_items: List[str]
    plan: Any
    status: Any
    phase_changed: bool
    user_request: str


class Phase(ABC):
    """
    Single orchestrator phase.

    Encapsulates ALL per-phase knowledge in one place:

    Identity:      name, is_terminal
    Behavior:      tools, guidance, validation, routing, focused prompts
    Preferences:   snapshot_mode, needs_node_context, max_iterations
    """

    name: str
    is_terminal: bool = False
    needs_node_context: bool = False
    snapshot_mode: PlanSnapshotMode = PlanSnapshotMode.FULL
    max_iterations: int = 10

    def __init__(self):
        self._tools: List[BaseTool] = []

    def initialize(self, deps: PhaseDependencies) -> None:
        """Create tools with injected dependencies. Called once per cycle."""
        self._tools = self.create_tools(deps)

    @property
    def tools(self) -> List[BaseTool]:
        return self._tools

    # ── Required: subclasses MUST implement ──────────────────

    @abstractmethod
    def create_tools(self, deps: PhaseDependencies) -> List[BaseTool]:
        """Return the tools this phase exposes to the LLM."""
        ...

    @abstractmethod
    def get_guidance(self) -> str:
        """Return the system-prompt guidance block for this phase."""
        ...

    @abstractmethod
    def decide_next(self, status: Any) -> str:
        """Given WorkPlanStatus, return the next phase name."""
        ...

    @abstractmethod
    def build_focused_prompt(self, ctx: PromptContext) -> str:
        """Build the situation-aware focused prompt for this phase."""
        ...

    # ── Optional: subclasses MAY override ────────────────────

    def create_validator(self) -> Optional[Any]:
        """Return a PhaseValidator for this phase, or None."""
        return None

    def on_limit_exceeded(self, status: Any) -> str:
        """Bail-out routing when the iteration limit is hit."""
        from .constants import OrchestratorPhase
        return OrchestratorPhase.SYNTHESIS

    def run_validation(self, context: Any) -> str:
        """Run the phase's validator and return guidance text."""
        v = self.create_validator()
        if not v:
            return ""
        try:
            return v.validate(context)
        except Exception:
            return ""
