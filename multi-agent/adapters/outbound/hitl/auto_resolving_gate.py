"""
Decorator that auto-resolves approval requests using shared rules.

Wraps any ``ApprovalGate`` and intercepts ``request_approval``:
  - Reads ``ApprovalOverrides`` from the injected ``OverridesStore``
    (Redis-backed, so updates from the API are visible cross-process).
  - If a matching rule exists, an instant ``ApprovalResponse`` is
    returned without blocking.
  - Otherwise the call is forwarded to the inner gate (which may
    emit a channel event and block until a human responds).

Thread-safety: each ``request_approval`` call reads a fresh snapshot
from the store.  No mutable shared state on this object.
"""
import logging
from typing import Optional

from mas.core.hitl.models import (
    ApprovalRequest,
    ApprovalResponse,
    HITLConfig,
)
from mas.core.hitl.ports import ApprovalGate, OverridesStore

logger = logging.getLogger(__name__)


class AutoResolvingApprovalGate(ApprovalGate):
    """Decorator: auto-resolves when rules match, delegates otherwise."""

    def __init__(
        self,
        inner: ApprovalGate,
        overrides_store: OverridesStore,
        session_id: str,
        config: HITLConfig,
    ) -> None:
        super().__init__(config)
        self._inner = inner
        self._overrides_store = overrides_store
        self._session_id = session_id

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        overrides = self._overrides_store.load(self._session_id)
        logger.debug(
            "HITL auto-resolve check: tool=%s, node_uid=%s, overrides=%s",
            request.tool_name,
            request.origin.node_uid,
            overrides.to_dict(),
        )
        decision = overrides.resolve(
            tool_name=request.tool_name,
            tool_access_mode=request.tool_access_mode,
            node_uid=request.origin.node_uid,
        )
        if decision is not None:
            logger.info(
                "HITL auto-resolved: tool=%s, node=%s (%s), decision=%s",
                request.tool_name,
                request.origin.node_display_name,
                request.origin.node_uid,
                decision.value,
            )
            return ApprovalResponse(
                request_id=request.request_id,
                decision=decision,
                feedback=f"auto-{decision.value} by session rule",
            )
        logger.debug(
            "HITL no matching rule — forwarding to inner gate: tool=%s, node_uid=%s",
            request.tool_name,
            request.origin.node_uid,
        )
        return self._inner.request_approval(request)

    def _send_and_wait(
        self,
        request: ApprovalRequest,
        timeout: float,
    ) -> Optional[ApprovalResponse]:
        return self._inner._send_and_wait(request, timeout)
