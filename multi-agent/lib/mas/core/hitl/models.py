"""
Human-in-the-Loop domain models.

Pure value objects with no infrastructure dependencies.
These define the vocabulary for all HITL interactions across the system.
"""
import uuid
from dataclasses import dataclass, field
from enum import Enum


class HITLMode(str, Enum):
    """Per-node HITL activation mode (set at blueprint / config time).

    ASK     — always gate tool calls through human approval.
    SKIP    — never gate; tools execute without approval.
    DYNAMIC — decide at runtime based on ``hitl_enabled`` in ExecutionContext tags.
    """
    ASK = "ask"
    SKIP = "skip"
    DYNAMIC = "dynamic"


class ToolAccessMode(Enum):
    """Declares a tool's side-effect profile.

    Used by ToolApprovalPolicy to decide whether human approval is required.
    Tools default to READ; concrete tools override as appropriate.
    """
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class ApprovalType(Enum):
    """Categorises the kind of approval being requested.

    Allows the UI to render different approval dialogs and allows
    policies to apply type-specific rules in the future.
    """
    TOOL_EXECUTION = "tool_execution"
    AGENT_ACTION = "agent_action"
    NODE_TRANSITION = "node_transition"
    HUMAN_INPUT = "human_input"


class ApprovalDecision(Enum):
    """The four possible human decisions on an approval request."""
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    REDIRECT = "redirect"


@dataclass(frozen=True)
class RequestOrigin:
    """Identifies who is asking for approval — immutable."""
    node_uid: str
    node_display_name: str
    session_id: str


@dataclass(frozen=True)
class ApprovalRequest:
    """Immutable request for human approval."""
    request_id: str
    type: ApprovalType
    origin: RequestOrigin
    tool_name: str
    tool_args: dict
    tool_description: str
    tool_access_mode: ToolAccessMode
    reasoning: str = ""

    @staticmethod
    def generate_id() -> str:
        return f"apr-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class ApprovalResponse:
    """Immutable human decision."""
    request_id: str
    decision: ApprovalDecision
    feedback: str = ""
    modified_args: dict = field(default_factory=dict)

    @property
    def approved(self) -> bool:
        return self.decision in (
            ApprovalDecision.APPROVE,
            ApprovalDecision.MODIFY,
        )


@dataclass(frozen=True)
class HITLConfig:
    """Global HITL settings — one instance per session.

    ``timeout_decision`` controls what happens when no human responds
    within ``timeout_seconds``.  Defaults to REJECT so that unanswered
    requests fail safe rather than executing silently.
    """
    enabled: bool = False
    timeout_seconds: float = 300.0
    timeout_decision: ApprovalDecision = ApprovalDecision.REJECT
    timeout_feedback: str = "Approval timed out — no human operator responded"


# ── Approval policy ───────────────────────────────────────────────

_APPROVAL_REQUIRED = frozenset({ToolAccessMode.WRITE, ToolAccessMode.DESTRUCTIVE})


class ToolApprovalPolicy:
    """Concrete domain policy — WRITE and DESTRUCTIVE tools need approval.

    Pure predicate with no I/O.  Instantiate directly; no abstract base
    needed because this is domain logic, not an infrastructure concern.
    """

    def requires_approval(
        self,
        tool_name: str,
        tool_access_mode: ToolAccessMode,
    ) -> bool:
        return tool_access_mode in _APPROVAL_REQUIRED


# ── Auto-approval rules ───────────────────────────────────────────

@dataclass(frozen=True)
class ApprovalRuleSet:
    """A set of auto-resolution rules for one scope (global or per-node).

    Immutable value object — construct a new instance to change rules.
    Resolution order: approve_all > tool-level approve > reject_all > tool-level reject.
    """
    approve_all: bool = False
    reject_all: bool = False
    auto_approve_tools: frozenset = field(default_factory=frozenset)
    auto_reject_tools: frozenset = field(default_factory=frozenset)

    def resolve(
        self,
        tool_name: str,
        tool_access_mode: ToolAccessMode,
    ) -> ApprovalDecision | None:
        """Return a decision if a rule matches, or ``None`` to fall through."""
        if self.approve_all:
            return ApprovalDecision.APPROVE
        if tool_name in self.auto_approve_tools:
            return ApprovalDecision.APPROVE
        if self.reject_all:
            return ApprovalDecision.REJECT
        if tool_name in self.auto_reject_tools:
            return ApprovalDecision.REJECT
        return None

    def to_dict(self) -> dict:
        return {
            "approve_all": self.approve_all,
            "reject_all": self.reject_all,
            "auto_approve_tools": sorted(self.auto_approve_tools),
            "auto_reject_tools": sorted(self.auto_reject_tools),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ApprovalRuleSet":
        if not data:
            return cls()
        return cls(
            approve_all=data.get("approve_all", False),
            reject_all=data.get("reject_all", False),
            auto_approve_tools=frozenset(data.get("auto_approve_tools", [])),
            auto_reject_tools=frozenset(data.get("auto_reject_tools", [])),
        )


@dataclass(frozen=True)
class ApprovalOverrides:
    """Per-session approval rules with node-level granularity.

    Resolution priority: node-specific rules checked first, then
    global rules.  Returns ``None`` when no rule matches (delegate
    to the real gate for human interaction).
    """
    global_rules: ApprovalRuleSet = field(default_factory=ApprovalRuleSet)
    node_rules: dict = field(default_factory=dict)

    def resolve(
        self,
        tool_name: str,
        tool_access_mode: ToolAccessMode,
        node_uid: str,
    ) -> ApprovalDecision | None:
        node_ruleset = self.node_rules.get(node_uid)
        if node_ruleset is not None:
            decision = node_ruleset.resolve(tool_name, tool_access_mode)
            if decision is not None:
                return decision
        return self.global_rules.resolve(tool_name, tool_access_mode)

    def to_dict(self) -> dict:
        return {
            "global_rules": self.global_rules.to_dict(),
            "node_rules": {
                uid: rs.to_dict() for uid, rs in self.node_rules.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ApprovalOverrides":
        if not data:
            return cls()
        return cls(
            global_rules=ApprovalRuleSet.from_dict(
                data.get("global_rules", {}),
            ),
            node_rules={
                uid: ApprovalRuleSet.from_dict(rs)
                for uid, rs in data.get("node_rules", {}).items()
            },
        )
