"""
A2A Agent Node Specification
"""

from elements.common.base_element_spec import BaseElementSpec
from core.enums import ResourceCategory
from ..config import A2AAgentNodeConfig
from ..a2a_agent_node import A2AAgentNode
from ..a2a_agent_node_factory import A2AAgentNodeFactory
from ..identifiers import Identifier, META


class A2AAgentNodeElementSpec(BaseElementSpec):
    """Element specification for A2A Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = A2AAgentNodeConfig
    factory_cls = A2AAgentNodeFactory
    reads = A2AAgentNode.total_reads()
    writes = A2AAgentNode.total_writes()
    tags = META.tags

