"""
Card builder for Claude Agent Node.

Builds element card from local configuration (model, tools, capabilities).
"""

from typing import List
from mas.elements.common.card.models import ElementCard, Skill, Capability, CardBuildInput
from mas.elements.common.card.interface import CardBuilder


class ClaudeAgentCardBuilder(CardBuilder):
    """
    Builds element card for Claude Agent Node.

    Skills = allowed tools (Read, Write, Bash, etc.)
    Capabilities = model, permission mode, max turns
    """

    def build(self, input: CardBuildInput) -> ElementCard:
        config = input.config

        skills: List[Skill] = []
        for tool_name in (config.allowed_tools or []):
            skills.append(Skill(
                name=tool_name,
                description=f"Claude Agent built-in tool: {tool_name}",
            ))

        for card in input.dependency_cards.values():
            skills.extend(card.skills)

        capabilities: List[Capability] = [
            Capability(
                name="model",
                description=f"Claude model: {config.model}",
            ),
            Capability(
                name="effort",
                description=f"Effort level: {config.effort}",
            ),
            Capability(
                name="autonomous_execution",
                description=f"Permission mode: {config.permission_mode}",
            ),
        ]

        if config.max_turns:
            capabilities.append(Capability(
                name="max_turns",
                description=f"Maximum {config.max_turns} agentic turns",
            ))

        if config.skills_repos:
            capabilities.append(Capability(
                name="skills",
                description=f"{len(config.skills_repos)} skills repo(s) configured",
            ))

        return ElementCard(
            uid=input.rid,
            category=input.spec_metadata.category,
            type_key=input.spec_metadata.type_key,
            name=input.name,
            description=input.spec_metadata.description,
            skills=skills,
            capabilities=capabilities,
            configuration={},
            metadata=None,
        )
