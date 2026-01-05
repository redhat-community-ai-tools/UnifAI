from elements.common.base_element_spec import BaseElementSpec
from core.enums import ResourceCategory
from elements.nodes.custom_agent.config import CustomAgentNodeConfig
from elements.nodes.custom_agent.custom_agent import CustomAgentNode
from elements.nodes.custom_agent.custom_agent_node_factory import CustomAgentNodeFactory
from elements.nodes.custom_agent.identifiers import Identifier, META
from elements.nodes.custom_agent.validator import CustomAgentNodeValidator


class CustomAgentNodeElementSpec(BaseElementSpec):
    """Element specification for Custom Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = CustomAgentNodeConfig
    factory_cls = CustomAgentNodeFactory
    reads = CustomAgentNode.total_reads()
    writes = CustomAgentNode.total_writes()
    tags = META.tags
    validator_cls = CustomAgentNodeValidator
