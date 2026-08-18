from mas.elements.nodes.common.base_node import BaseNode
import logging
from global_utils.utils.logging_config import emit
from mas.graph.state.graph_state import Channel
from mas.graph.state.state_view import StateView
from typing import Optional

logger = logging.getLogger(__name__)


class BranchChooserNode(BaseNode):
    """
    Mock node that looks at target branches from step context and chooses the first one.
    Writes the chosen branch to the target_branch state channel.
    """
    READS = set()  # We don't read from state channels, we read from step context
    WRITES = {"target_branch"}  # Write to the target_branch channel

    def __init__(self,
                 *,
                 default_branch: Optional[str] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.default_branch = default_branch

    def run(self, state: StateView) -> StateView:
        # Get target branches from step context
        chosen_branch = None

        try:
            context = self.get_context()
            if context.branches:
                # Get the first branch from the step context branches
                first_branch_key = next(iter(context.branches.keys()), None)

                if first_branch_key:
                    chosen_branch = context.branches[first_branch_key]
        except RuntimeError:
            pass

        # Fall back to default branch if no branches found
        if chosen_branch is None:
            chosen_branch = self.default_branch or "default_branch"

        emit(logger, logging.INFO, "graph.branch_chosen", chosen_branch=chosen_branch)
        # Write the chosen branch to the target_branch state channel
        state["target_branch"] = chosen_branch
        return state
