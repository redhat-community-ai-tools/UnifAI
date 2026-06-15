from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import DeepAgentNodeConfig
from ..deep_agent_node import DeepAgentNode
from ..deep_agent_node_factory import DeepAgentNodeFactory
from ..identifiers import Identifier, META
from ..validator import DeepAgentNodeValidator
from ..card_builder import DeepAgentCardBuilder


class DeepAgentNodeElementSpec(BaseElementSpec):
    """Element specification for Deep Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = DeepAgentNodeConfig
    factory_cls = DeepAgentNodeFactory
    validator_cls = DeepAgentNodeValidator
    card_builder_cls = DeepAgentCardBuilder
    reads = DeepAgentNode.total_reads()
    writes = DeepAgentNode.total_writes()
    tags = META.tags
