"""Auth command group — login, logout, and session status."""
from __future__ import annotations

import typer

auth_app = typer.Typer(
    name="auth",
    help="Manage CLI authentication (SSO / Keycloak).",
    no_args_is_help=True,
)


@auth_app.command("login")
def login_cmd(
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Re-authenticate even if a valid session already exists.",
    ),
    callback_port: int = typer.Option(
        0, "--callback-port", "-p",
        help=(
            "Port for the local OAuth callback server (default: auto-select). "
            "Set this to a fixed value when running over SSH so you can forward "
            "the same port: ssh -L <port>:localhost:<port> <remote-host>. "
            "Can also be set via the AUTH_CALLBACK_PORT environment variable."
        ),
        envvar="AUTH_CALLBACK_PORT",
    ),
):
    """Authenticate with the SSO provider and cache the session for 10 hours."""
    from unifai_cli.auth.flow import ensure_authenticated
    ensure_authenticated(force=force, callback_port=callback_port or None)


@auth_app.command("logout")
def logout_cmd():
    """Clear the local auth session (next command will require re-login)."""
    from unifai_cli.auth.session import clear_session, load_session
    from unifai_cli.display.formatting import console

    if not load_session():
        console.print("[dim]No active session found.[/dim]")
        return

    clear_session()
    console.print("[dim]Session cleared. Run [bold]unifai auth login[/bold] to authenticate again.[/dim]")


@auth_app.command("status")
def status_cmd():
    """Show the current authentication status and session expiry."""
    from unifai_cli.auth.session import load_session, session_expires_at
    from unifai_cli.display.formatting import console

    session = load_session()
    if not session:
        console.print(
            "[yellow]Not authenticated.[/yellow]  "
            "Run [bold]unifai auth login[/bold] to log in."
        )
        return

    expires = session_expires_at(session)
    console.print("[green]Authenticated[/green] (session cookie active)")
    console.print(f"[dim]Session expires: {expires.strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
