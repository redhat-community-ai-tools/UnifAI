"""
Tool for listing adjacent nodes.
"""

from typing import Dict, Any, Callable
from pydantic import BaseModel
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.nodes.common.agent.constants import ToolNames


class ListAdjacentNodeArgs(BaseModel):
    pass


class ListAdjacentNodesTool(BaseTool):
    """List all adjacent nodes with their capabilities."""

    name = ToolNames.TOPOLOGY_LIST_ADJACENT
    description = "Get a list of all adjacent nodes with their capabilities and skills"
    args_schema = ListAdjacentNodeArgs

    def __init__(self, get_adjacent_nodes: Callable[[], Dict[str, Any]]):
        self._get_adjacent_nodes = get_adjacent_nodes

    def run(self, **kwargs) -> Dict[str, Any]:
        """List adjacent nodes using their ElementCard representation."""
        adjacent_nodes = self._get_adjacent_nodes()

        if not adjacent_nodes:
            return {"adjacent_count": 0, "nodes": []}

        nodes_info = []
        for uid, card in adjacent_nodes.items():
            nodes_info.append({"uid": uid, "card": str(card)})

        return {
            "adjacent_count": len(adjacent_nodes),
            "nodes": nodes_info,
        }
