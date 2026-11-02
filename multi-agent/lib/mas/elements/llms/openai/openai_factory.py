from typing import Any, Optional
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.elements.llms.openai.config import OpenAIConfig
from mas.elements.llms.openai.openai import OpenAILLM
from mas.elements.llms.openai.identifiers import Identifier


class OpenAIFactory(BaseFactory[OpenAIConfig, OpenAILLM]):
    """
    Factory for creating OpenAI LLM instances (Responses API).

    Validates configuration and creates an OpenAILLM pointed at the
    official OpenAI Responses API endpoint.
    """

    def accepts(self, cfg: OpenAIConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: OpenAIConfig, **deps: Any) -> OpenAILLM:
        try:
            element_deps = deps.pop("deps", None)
            tracing = element_deps.tracing_service if element_deps else None

            llm = OpenAILLM(
                model_name=cfg.model_name,
                api_key=cfg.api_key,
                base_url=str(cfg.base_url),
                max_tokens=cfg.max_tokens,
                reasoning_effort=cfg.reasoning_effort,
                tracing=tracing,
                **cfg.extra
            )
            return llm
        except Exception as e:
            raise PluginConfigurationError(
                f"Failed to create OpenAI LLM: {e}", cfg
            ) from e
