from ..common.base_condition import BaseCondition
from ..common.models import ConditionOutputSchema, BranchType, DirectBranchDef
import logging
from mas.graph.state.state_view import StateView
from mas.graph.state.graph_state import Channel
from mas.core.iem.utils import get_outgoing_targets

logger = logging.getLogger(__name__)


class RouterDirectCondition(BaseCondition):
    """
    IEM-based router condition that routes to nodes receiving packets.
    """

    READS = {Channel.INTER_PACKETS}

    def run(self, state: StateView):
        """
        Route to nodes that have been receiving packets from this node.
        
        Returns:
            - Node UID(s) if targets exist
            - END if no targets (graceful termination instead of None crash)
        """
        if not self.context:
            logger.warning("graph.router_no_context")
            return "END"

        targets = get_outgoing_targets(state, self.context)
        logger.debug("graph.router_targets", extra={"targets": list(targets)})
        if not targets:
            logger.warning("graph.router_no_targets")
            return "END"

        if len(targets) == 1:
            return list(targets)[0]

        # Return as tuple for multiple targets
        return tuple(sorted(targets))

    def __repr__(self) -> str:
        return "<RouterDirectCondition: IEM-based routing>"

    @classmethod
    def get_output_schema(cls) -> ConditionOutputSchema:
        """
        RouterDirectCondition returns direct node UIDs based on IEM analysis.
        """
        return ConditionOutputSchema(
            branch_type=BranchType.DIRECT,
            direct_config=DirectBranchDef(
                description="Routes to nodes based on IEM communication patterns"
            ),
            description="IEM-based router that follows actual packet communication"
        )
