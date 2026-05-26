"""
Blueprints command group — list and inspect workflow blueprints.
"""
from __future__ import annotations

from typing import Optional

import typer

from unifai_cli.api import MASClient

blueprints_app = typer.Typer(
    name="blueprints",
    help="Browse and inspect workflow blueprints.",
    no_args_is_help=True,
)


@blueprints_app.command("list")
def list_cmd(
    user: Optional[str] = typer.Option(None, "--user", "-u", help="User ID", envvar="UNIFAI_USER"),
    mas_url: Optional[str] = typer.Option(None, "--mas-url", help="MAS server URL", envvar="MAS_URL"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Select a blueprint to inspect"),
):
    """List all blueprints available to a user."""
    from unifai_cli.bootstrap import build_client, resolve_user_id
    from unifai_cli.display.formatting import console, render_blueprint_table

    user_id = resolve_user_id(user)
    client = build_client(mas_url, user_id=user_id)

    try:
        summaries = client.list_blueprint_summaries(user_id)
    except Exception as e:
        console.print(f"[red]Failed to list blueprints:[/red] {e}")
        return

    if not summaries:
        console.print("[dim]No blueprints found.[/dim]")
        return

    console.print(render_blueprint_table(summaries))

    if interactive:
        from unifai_cli.interaction.menus import select_blueprint
        selected = select_blueprint(summaries)
        if selected:
            _show_blueprint(client, selected["blueprint_id"])


@blueprints_app.command("inspect")
def inspect_cmd(
    blueprint_id: str = typer.Argument(..., help="Blueprint ID to inspect"),
    mas_url: Optional[str] = typer.Option(None, "--mas-url", help="MAS server URL", envvar="MAS_URL"),
):
    """Show the full YAML configuration of a blueprint."""
    from unifai_cli.bootstrap import build_client

    client = build_client(mas_url)
    _show_blueprint(client, blueprint_id)


# ── Helpers used by both CLI commands and the interactive menu ──


def list_blueprints_interactive(client: MASClient, user_id: str) -> Optional[dict]:
    """List blueprints and let the user select one. Returns the selected summary or None."""
    from unifai_cli.display.formatting import console, render_blueprint_table
    from unifai_cli.interaction.menus import select_blueprint

    try:
        summaries = client.list_blueprint_summaries(user_id)
    except Exception as e:
        console.print(f"[red]Failed to list blueprints:[/red] {e}")
        return None

    if not summaries:
        console.print("[dim]No blueprints found.[/dim]")
        return None

    console.print(render_blueprint_table(summaries))
    return select_blueprint(summaries)


def inspect_blueprint_interactive(client: MASClient, blueprint_id: str) -> None:
    """Show a blueprint's YAML config (called from interactive menu)."""
    _show_blueprint(client, blueprint_id)


def _show_blueprint(client: MASClient, blueprint_id: str) -> None:
    from unifai_cli.display.formatting import console, render_yaml

    try:
        data = client.get_blueprint(blueprint_id)
    except Exception as e:
        console.print(f"[red]Error loading blueprint:[/red] {e}")
        return

    spec = data.get("spec_dict", data)
    name = spec.get("name", data.get("name", "Untitled"))
    render_yaml(spec, title=f"Blueprint: {name}")
