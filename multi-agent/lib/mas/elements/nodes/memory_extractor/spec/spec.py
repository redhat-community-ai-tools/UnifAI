from typing import ClassVar
from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import MemoryExtractorNodeConfig
from ..memory_extractor_node_factory import MemoryExtractorNodeFactory
from ..memory_extractor import MemoryExtractorNode
from ..identifiers import Identifier, META


class MemoryExtractorNodeElementSpec(BaseElementSpec):
    """Element specification for the Memory Extractor Node."""

    category: ClassVar[ResourceCategory] = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = MemoryExtractorNodeConfig
    factory_cls = MemoryExtractorNodeFactory
    reads = MemoryExtractorNode.total_reads()
    writes = MemoryExtractorNode.total_writes()
    tags = META.tags
