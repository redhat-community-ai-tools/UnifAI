"""
UnifAI CLI — interactive terminal interface for the multi-agent platform.

Entry point for the ``unifai`` command.  Registers subcommand groups
for blueprints, inventory, and workflow execution, plus a top-level
``interactive`` command that presents a guided menu.

The CLI is a thin HTTP client that talks to the MAS API server.
"""
from __future__ import annotations

from typing import Optional

import typer

from unifai_cli.commands.auth import auth_app
from unifai_cli.commands.blueprints import blueprints_app
from unifai_cli.commands.inventory import inventory_app
from unifai_cli.commands.workflow import workflow_app

app = typer.Typer(
    name="unifai",
    help="UnifAI CLI — explore blueprints, inventory, and run workflows.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

app.add_typer(auth_app, name="auth")
app.add_typer(blueprints_app, name="blueprints")
app.add_typer(inventory_app, name="inventory")
app.add_typer(workflow_app, name="workflow")


@app.command("interactive")
def interactive(
    user: Optional[str] = typer.Option(None, "--user", "-u", help="User ID", envvar="UNIFAI_USER"),
    mas_url: Optional[str] = typer.Option(None, "--mas-url", help="MAS server URL", envvar="MAS_URL"),
):
    """Launch the interactive menu."""
    from unifai_cli.bootstrap import build_client, resolve_user_id
    from unifai_cli.interaction.menus import select_main_menu
    from unifai_cli.commands.blueprints import list_blueprints_interactive, inspect_blueprint_interactive
    from unifai_cli.commands.inventory import list_inventory_interactive, inspect_resource_interactive
    from unifai_cli.commands.workflow import run_workflow_interactive
    from unifai_cli.display.formatting import console

    user_id = resolve_user_id(user)
    client = build_client(mas_url, user_id=user_id)

    console.print(f"\n[bold]Welcome to UnifAI CLI[/bold]  (user: [cyan]{user_id}[/cyan], server: [dim]{client.base_url}[/dim])\n")

    while True:
        choice = select_main_menu()
        if choice is None:
            break

        if choice == "blueprints":
            bp = list_blueprints_interactive(client, user_id)
            if bp:
                inspect_blueprint_interactive(client, bp["blueprint_id"])

        elif choice == "inventory":
            resource = list_inventory_interactive(client, user_id)
            if resource:
                inspect_resource_interactive(client, resource["rid"])

        elif choice == "workflow":
            run_workflow_interactive(client, user_id)

        console.print()
