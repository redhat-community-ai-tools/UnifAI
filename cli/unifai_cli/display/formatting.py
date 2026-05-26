"""
Display utilities — YAML rendering, tables, and panels.

All output goes through a shared ``console`` instance so that
colour/width settings are consistent across the CLI.
"""
from __future__ import annotations

from typing import Any, Dict, List

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()


def render_yaml(data: Dict[str, Any], title: str = "") -> None:
    """Dump *data* as syntax-highlighted YAML inside a panel."""
    yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    syntax = Syntax(yaml_str, "yaml", theme="monokai", word_wrap=True)
    console.print(Panel(syntax, title=title, expand=False))


def render_blueprint_table(summaries: List[dict]) -> Table:
    """Build a rich Table from a list of blueprint summary dicts."""
    table = Table(title="Blueprints", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="bold cyan")
    table.add_column("Description", max_width=50)
    table.add_column("Updated", style="dim")
    table.add_column("ID", style="dim")

    for idx, s in enumerate(summaries, 1):
        desc = (s.get("description") or "")[:50]
        updated = s.get("updated_at", "")
        if isinstance(updated, str) and len(updated) > 16:
            updated = updated[:16]
        table.add_row(str(idx), s.get("name", "Untitled"), desc, str(updated), s.get("blueprint_id", "")[:15] + "...")

    return table


def render_resource_table(resources: List[dict]) -> Table:
    """Build a rich Table from a list of resource dicts."""
    table = Table(title="Inventory Elements", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Category", style="bold magenta")
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("ID", style="dim")

    for idx, r in enumerate(resources, 1):
        category_label = _category_display(r.get("category", ""))
        rid = r.get("rid", r.get("_id", ""))
        table.add_row(str(idx), category_label, r.get("type", ""), r.get("name", ""), str(rid)[:15] + "...")

    return table


CATEGORY_LABELS = {
    "llms": "LLMs",
    "tools": "Tools",
    "nodes": "Agents",
    "retrievers": "Retrievers",
    "providers": "Providers",
    "conditions": "Conditions",
}


def _category_display(category: str) -> str:
    """Convert a category string to a human-friendly label."""
    return CATEGORY_LABELS.get(category, category)


def render_session_status(status: str) -> str:
    """Return a rich-styled status string."""
    colors = {
        "PENDING": "dim",
        "QUEUED": "yellow",
        "RUNNING": "bold yellow",
        "COMPLETED": "bold green",
        "FAILED": "bold red",
    }
    color = colors.get(status.upper(), "white")
    return f"[{color}]{status}[/{color}]"
