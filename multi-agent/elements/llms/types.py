from typing import Union, Annotated
from pydantic import Field
from elements.llms.openai.config import OpenAIConfig
from elements.llms.mock.config import MockLLMConfig
from elements.llms.google_genai.config import GoogleGenAIConfig

# Union type for backward compatibility with blueprints
LLMsSpec = Annotated[
    Union[
        OpenAIConfig,
        MockLLMConfig,
        GoogleGenAIConfig
    ],
    Field(discriminator="type")
]
