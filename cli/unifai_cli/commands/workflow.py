"""
Workflow command group — start and interact with workflow sessions.

Execution uses POST /user.session.submit + GET /session.subscribe (UI path),
with submit + poll as fallback when subscribe is unavailable.
"""
from __future__ import annotations

import time
from typing import Optional

import typer

from unifai_cli.api import MASClient

workflow_app = typer.Typer(
    name="workflow",
    help="Start and interact with workflow sessions.",
    no_args_is_help=True,
)


@workflow_app.command("run")
def run_cmd(
    user: Optional[str] = typer.Option(None, "--user", "-u", help="User ID", envvar="UNIFAI_USER"),
    mas_url: Optional[str] = typer.Option(None, "--mas-url", help="MAS server URL", envvar="MAS_URL"),
    blueprint_id: Optional[str] = typer.Option(None, "--blueprint-id", "-b", help="Blueprint ID to run"),
    blueprint_name: Optional[str] = typer.Option(None, "--blueprint-name", "-n", help="Blueprint name to resolve"),
    question: Optional[str] = typer.Option(None, "--question", "-q", help="Single prompt (non-interactive mode)"),
):
    """Start a workflow session and interact with it."""
    from unifai_cli.bootstrap import build_client, resolve_user_id
    from unifai_cli.display.formatting import console

    user_id = resolve_user_id(user)
    client = build_client(mas_url, user_id=user_id)

    bp_id = _resolve_blueprint(client, user_id, blueprint_id, blueprint_name)
    if bp_id is None:
        return

    if question:
        _run_single_shot(client, user_id, bp_id, question, console)
    else:
        _run_interactive_loop(client, user_id, bp_id, console)


def run_workflow_interactive(client: MASClient, user_id: str) -> None:
    """Entry point from the interactive menu — select blueprint then chat."""
    from unifai_cli.display.formatting import console

    bp_id = _resolve_blueprint(client, user_id, None, None)
    if bp_id is None:
        return

    _run_interactive_loop(client, user_id, bp_id, console)


# ── Blueprint resolution ──


def _resolve_blueprint(
    client: MASClient,
    user_id: str,
    blueprint_id: Optional[str],
    blueprint_name: Optional[str],
) -> Optional[str]:
    """Resolve a blueprint ID from direct ID, name lookup, or interactive selection."""
    if blueprint_id:
        return blueprint_id

    if blueprint_name:
        return _resolve_by_name(client, user_id, blueprint_name)

    return _resolve_by_selection(client, user_id)


def _resolve_by_name(client: MASClient, user_id: str, name: str) -> Optional[str]:
    from unifai_cli.display.formatting import console

    try:
        summaries = client.list_blueprint_summaries(user_id)
    except Exception as e:
        console.print(f"[red]Failed to list blueprints:[/red] {e}")
        return None

    target = name.lower().strip()
    matches = [s for s in summaries if s.get("name", "").lower().strip() == target]

    if not matches:
        console.print(f"[red]Blueprint '{name}' not found.[/red]")
        return None
    if len(matches) > 1:
        console.print(f"[red]Multiple blueprints named '{name}'. Use --blueprint-id instead.[/red]")
        return None

    return matches[0]["blueprint_id"]


def _resolve_by_selection(client: MASClient, user_id: str) -> Optional[str]:
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
    selected = select_blueprint(summaries)
    return selected["blueprint_id"] if selected else None


# ── Execution ──


def _execute_turn(client: MASClient, session_id: str, prompt: str,
                  user_id: str, console) -> bool:
    """
    Execute a single user turn via submit + subscribe (same as the UI).

    Falls back to submit + poll if the subscribe stream is unavailable.

    Returns True on success, False on failure.
    """
    from unifai_cli.display.streaming import display_streaming_events

    inputs = {"user_prompt": prompt}

    try:
        response = client.run_session_turn(
            session_id, inputs, scope="public", user_id=user_id,
        )
        if display_streaming_events(response, console):
            return True
        return False
    except Exception:
        pass

    try:
        client.submit_session(session_id, inputs, user_id=user_id)
        _poll_until_done(client, session_id, console)
        return True
    except Exception as e:
        console.print(f"\n[red]Execution error:[/red] {e}")
        return False


def _poll_until_done(client: MASClient, session_id: str, console,
                     interval: int = 5) -> None:
    """Poll session status until execution completes."""
    console.print("  [dim]Waiting for execution...[/dim]", end="")

    while True:
        try:
            status = client.get_stream_status(session_id)
            is_active = status.get("is_active", False)
            if not is_active:
                console.print(" done")
                return
        except Exception:
            # stream.status may 404 after completion — check session status
            try:
                session_status = client.get_session_status(session_id)
                status_name = session_status.get("status", session_status) if isinstance(session_status, dict) else str(session_status)
                if isinstance(status_name, str) and status_name.upper() in ("COMPLETED", "FAILED"):
                    console.print(f" {status_name.lower()}")
                    return
            except Exception:
                pass

        console.print(".", end="")
        time.sleep(interval)


def _run_single_shot(client, user_id, blueprint_id, question, console):
    """Run a single prompt and display the result."""
    from rich.panel import Panel

    console.print(f"\n[bold]Starting workflow...[/bold]")

    try:
        run_id = client.create_session(user_id, blueprint_id)
        if isinstance(run_id, dict):
            run_id = run_id.get("sessionId", run_id.get("session_id", run_id.get("run_id", str(run_id))))
    except Exception as e:
        console.print(f"[red]Failed to create session:[/red] {e}")
        return

    console.print(f"[dim]Session: {run_id}[/dim]\n")
    console.print(f"[bold green]You:[/bold green] {question}\n")

    success = _execute_turn(client, run_id, question, user_id, console)
    if success:
        _show_final_answer(client, run_id, console)


def _run_interactive_loop(client, user_id, blueprint_id, console):
    """Interactive chat loop: prompt -> execute -> display -> repeat."""
    from rich.panel import Panel

    console.print(f"\n[bold]Starting workflow session...[/bold]")

    try:
        run_id = client.create_session(user_id, blueprint_id)
        if isinstance(run_id, dict):
            run_id = run_id.get("sessionId", run_id.get("session_id", run_id.get("run_id", str(run_id))))
    except Exception as e:
        console.print(f"[red]Failed to create session:[/red] {e}")
        return

    console.print(f"[dim]Session: {run_id}[/dim]")
    console.print("[dim]Type your prompts below. Enter 'exit' or 'quit' to end the session.[/dim]\n")

    while True:
        try:
            prompt = console.input("[bold green]You:[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if not prompt.strip():
            continue
        if prompt.strip().lower() in ("exit", "quit", "q"):
            console.print("[dim]Session ended.[/dim]")
            break

        console.print()

        success = _execute_turn(client, run_id, prompt, user_id, console)
        if success:
            _show_final_answer(client, run_id, console)
        else:
            console.print("[dim]You can try another prompt or type 'exit' to quit.[/dim]")

        console.print()


def _show_final_answer(client, run_id, console):
    """Retrieve and display the final answer from a completed session."""
    from rich.panel import Panel

    try:
        chat = client.get_session_chat(run_id)
        status = (chat.get("status") or "").upper()
        status_message = chat.get("status_message") or ""

        if status == "FAILED":
            console.print(
                f"[red]Workflow failed:[/red] {status_message or 'No details available.'}"
            )
            return
        if status == "CANCELLED":
            console.print("[dim]Workflow cancelled.[/dim]")
            return

        output = chat.get("output", "")
        if output:
            console.print(Panel(output, title="[bold]Assistant[/bold]", border_style="blue"))
            return

        messages = chat.get("messages", [])
        if messages:
            last = messages[-1]
            content = last.get("content", "")
            if content and last.get("role") != "user":
                console.print(Panel(content, title="[bold]Assistant[/bold]", border_style="blue"))
                return

        if status:
            console.print(f"[dim]Session status: {status} (no output yet)[/dim]")
        else:
            session_status = client.get_session_status(run_id)
            console.print(f"[dim]Session status: {session_status} (no output yet)[/dim]")
    except Exception as e:
        console.print(f"[dim]Could not retrieve answer: {e}[/dim]")
