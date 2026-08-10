"""
Concrete ApprovalGateFactory — adapter that assembles the HITL gate stack.

Creates a ``ChannelApprovalGate`` (transport layer) wrapped in an
``AutoResolvingApprovalGate`` (auto-rule decorator) that reads rules
from the shared ``OverridesStore``.

Both foreground and background runners receive this factory via DI
so the domain layer never imports adapter classes.

On ``create()``, initial overrides are loaded from session metadata
and seeded into the ``OverridesStore`` so the gate has a warm cache.
On ``remove()``, the store entry is cleaned up.
"""
import logging
from typing import Any, Optional

from mas.core.channels import InputCapableChannel
from mas.core.hitl.models import (
    ApprovalOverrides,
    HITLConfig,
    ToolApprovalPolicy,
)
from mas.core.hitl.ports import ApprovalGate, ApprovalGateFactory, OverridesStore
from .auto_resolving_gate import AutoResolvingApprovalGate
from .channel_gate import ChannelApprovalGate

logger = logging.getLogger(__name__)


class ChannelApprovalGateFactory(ApprovalGateFactory):
    """Builds a channel-backed gate with auto-resolving decorator.

    Uses a shared ``OverridesStore`` (Redis-backed) so that rule
    updates from the API endpoint are visible to gates in any
    process — foreground Flask threads or Temporal workers.
    """

    def __init__(self, overrides_store: OverridesStore) -> None:
        self._overrides_store = overrides_store

    @property
    def overrides_store(self) -> OverridesStore:
        return self._overrides_store

    def create(
        self,
        channel: Any,
        session_metadata: Any,
        run_id: str,
    ) -> tuple[Optional[ApprovalGate], Optional[ToolApprovalPolicy]]:
        if not isinstance(channel, InputCapableChannel):
            return None, None

        config = HITLConfig(enabled=True)
        inner_gate = ChannelApprovalGate(channel=channel, config=config)

        raw_overrides = getattr(session_metadata, "hitl_overrides", None) or {}
        overrides = ApprovalOverrides.from_dict(raw_overrides)
        self._overrides_store.save(run_id, overrides)

        gate = AutoResolvingApprovalGate(
            inner=inner_gate,
            overrides_store=self._overrides_store,
            session_id=run_id,
            config=config,
        )
        policy = ToolApprovalPolicy()

        logger.info(
            "HITL gate created: run_id=%s, timeout=%ss, default=%s, overrides=%s",
            run_id,
            config.timeout_seconds,
            config.timeout_decision.value,
            overrides.to_dict(),
        )

        return gate, policy

    def remove(self, run_id: str) -> None:
        """Clean up the overrides store entry after a run completes."""
        self._overrides_store.remove(run_id)
