"""
HITL adapter implementations.

ChannelApprovalGate:              ApprovalGate backed by InputCapableChannel.
AutoResolvingApprovalGate:        Decorator that auto-resolves via shared OverridesStore.
ChannelApprovalGateFactory:       ApprovalGateFactory that assembles the full gate stack.
RedisOverridesStore:              OverridesStore backed by Redis for cross-process sync.
"""
from .channel_gate import ChannelApprovalGate
from .auto_resolving_gate import AutoResolvingApprovalGate
from .gate_factory import ChannelApprovalGateFactory
from .redis_overrides_store import RedisOverridesStore

__all__ = [
    "ChannelApprovalGate",
    "AutoResolvingApprovalGate",
    "ChannelApprovalGateFactory",
    "RedisOverridesStore",
]
