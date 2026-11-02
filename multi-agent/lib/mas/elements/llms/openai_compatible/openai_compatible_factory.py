from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.elements.llms.openai_compatible.config import OpenAICompatibleConfig
from mas.elements.llms.openai_compatible.openai_compatible import OpenAICompatibleLLM
from mas.elements.llms.openai_compatible.identifiers import Identifier


class OpenAICompatibleFactory(BaseFactory[OpenAICompatibleConfig, OpenAICompatibleLLM]):
    """
    Factory for creating OpenAI-compatible LLM instances.

    Accepts any server implementing the Chat Completions API
    (vLLM, LocalAI, Ollama, Azure OpenAI, etc.).
    """

    def accepts(self, cfg: OpenAICompatibleConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: OpenAICompatibleConfig, **deps: Any) -> OpenAICompatibleLLM:
        try:
            element_deps = deps.pop("deps", None)
            tracing = element_deps.tracing_service if element_deps else None

            llm = OpenAICompatibleLLM(
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
            raise PluginConfigurationError(
                f"Failed to create OpenAI-compatible LLM: {e}", cfg
            ) from e
