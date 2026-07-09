from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.elements.llms.anthropic.config import AnthropicConfig
from mas.elements.llms.anthropic.anthropic import AnthropicLLM
from mas.elements.llms.anthropic.identifiers import Identifier


class AnthropicFactory(BaseFactory[AnthropicConfig, AnthropicLLM]):
    """
    Factory for creating Anthropic (Claude) LLM instances.

    Validates configuration and creates AnthropicLLM with API key, model, etc.
    """

    def accepts(self, cfg: AnthropicConfig, element_type: str) -> bool:
        """
        Recognize configs with 'type': 'anthropic'.
        """
        return element_type == Identifier.TYPE

    def create(self, cfg: AnthropicConfig, **deps: Any) -> AnthropicLLM:
        """
        Validate cfg and return a connected AnthropicLLM.

        :param cfg: config with keys:
            - type == "anthropic"
            - model_name (str)
            - api_key (str)
            - temperature (float, optional)
            - max_tokens (int, optional)
            - top_p (float, optional)
            - top_k (int, optional)
        :raises PluginConfigurationError: on validation failure
        """
        try:
            llm = AnthropicLLM(
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
            raise PluginConfigurationError(f"Failed to create Anthropic LLM: {e}", cfg) from e
