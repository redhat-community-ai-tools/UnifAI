from typing import ClassVar
from elements.common.base_element_spec import BaseElementSpec
from core.enums import ResourceCategory
from ..config import DocsDataflowRetrieverConfig
from ..docs_dataflow_retriever_factory import DocsDataflowRetrieverFactory
from ..identifiers import Identifier, META
from ..validator import DocsDataflowRetrieverValidator


class DocsDataflowRetrieverElementSpec(BaseElementSpec):
    """
    Element specification for Docs Dataflow Retriever.

    Retrieves document passages via Dataflow vector database.
    """

    category: ClassVar[ResourceCategory] = ResourceCategory.RETRIEVER
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = DocsDataflowRetrieverConfig
    factory_cls = DocsDataflowRetrieverFactory
    tags = META.tags
    validator_cls = DocsDataflowRetrieverValidator

