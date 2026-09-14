from typing import Union, Annotated
from pydantic import Field
from mas.elements.llms.openai.config import OpenAIConfig
from mas.elements.llms.openai_compatible.config import OpenAICompatibleConfig
from mas.elements.llms.mock.config import MockLLMConfig
from mas.elements.llms.google_genai.config import GoogleGenAIConfig

# Union type for backward compatibility with blueprints
LLMsSpec = Annotated[
    Union[
        OpenAIConfig,
        OpenAICompatibleConfig,
        MockLLMConfig,
        GoogleGenAIConfig
    ],
    Field(discriminator="type")
]
