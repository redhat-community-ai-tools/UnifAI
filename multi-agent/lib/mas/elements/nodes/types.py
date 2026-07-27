from typing import Union, Annotated
from pydantic import Field

from mas.elements.nodes.custom_agent.config import CustomAgentNodeConfig
from mas.elements.nodes.mock_agent.config import MockAgentNodeConfig
from mas.elements.nodes.llm_merger.config import MergerLLMNodeConfig
from mas.elements.nodes.final_answer.config import FinalAnswerNodeConfig
from mas.elements.nodes.user_question.config import UserQuestionNodeConfig
from mas.elements.nodes.branch_chooser.config import BranchChooserNodeConfig
from mas.elements.nodes.orchestrator.config import OrchestratorNodeConfig
from mas.elements.nodes.a2a_agent.config import A2AAgentNodeConfig
from mas.elements.nodes.deep_agent.config import DeepAgentNodeConfig
from mas.elements.nodes.claude_agent.config import ClaudeAgentNodeConfig

# Union type for backward compatibility with blueprints
NodeSpec = Annotated[
    Union[
        CustomAgentNodeConfig,
        MockAgentNodeConfig,
        # MergerLLMNodeConfig,
        FinalAnswerNodeConfig,
        UserQuestionNodeConfig,
        BranchChooserNodeConfig,
        OrchestratorNodeConfig,
        A2AAgentNodeConfig,
        DeepAgentNodeConfig,
        A2AAgentNodeConfig,
        ClaudeAgentNodeConfig,
    ],
    Field(discriminator="type")
]
