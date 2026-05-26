"""
Reusable interactive selection menus wrapping questionary.

All "Back" choices use value=False (not None) because questionary falls back
to returning the display string when value=None, which breaks callers that
check truthiness.  False is falsy, so existing `if selected:` guards work.
"""
from __future__ import annotations

from typing import List, Optional

import questionary


def select_main_menu() -> Optional[str]:
    """Present the top-level interactive menu.  Returns action key or None."""
    choices = [
        questionary.Choice("Blueprints  — browse workflow definitions", value="blueprints"),
        questionary.Choice("Inventory   — browse LLMs, tools, agents, etc.", value="inventory"),
        questionary.Choice("Run         — start a workflow session", value="workflow"),
        questionary.Separator(),
        questionary.Choice("Exit", value="exit"),
    ]
    try:
        result = questionary.select("What would you like to do?", choices=choices).ask()
        return None if result in (None, "exit") else result
    except KeyboardInterrupt:
        return None


def select_blueprint(summaries: List[dict]) -> Optional[dict]:
    """Prompt the user to pick a blueprint from the list."""
    if not summaries:
        return None

    choices = [
        questionary.Choice(
            f"{s.get('name', 'Untitled')}  ({s.get('blueprint_id', '')[:8]}...)",
            value=s,
        )
        for s in summaries
    ]
    choices.append(questionary.Separator())
    choices.append(questionary.Choice("Back", value=False))

    try:
        return questionary.select("Select a blueprint:", choices=choices).ask()
    except KeyboardInterrupt:
        return False


def select_resource(resources: List[dict]) -> Optional[dict]:
    """Prompt the user to pick a resource from the list."""
    if not resources:
        return None

    choices = [
        questionary.Choice(
            f"[{_cat_label(r.get('category', ''))}] {r.get('name', '')}  ({r.get('type', '')})",
            value=r,
        )
        for r in resources
    ]
    choices.append(questionary.Separator())
    choices.append(questionary.Choice("Back", value=False))

    try:
        return questionary.select("Select a resource:", choices=choices).ask()
    except KeyboardInterrupt:
        return False


# False is the "Back" sentinel for select_category.
# None is already taken by "All categories" so we need a distinct value.
CATEGORY_OPTIONS = [
    questionary.Choice("All categories", value=None),
    questionary.Separator(),
    questionary.Choice("LLMs", value="llms"),
    questionary.Choice("Tools", value="tools"),
    questionary.Choice("Agents (Nodes)", value="nodes"),
    questionary.Choice("Retrievers", value="retrievers"),
    questionary.Choice("Providers", value="providers"),
    questionary.Choice("Conditions", value="conditions"),
    questionary.Separator(),
    questionary.Choice("Back", value=False),
]


def select_category():
    """
    Prompt the user to pick a resource category filter.

    Returns:
        None  — "All categories" selected
        str   — specific category string
        False — "Back" selected or Ctrl+C interrupted
    """
    try:
        return questionary.select("Filter by category:", choices=CATEGORY_OPTIONS).ask()
    except KeyboardInterrupt:
        return False


def _cat_label(category: str) -> str:
    """Short display label for a category string."""
    labels = {
        "llms": "LLM",
        "tools": "Tool",
        "nodes": "Agent",
        "retrievers": "Retriever",
        "providers": "Provider",
        "conditions": "Condition",
    }
    return labels.get(category, category)
