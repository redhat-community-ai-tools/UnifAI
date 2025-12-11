"""
Tool wrapper that adapts any BaseRetriever to be used as a BaseTool.
Allows agents to decide when to perform retrieval.
"""

from typing import Any, Type, Optional
from pydantic import BaseModel, Field
from elements.tools.common.base_tool import BaseTool
from elements.retrievers.common.base_retriever import BaseRetriever
from global_utils.utils import to_snake_case


class RetrieverToolArgs(BaseModel):
    """Generic args schema for retriever tools."""
    query: str = Field(
        ...,
        description="The search query to retrieve relevant information"
    )


class RetrieverTool(BaseTool):
    """
    A wrapper that adapts any BaseRetriever to be used as a BaseTool.
    
    This follows the Adapter Pattern, allowing retrievers to be exposed 
    as tools to LLM agents, giving agents the ability to decide when 
    to perform retrieval based on context.
    
    Usage:
        retriever = SlackRetriever(api_url="...", top_k_results=5, threshold=0.7)
        tool = RetrieverTool(retriever)
        # Or with customizations:
        tool = RetrieverTool(
            retriever,
            name="search_slack_messages",
            description="Search Slack for relevant messages and conversations"
        )
    """

    name: str = "retriever_tool"
    description: str = "Search and retrieve relevant information based on a query"
    args_schema: Type[BaseModel] = RetrieverToolArgs

    def __init__(
        self,
        retriever: BaseRetriever,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        args_schema: Optional[Type[BaseModel]] = None
    ):
        """
        Initialize a retriever tool wrapper.
        
        Args:
            retriever: The BaseRetriever instance to wrap
            name: Optional custom tool name (default: auto-generated from retriever class)
            description: Optional custom description for the LLM
            args_schema: Optional custom args schema (default: RetrieverToolArgs)
        """
        self._retriever = retriever

        # Set custom name or generate from retriever class name
        if name:
            self.name = name
        else:
            # e.g., SlackRetriever -> slack_retriever_tool
            retriever_name = retriever.__class__.__name__
            self.name = f"{to_snake_case(retriever_name)}_tool"

        # Set custom description or generate default
        if description:
            self.description = description
        else:
            retriever_class_name = retriever.__class__.__name__
            self.description = (
                f"Search and retrieve relevant information using {retriever_class_name}.\n\n"
                f"Use this tool to find and retrieve contextual information that can help "
                f"answer the user's question more accurately. The tool returns relevant data "
                f"that you can use to augment your response.\n\n"
                f"Consider using this when additional context or specific information "
                f"would improve your answer. Skip it when the question can be fully "
                f"addressed with your existing knowledge."
            )

        # Set custom args schema or use default
        if args_schema:
            self.args_schema = args_schema

    def run(self, **kwargs) -> Any:
        """Execute the retriever with the given query."""
        args = self.args_schema(**kwargs)
        return self._retriever.retrieve(args.query)

