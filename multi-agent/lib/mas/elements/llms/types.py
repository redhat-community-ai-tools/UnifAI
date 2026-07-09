from typing import Union, Annotated
from pydantic import Field
from mas.elements.llms.openai.config import OpenAIConfig
from mas.elements.llms.mock.config import MockLLMConfig
from mas.elements.llms.google_genai.config import GoogleGenAIConfig
from mas.elements.llms.anthropic.config import AnthropicConfig

# Union type for backward compatibility with blueprints
LLMsSpec = Annotated[
    Union[
        OpenAIConfig,
        MockLLMConfig,
        GoogleGenAIConfig,
        AnthropicConfig
    ],
    Field(discriminator="type")
]
