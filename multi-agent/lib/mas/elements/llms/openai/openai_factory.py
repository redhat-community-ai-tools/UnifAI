from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.elements.llms.openai.config import OpenAIConfig
from mas.elements.llms.openai.openai import OpenAILLM
from mas.elements.llms.openai.identifiers import Identifier


class OpenAIFactory(BaseFactory[OpenAIConfig, OpenAILLM]):
    """
    Factory for creating OpenAI LLM instances.

    Validates configuration and creates OpenAILLM with API key, model, etc.
    """

    def accepts(self, cfg: OpenAIConfig, element_type: str) -> bool:
        """
        Recognize configs with 'type': 'openai'.
        """
        return element_type == Identifier.TYPE

    def create(self, cfg: OpenAIConfig, **deps: Any) -> OpenAILLM:
        """
        Validate cfg and return a connected OpenAILLM.

        :param cfg: config dict with keys:
            - name (str)
            - type == "openai"
            - model_name (str)
            - api_key (str, optional)
            - base_url (HttpUrl, optional)
            - temperature (float, optional)
            - max_tokens (int, optional)
        :raises PluginConfigurationError: on validation failure
        """
        try:
            element_deps = deps.pop("deps", None)
            tracing = element_deps.tracing_service if element_deps else None

            llm = OpenAILLM(
                model_name=cfg.model_name,
                api_key=cfg.api_key,
                base_url=str(cfg.base_url),
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                tracing=tracing,
                **cfg.extra
            )
            return llm
        except Exception as e:
            raise PluginConfigurationError(f"Failed to create OpenAI LLM: {e}", cfg) from e
