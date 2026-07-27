"""High-level auth gate — ensure the CLI user is authenticated."""
from __future__ import annotations

from typing import Optional

from unifai_cli.auth.session import load_session, save_session


def ensure_authenticated(
    force: bool = False,
    callback_port: Optional[int] = None,
) -> dict:
    """
    Return a valid user session dict, triggering browser login if needed.

    Args:
        force:         Re-authenticate even if a valid cached session exists.
        callback_port: Explicit port for the local OAuth callback server.
                       Pass the port you have already forwarded when running
                       over SSH (ssh -L {port}:localhost:{port} <host>).
                       If None, resolved from AUTH_CALLBACK_PORT env/config,
                       or auto-selected.

    Returns:
        dict with keys: username, email, name, sub, expires_at

    Raises:
        SystemExit(1) on authentication failure.
    """
    from rich.console import Console
    console = Console()

    if not force:
        session = load_session()
        if session:
            return session

    from unifai_cli.auth.login import browser_login
    from unifai_cli.auth.session import session_expires_at

    console.print("\n[bold]UnifAI authentication[/bold]  (opens browser...)\n")

    try:
        user_info = browser_login(port=callback_port)
    except RuntimeError as exc:
        console.print(f"\n[red]Authentication failed:[/red] {exc}")
        raise SystemExit(1)

    save_session(user_info)

    display_name = user_info.get("name") or user_info.get("username", "unknown")
    username = user_info.get("username", "")
    session = load_session()
    expires = session_expires_at(session) if session else None
    expires_str = expires.strftime("%Y-%m-%d %H:%M") if expires else "10 hours"

    console.print(
        f"[green]Authenticated[/green] as [bold]{display_name}[/bold]"
        f" ([dim]{username}[/dim]) · session valid until [dim]{expires_str}[/dim]\n"
    )
    return user_info
