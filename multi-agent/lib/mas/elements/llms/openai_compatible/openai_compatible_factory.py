from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.elements.llms.openai_compatible.config import OpenAICompatibleConfig
from mas.elements.llms.openai_compatible.openai_compatible import OpenAICompatibleLLM
from mas.elements.llms.openai_compatible.identifiers import Identifier
from mas.core.identity_forwarding import IdentityForwarder, NullIdentityTokenSource


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

            forwarder = None
            if cfg.forward_user_token or cfg.default_headers or cfg.metadata_lookup_url:
                source = getattr(element_deps, "identity_token_source", None) or NullIdentityTokenSource()
                holder = getattr(element_deps, "execution_ctx", None)
                # The user's token may only reach the model endpoint and the routing lookup it names.
                targets = tuple(u for u in (str(cfg.base_url), cfg.metadata_lookup_url) if u)
                forwarder = IdentityForwarder(source, holder, target_urls=targets)

            llm = OpenAICompatibleLLM(
                model_name=cfg.model_name,
                api_key=cfg.api_key,
                base_url=str(cfg.base_url),
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                max_retries=cfg.max_retries,
                timeout_seconds=cfg.timeout_seconds,
                metadata_lookup_url=cfg.metadata_lookup_url,
                metadata_lookup_timeout=cfg.metadata_lookup_timeout,
                request_id_header=cfg.request_id_header,
                tracing=tracing,
                forwarder=forwarder,
                forward_user_token=cfg.forward_user_token,
                header_templates=cfg.default_headers,
                **cfg.extra
            )
            return llm
        except Exception as e:
            raise PluginConfigurationError(
                f"Failed to create OpenAI-compatible LLM: {e}", cfg
            ) from e
