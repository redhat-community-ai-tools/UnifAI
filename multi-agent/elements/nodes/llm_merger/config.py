from core.ref.models import LLMRef
from elements.nodes.common.base_config import NodeBaseConfig
from typing import Literal
from pydantic import Field
from .identifiers import Identifier
from core.field_hints import ApiHint, HintType, SelectionType


class MergerLLMNodeConfig(NodeBaseConfig):
    """
    Node that merges outputs from multiple agents.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    llm: LLMRef = Field(
        description="LLM Ref UID to use",
        json_schema_extra=ApiHint(
            endpoint="/resources/resource.validate",
            method="POST",
            hint_type=HintType.VALIDATE,
            selection_type=SelectionType.AUTOMATIC,
            dependencies={"llm": "resourceId"},
            field_mapping="is_valid"
        ).to_hints()
    )
    system_message: str = Field("""You are the Merger Agent. Your role is to combine answers from specialized agents into one clear, helpful response.

        1. **Merge answers**:
           - Combine all relevant information into a single coherent message.
           - Attribute each part using inline tags like “[Slack Agent]”, “[Document Agent]”, etc.
           - If sources agree, write: “...confirmed by multiple sources [Slack Agent, Document Agent].”
           - For conflicting views, show both sides neutrally.

        2. **Preserve original references**:
           - If an agent mentioned a source (e.g., PDF name, Slack user, timestamp), include it in parentheses within the sentence.
           - Keep source mentions (like file names or authors) distinct from agent tags.

        3. **Missing info**:
           - If any agent asked for more input, list those requests at the end under:
             "**To improve this answer, consider providing:**"
           - Only include real prompts—don’t invent or specify which agent asked.

        Output:
        - Start with the merged answer using inline agent tags and source mentions.
        - End with the improvement section if needed.
        - Use a professional, neutral tone that’s easy to follow.""",
                                description="Unifier/Merger system prompt")
