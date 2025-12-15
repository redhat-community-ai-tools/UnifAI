from typing import Any
from elements.common.base_factory import BaseFactory
from elements.common.exceptions import PluginConfigurationError
from elements.llms.google_genai.config import GoogleGenAIConfig
from elements.llms.google_genai.google_genai import GoogleGenAILLM
from elements.llms.google_genai.identifiers import Identifier


class GoogleGenAIFactory(BaseFactory[GoogleGenAIConfig, GoogleGenAILLM]):
    """
    Factory for creating Google Generative AI LLM instances.

    Validates configuration and creates GoogleGenAILLM with API key, model, etc.
    """

    def accepts(self, cfg: GoogleGenAIConfig, element_type: str) -> bool:
        """
        Recognize configs with 'type': 'google_genai'.
        """
        return element_type == Identifier.TYPE

    def create(self, cfg: GoogleGenAIConfig, **deps: Any) -> GoogleGenAILLM:
        """
        Validate cfg and return a connected GoogleGenAILLM.

        :param cfg: config with keys:
            - type == "google_genai"
            - model_name (str)
            - api_key (str)
            - temperature (float, optional)
            - max_tokens (int, optional)
            - top_p (float, optional)
            - top_k (int, optional)
        :raises PluginConfigurationError: on validation failure
        """
        try:
            llm = GoogleGenAILLM(
                model_name=cfg.model_name,
                api_key=cfg.api_key,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                top_p=cfg.top_p,
                top_k=cfg.top_k,
                **cfg.extra
            )
            return llm
        except Exception as e:
            raise PluginConfigurationError(f"Failed to create Google GenAI LLM: {e}", cfg) from e

