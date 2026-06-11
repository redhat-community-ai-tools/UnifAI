"""
Claude Agent Node Specification
"""

from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import ClaudeAgentNodeConfig
from ..claude_agent_node import ClaudeAgentNode
from ..claude_agent_node_factory import ClaudeAgentNodeFactory
from ..identifiers import Identifier, META
from ..validator import ClaudeAgentNodeValidator
from ..card_builder import ClaudeAgentCardBuilder


class ClaudeAgentNodeElementSpec(BaseElementSpec):
    """Element specification for Claude Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = ClaudeAgentNodeConfig
    factory_cls = ClaudeAgentNodeFactory
    validator_cls = ClaudeAgentNodeValidator
    card_builder_cls = ClaudeAgentCardBuilder
    reads = ClaudeAgentNode.total_reads()
    writes = ClaudeAgentNode.total_writes()
    tags = META.tags
