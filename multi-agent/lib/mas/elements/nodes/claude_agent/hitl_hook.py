"""HITL hook for Claude Agent SDK — bridges the ``PreToolUse`` hook
to our domain ``ApprovalGate`` / ``ToolApprovalPolicy``.

Delegates the resolve → check → request flow to ``HITLToolGatekeeper``
(shared with ``HITLExecutionHandler`` and ``HITLMiddleware``).  This
adapter is responsible only for translating gatekeeper results into the
``HookJSONOutput`` dict that the Claude SDK expects.

Claude Code comes with built-in tools (``Read``, ``Write``, ``Bash``,
etc.) that are NOT in our domain tool registry.
``CLAUDE_BUILTIN_ACCESS_MODES`` maps these to the correct
``ToolAccessMode`` so they are properly gated.

The hook callback is async (Claude SDK requirement).  Since
``ApprovalGate.request_approval`` is synchronous (blocks on Redis),
we bridge via ``asyncio.to_thread``.
"""
import asyncio
import logging
from typing import Any, Dict

from mas.core.hitl.models import ApprovalDecision, ToolAccessMode
from mas.elements.nodes.common.capabilities.hitl_gatekeeper import HITLToolGatekeeper

logger = logging.getLogger(__name__)

_MCP_SERVER_PREFIX = "mas-tools__"

CLAUDE_BUILTIN_ACCESS_MODES: Dict[str, ToolAccessMode] = {
    "Read": ToolAccessMode.READ,
    "Grep": ToolAccessMode.READ,
    "Glob": ToolAccessMode.READ,
    "LS": ToolAccessMode.READ,
    "WebSearch": ToolAccessMode.READ,
    "WebFetch": ToolAccessMode.READ,
    "TodoRead": ToolAccessMode.READ,
    "Write": ToolAccessMode.WRITE,
    "Edit": ToolAccessMode.WRITE,
    "MultiEdit": ToolAccessMode.WRITE,
    "TodoWrite": ToolAccessMode.WRITE,
    "Bash": ToolAccessMode.DESTRUCTIVE,
    "Task": ToolAccessMode.WRITE,
}


class HITLHook:
    """Callable that implements the Claude SDK ``HookCallback`` protocol.

    Registered as a ``PreToolUse`` hook via ``HookMatcher``.  Fires
    before every tool call regardless of ``permission_mode``.

    Decision mapping (our domain → Claude SDK):
      APPROVE  → permissionDecision: "allow"
      MODIFY   → permissionDecision: "allow" + updatedInput
      REJECT   → permissionDecision: "deny"  + reason
      REDIRECT → permissionDecision: "deny"  + reason
    """

    def __init__(self, gatekeeper: HITLToolGatekeeper) -> None:
        self._gatekeeper = gatekeeper

    async def __call__(
        self,
        hook_input: Any,
        tool_use_id: str | None,
        context: Any,
    ) -> dict:
        tool_name = hook_input.get("tool_name", "")
        tool_args = hook_input.get("tool_input", {})

        lookup_name = self._strip_mcp_prefix(tool_name)

        response = await asyncio.to_thread(
            self._gatekeeper.check, lookup_name, tool_args,
        )

        if response is None:
            return self._allow()

        match response.decision:
            case ApprovalDecision.APPROVE:
                return self._allow()

            case ApprovalDecision.MODIFY:
                if response.modified_args:
                    return self._allow(updated_input=response.modified_args)
                return self._allow()

            case ApprovalDecision.REJECT:
                return self._deny(
                    f"Action rejected by human operator. "
                    f"Reason: {response.feedback}. "
                    f"Please choose a safer approach.",
                )

            case ApprovalDecision.REDIRECT:
                return self._deny(
                    f"Human operator instruction: {response.feedback}",
                )

        return self._allow()

    # ------------------------------------------------------------------
    # Response builders
    # ------------------------------------------------------------------

    @staticmethod
    def _allow(*, updated_input: dict | None = None) -> dict:
        output: dict = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
        if updated_input:
            output["updatedInput"] = updated_input
        return {"hookSpecificOutput": output}

    @staticmethod
    def _deny(reason: str) -> dict:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
            },
            "reason": reason,
        }

    @staticmethod
    def _strip_mcp_prefix(tool_name: str) -> str:
        """Strip the ``mas-tools__`` prefix added by the SDK for MCP tools."""
        if tool_name.startswith(_MCP_SERVER_PREFIX):
            return tool_name[len(_MCP_SERVER_PREFIX):]
        return tool_name
