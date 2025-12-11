from typing import ClassVar
from elements.common.base_element_spec import BaseElementSpec
from core.enums import ResourceCategory
from ..config import DataflowProviderConfig
from ..dataflow_provider_factory import DataflowProviderFactory
from ..identifiers import Identifier, META


class DataflowProviderElementSpec(BaseElementSpec):
    """
    Element specification for Dataflow Provider.

    Provides vector database query and document retrieval capabilities
    via the Dataflow service.
    """

    category: ClassVar[ResourceCategory] = ResourceCategory.PROVIDER
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = DataflowProviderConfig
    factory_cls = DataflowProviderFactory
    tags = META.tags

