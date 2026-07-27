"""
Card builder for ``DeepAgentNode``.

Uses the default card composition strategy — skills and capabilities
are aggregated from dependency cards (tools, providers).
"""

from mas.elements.common.card.default import DefaultCardBuilder


class DeepAgentCardBuilder(DefaultCardBuilder):
    """Deep Agent uses default card building.

    Skills come from tools and MCP providers referenced in config.
    Capabilities come from retrievers referenced in config.
    """
    pass
