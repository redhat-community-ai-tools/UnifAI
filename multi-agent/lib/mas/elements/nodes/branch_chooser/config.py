from typing import Literal, Optional
from pydantic import Field
from mas.elements.nodes.common.base_config import NodeBaseConfig
from mas.core.field_hints import CardHint
from .identifiers import Identifier


class BranchChooserNodeConfig(NodeBaseConfig):
    """
    Configuration for the branch chooser node that selects the first target branch.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    default_branch: Optional[str] = Field(
        None,
        description="Default branch name to use if no target branches are available",
        json_schema_extra=CardHint(contexts=["builtin", "custom"]).to_hints(),
    )