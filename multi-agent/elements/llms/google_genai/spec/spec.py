from elements.common.base_element_spec import BaseElementSpec
from ..google_genai_factory import GoogleGenAIFactory
from core.enums import ResourceCategory
from ..config import GoogleGenAIConfig
from ..identifiers import Identifier, META
from ..validator import GoogleGenAIValidator


class GoogleGenAIElementSpec(BaseElementSpec):
    """
    Element specification for Google Generative AI (Gemini) LLM.

    Provides all metadata needed for UI integration and runtime configuration.
    """
    category = ResourceCategory.LLM
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = GoogleGenAIConfig
    factory_cls = GoogleGenAIFactory
    tags = META.tags
    validator_cls = GoogleGenAIValidator

