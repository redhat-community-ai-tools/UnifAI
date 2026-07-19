"""
Node Capability Binding System — runtime phase.

Centralises all per-execution injection/removal of capabilities
(streaming channel, HITL gate/policy, …) into a single binder
that uses capability protocols from ``contracts.py``.

Components
----------
CapabilitySlot
    Self-contained descriptor for one bindable capability.
    Knows how to check, apply, and remove itself from a node.

NodeRuntimeBindings
    Frozen value object carrying ALL runtime values for one
    execution run.  Created by the runner, consumed by the binder.

NodeRuntimeBinder
    Registration-based orchestrator.  Iterates registered slots
    and applies/removes bindings via protocol checks.

Adding a new runtime capability
-------------------------------
1. Add a ``@runtime_checkable Protocol`` in ``contracts.py``.
2. Add a field to ``NodeRuntimeBindings``.
3. Create a ``CapabilitySlot`` instance.
4. Append ``(slot, extractor)`` to ``_DEFAULT_ENTRIES``.
"""

from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, TypeVar

from mas.core.channels import SessionChannel
from mas.core.contracts import SupportsHITL, SupportsStreamingChannel
from mas.core.enums import ResourceCategory
from mas.core.hitl.models import ToolApprovalPolicy
from mas.core.hitl.ports import ApprovalGate

T = TypeVar("T")


# ── CapabilitySlot ────────────────────────────────────────────

@dataclass(frozen=True)
class CapabilitySlot(Generic[T]):
    """One bindable runtime capability.

    Self-contained: knows which protocol to check, how to apply a
    value, and how to clean up.  The binder iterates slots without
    any ``if/elif`` chains.
    """

    protocol: type
    apply_fn: Callable[[Any, T], None]
    remove_fn: Callable[[Any], None]

    def supports(self, node: Any) -> bool:
        return isinstance(node, self.protocol)

    def apply(self, node: Any, value: T) -> None:
        if self.supports(node) and value is not None:
            self.apply_fn(node, value)

    def remove(self, node: Any) -> None:
        if self.supports(node):
            self.remove_fn(node)


# ── Pre-defined slots ────────────────────────────────────────

STREAMING: CapabilitySlot = CapabilitySlot(
    protocol=SupportsStreamingChannel,
    apply_fn=lambda n, ch: n.set_streaming_channel(ch),
    remove_fn=lambda n: n.set_streaming_channel(None),
)

HITL_GATE: CapabilitySlot = CapabilitySlot(
    protocol=SupportsHITL,
    apply_fn=lambda n, g: n.set_approval_gate(g),
    remove_fn=lambda n: n.set_approval_gate(None),
)

HITL_POLICY: CapabilitySlot = CapabilitySlot(
    protocol=SupportsHITL,
    apply_fn=lambda n, p: n.set_approval_policy(p),
    remove_fn=lambda n: n.set_approval_policy(None),
)


# ── NodeRuntimeBindings ─────────────────────────────────────

@dataclass(frozen=True)
class NodeRuntimeBindings:
    """Immutable snapshot of everything a node receives per execution run."""

    channel: Optional[SessionChannel] = None
    approval_gate: Optional[ApprovalGate] = None
    approval_policy: Optional[ToolApprovalPolicy] = None


# ── NodeRuntimeBinder ────────────────────────────────────────

# Each entry is (slot, extractor_from_bindings).
_SlotEntry = tuple[CapabilitySlot, Callable[[NodeRuntimeBindings], Any]]

_DEFAULT_ENTRIES: list[_SlotEntry] = [
    (STREAMING, lambda b: b.channel),
    (HITL_GATE, lambda b: b.approval_gate),
    (HITL_POLICY, lambda b: b.approval_policy),
]


class NodeRuntimeBinder:
    """Applies and removes runtime capabilities to/from nodes.

    Registration-based: new capabilities are added via ``register()``
    without modifying existing code (OCP).  The ``default()`` factory
    returns a binder pre-loaded with all standard capabilities.
    """

    def __init__(self, entries: Optional[list] = None) -> None:
        self._entries: list[_SlotEntry] = list(entries or [])

    def register(self, slot: CapabilitySlot, extractor: Callable[[NodeRuntimeBindings], Any]) -> None:
        """Add a new runtime capability (OCP entry point)."""
        self._entries.append((slot, extractor))

    # ── Single-node operations ────────────────────────────────

    def bind(self, node: Any, bindings: NodeRuntimeBindings) -> None:
        for slot, extract in self._entries:
            slot.apply(node, extract(bindings))

    def unbind(self, node: Any) -> None:
        for slot, _ in self._entries:
            slot.remove(node)

    # ── Registry-wide operations ──────────────────────────────

    def bind_all(self, registry: Any, bindings: NodeRuntimeBindings) -> None:
        for node in registry.all_of(ResourceCategory.NODE).values():
            self.bind(node, bindings)

    def unbind_all(self, registry: Any) -> None:
        for node in registry.all_of(ResourceCategory.NODE).values():
            self.unbind(node)

    # ── Factory ───────────────────────────────────────────────

    @classmethod
    def default(cls) -> "NodeRuntimeBinder":
        """Create a binder pre-loaded with all standard capabilities."""
        return cls(entries=list(_DEFAULT_ENTRIES))
