"""Default card builder for sandboxes.

A sandbox represents itself as a single skill.
"""

from mas.elements.common.card.models import ElementCard, Skill, CardBuildInput
from mas.elements.common.card.interface import CardBuilder


class SandboxCardBuilder(CardBuilder):
    """Sandbox builds its card with itself as a skill."""

    def build(self, input: CardBuildInput) -> ElementCard:
        """Build card with this sandbox as a skill."""
        skill = Skill(
            name=input.name,
            description=input.spec_metadata.description,
        )
        return ElementCard(
            uid=input.rid,
            category=input.spec_metadata.category,
            type_key=input.spec_metadata.type_key,
            name=input.name,
            description=input.spec_metadata.description,
            skills=[skill],
            capabilities=[],
            configuration={},
            metadata=None,
        )
