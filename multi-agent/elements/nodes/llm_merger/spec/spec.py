from elements.common.base_element_spec import BaseElementSpec
from core.enums import ResourceCategory
from ..config import MergerLLMNodeConfig
from ..llm_merger_node_factory import LLMMergerNodeFactory
from ..llm_merger import LLMMergerNode
from ..identifiers import Identifier, META
from ..validator import LLMMergerNodeValidator


class LLMMergerNodeElementSpec(BaseElementSpec):
    """Element specification for LLM Merger Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = MergerLLMNodeConfig
    factory_cls = LLMMergerNodeFactory
    reads = LLMMergerNode.total_reads()
    writes = LLMMergerNode.total_writes()
    tags = META.tags
    validator_cls = LLMMergerNodeValidator
