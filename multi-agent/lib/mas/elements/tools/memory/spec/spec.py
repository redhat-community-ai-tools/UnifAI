from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import MemoryToolConfig
from ..identifiers import Identifier, META
from ..memory_factory import MemoryToolFactory


class MemoryToolElementSpec(BaseElementSpec):

    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = MemoryToolConfig
    factory_cls = MemoryToolFactory
    tags = META.tags
