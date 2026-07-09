from mas.elements.common.base_element_spec import BaseElementSpec
from ..anthropic_factory import AnthropicFactory
from mas.core.enums import ResourceCategory
from ..config import AnthropicConfig
from ..identifiers import Identifier, META
from ..validator import AnthropicValidator


class AnthropicElementSpec(BaseElementSpec):
    """
    Element specification for Anthropic (Claude) LLM.

    Provides all metadata needed for UI integration and runtime configuration.
    """
    category = ResourceCategory.LLM
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = AnthropicConfig
    factory_cls = AnthropicFactory
    tags = META.tags
    validator_cls = AnthropicValidator
