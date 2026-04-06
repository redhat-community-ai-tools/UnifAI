"""Synthesis phase — create final answer from all completed work."""

from typing import Any, List

from mas.elements.tools.common.base_tool import BaseTool

from .constants import OrchestratorPhase
from .base import Phase, PhaseDependencies, PlanSnapshotMode, PromptContext
from .validators import SynthesisValidator


class SynthesisPhase(Phase):
    name = OrchestratorPhase.SYNTHESIS
    is_terminal = True
    snapshot_mode = PlanSnapshotMode.FULL

    def create_tools(self, deps: PhaseDependencies) -> List[BaseTool]:
        return []

    def get_guidance(self) -> str:
        return (
            "SYNTHESIS: Create final answer from all completed work.\n\n"
            "- Review ALL items (DONE results, FAILED learnings, IN_PROGRESS partials)\n"
            "- Produce a DIRECT TEXT answer — NO tool calls\n"
            "- Start with the direct answer, then supporting details\n"
            "- Be transparent about completeness and confidence\n"
            "- Extract value even from failures — they contain information"
        )

    def create_validator(self):
        return SynthesisValidator()

    def decide_next(self, status: Any) -> str:
        return OrchestratorPhase.SYNTHESIS

    def build_focused_prompt(self, ctx: PromptContext) -> str:
        from ..context.models import CycleTriggerReason

        reason = ctx.trigger_reason
        status = ctx.status
        user_request = ctx.user_request or "the request"
        total = status.total_items
        done = status.done_items
        failed = status.failed_items

        if ctx.phase_changed and status.is_complete and failed == 0:
            return (
                "**SYNTHESIZE COMPLETE RESULTS**\n\n"
                f"All {total} work items completed successfully!\n\n"
                f"Original request: \"{user_request}\"\n\n"
                "Create comprehensive final response.\n\n"
                "**Include:**\n"
                "1. Direct answer to user's request\n"
                "2. Summary of what was accomplished\n"
                "3. Key findings or results from work items\n"
                "4. Any important details or context\n\n"
                "Then finish to return response to user."
            )

        if ctx.phase_changed and (done > 0 or failed > 0):
            return (
                "**SYNTHESIZE PARTIAL RESULTS**\n\n"
                f"Work summary: {done}/{total} done, {failed} failed.\n\n"
                f"Original request: \"{user_request}\"\n\n"
                "Create honest, transparent response.\n\n"
                "**Include:**\n"
                "1. What was successfully accomplished (from DONE items)\n"
                "2. What couldn't be completed and why (from FAILED items)\n"
                "3. Whether partial results answer the request\n"
                "4. Suggestions for next steps if applicable\n\n"
                "Be transparent about limitations.\nThen finish."
            )

        if ctx.phase_changed and done == 0 and total > 0:
            if failed == total:
                return (
                    "**SYNTHESIZE FAILURE RESULTS**\n\n"
                    f"Unable to complete any of {total} work items.\n\n"
                    f"Original request: \"{user_request}\"\n\n"
                    "Explain what went wrong.\n\n"
                    "**Include:**\n"
                    "1. Clear explanation of why work couldn't be completed\n"
                    "2. What was attempted\n"
                    "3. Suggestions for alternative approaches\n\n"
                    "Then finish."
                )
            return (
                "**EARLY SYNTHESIS**\n\n"
                "Entered SYNTHESIS but work is still in progress.\n\n"
                "Provide interim update or explain current status.\nThen finish."
            )

        if reason == CycleTriggerReason.NEW_REQUEST:
            return (
                "**USER FOLLOW-UP IN SYNTHESIS**\n\n"
                f"User asked: \"{user_request}\"\n\n"
                "Options:\n"
                "- If clarification -> Answer directly and finish\n"
                "- If needs new work -> Suggest returning to PLANNING"
            )

        if not ctx.phase_changed:
            return (
                "**CONTINUE SYNTHESIS**\n\n"
                "Refine your response or add more context.\n"
                "Finish when response is complete.\n\n"
                f"Original request: \"{user_request}\""
            )

        return (
            "Synthesize results and create final response for the user. "
            "Review completed work items and formulate a comprehensive answer."
        )
