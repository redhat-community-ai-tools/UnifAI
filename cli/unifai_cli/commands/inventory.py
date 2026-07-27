"""
Inventory command group — list and inspect resources (LLMs, tools, agents, etc.).
"""
from __future__ import annotations

from typing import Optional

import typer

from unifai_cli.api import MASClient

inventory_app = typer.Typer(
    name="inventory",
    help="Browse and inspect inventory elements (LLMs, tools, agents, etc.).",
    no_args_is_help=True,
)


@inventory_app.command("list")
def list_cmd(
    mas_url: Optional[str] = typer.Option(None, "--mas-url", help="MAS server URL", envvar="MAS_URL"),
    category: Optional[str] = typer.Option(
        None, "--category", "-c",
        help="Filter by category (llms, tools, nodes, retrievers, providers, conditions)",
    ),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Select a resource to inspect"),
):
    """List inventory elements for the authenticated user."""
    from unifai_cli.bootstrap import build_client, resolve_session
    from unifai_cli.display.formatting import console, render_resource_table

    session_cookie = resolve_session()
    client = build_client(mas_url, session_cookie=session_cookie)

    try:
        result = client.list_resources(category=category)
    except Exception as e:
        console.print(f"[red]Failed to list resources:[/red] {e}")
        return

    resources = result.get("resources", [])
    pagination = result.get("pagination", {})
    total = pagination.get("total", len(resources))

    if not resources:
        console.print("[dim]No resources found.[/dim]")
        return

    console.print(render_resource_table(resources))
    console.print(f"[dim]Showing {len(resources)} of {total} resources[/dim]")

    if interactive:
        from unifai_cli.interaction.menus import select_resource
        selected = select_resource(resources)
        if selected:
            rid = selected.get("rid", selected.get("_id", ""))
            _show_resource(client, rid)


@inventory_app.command("inspect")
def inspect_cmd(
    resource_id: str = typer.Argument(..., help="Resource ID to inspect"),
    mas_url: Optional[str] = typer.Option(None, "--mas-url", help="MAS server URL", envvar="MAS_URL"),
):
    """Show the full YAML configuration of a resource."""
    from unifai_cli.bootstrap import build_client

    client = build_client(mas_url)
    _show_resource(client, resource_id)


# ── Helpers used by both CLI commands and the interactive menu ──


def list_inventory_interactive(client: MASClient) -> Optional[dict]:
    """List resources with optional category filter and let the user select one."""
    from unifai_cli.display.formatting import console, render_resource_table
    from unifai_cli.interaction.menus import select_category, select_resource

    category = select_category()
    if category is False:
        return None

    try:
        result = client.list_resources(category=category)
    except Exception as e:
        console.print(f"[red]Failed to list resources:[/red] {e}")
        return None

    resources = result.get("resources", [])
    pagination = result.get("pagination", {})
    total = pagination.get("total", len(resources))

    if not resources:
        console.print("[dim]No resources found.[/dim]")
        return None

    console.print(render_resource_table(resources))
    console.print(f"[dim]Showing {len(resources)} of {total} resources[/dim]")

    return select_resource(resources)


def inspect_resource_interactive(client: MASClient, resource_id: str) -> None:
    """Show a resource's YAML config (called from interactive menu)."""
    _show_resource(client, resource_id)


def _show_resource(client: MASClient, resource_id: str) -> None:
    from unifai_cli.display.formatting import console, render_yaml

    try:
        resource = client.get_resource(resource_id)
    except Exception as e:
        console.print(f"[red]Error loading resource:[/red] {e}")
        return

    data = {
        "name": resource.get("name", ""),
        "category": resource.get("category", ""),
        "type": resource.get("type", ""),
        "config": resource.get("cfg_dict", {}),
    }
    render_yaml(data, title=f"Resource: {resource.get('name', 'Unknown')}")
