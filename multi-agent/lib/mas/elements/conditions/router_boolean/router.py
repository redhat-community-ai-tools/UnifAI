from ..common.base_condition import BaseCondition
from ..common.models import ConditionOutputSchema, BranchType, SymbolicBranchDef
import logging
from global_utils.utils.logging_config import emit
from mas.graph.state.state_view import StateView

logger = logging.getLogger(__name__)


class RouterBooleanCondition(BaseCondition):
    """
    Router boolean condition that returns a configured boolean value.
    Returns True or False based on configuration for symbolic branching.
    """
    
    # Declare what channels this condition reads (none in this case)
    READS = set()

    def __init__(self, boolean_value: bool = True):
        super().__init__()
        self.boolean_value = boolean_value

    def run(self, state: StateView) -> str:
        """
        Returns the configured boolean value.
        """
        emit(logger, logging.DEBUG, "graph.router_boolean", boolean_value=self.boolean_value)
        return str(self.boolean_value).lower()

    def __repr__(self) -> str:
        return f"<RouterBooleanCondition: returns {self.boolean_value}>"

    @classmethod
    def get_output_schema(cls) -> ConditionOutputSchema:
        """
        RouterBooleanCondition returns boolean values (True/False) for symbolic branching.
        """
        return ConditionOutputSchema(
            branch_type=BranchType.SYMBOLIC,
            symbolic_branches=[
                SymbolicBranchDef(
                    name=True,
                    display_name="True",
                    description="Condition returns true"
                ),
                SymbolicBranchDef(
                    name=False,
                    display_name="False",
                    description="Condition returns false"
                )
            ],
            description="Boolean router condition for true/false symbolic branching"
        )