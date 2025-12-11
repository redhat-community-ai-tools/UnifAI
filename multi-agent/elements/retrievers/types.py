from typing import Union, Annotated
from pydantic import Field
from elements.retrievers.docs_dataflow.config import DocsDataflowRetrieverConfig
from elements.retrievers.slack.config import SlackRetrieverConfig

# Union type for backward compatibility with blueprints
RetrieversSpec = Annotated[
    Union[
        DocsDataflowRetrieverConfig,
        SlackRetrieverConfig,
    ],
    Field(discriminator="type")
]
