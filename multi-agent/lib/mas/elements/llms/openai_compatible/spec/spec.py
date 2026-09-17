from mas.elements.common.base_element_spec import BaseElementSpec
from ..openai_compatible_factory import OpenAICompatibleFactory
from mas.core.enums import ResourceCategory
from ..config import OpenAICompatibleConfig
from ..identifiers import Identifier, META
from ..validator import OpenAICompatibleLLMValidator


class OpenAICompatibleElementSpec(BaseElementSpec):
    """
    Element specification for OpenAI-compatible LLM.

    Provides all metadata needed for UI integration and runtime configuration.
    """
    category = ResourceCategory.LLM
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = OpenAICompatibleConfig
    factory_cls = OpenAICompatibleFactory
    tags = META.tags
    validator_cls = OpenAICompatibleLLMValidator
