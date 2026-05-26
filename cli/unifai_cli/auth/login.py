"""Browser-based SSO login with a local HTTP callback server.

Flow:
  1. Resolve the callback port (explicit flag > AUTH_CALLBACK_PORT env > auto-select).
  2. Encode {"cli": true, "callbackUrl": "http://localhost:{port}/callback"}
     as base64 and pass it as the `state` query param to the SSO backend.
  3. Open the browser to {sso_url}/api/auth/login?state=<b64>.
  4. SSO backend detects the CLI state, exchanges the Keycloak code, and
     redirects the browser to our local callback with
     ?auth=success&user=<base64_user_info>.
  5. Callback handler decodes the user payload and signals completion.
  6. browser_login() returns the user dict; the caller persists the session.

Remote / port-forwarding note
------------------------------
When the CLI runs on a remote host (VM, container, OCP pod), the browser
runs on the developer's laptop.  The SSO backend redirects to
http://localhost:{port}/callback which the browser resolves as *laptop*
localhost — but the callback server is on the *remote* host.

Fix: set up an SSH tunnel *before* running `unifai auth login`:

    ssh -L {port}:localhost:{port} <remote-host>

Use a fixed port (--callback-port / AUTH_CALLBACK_PORT) so you know which
port to forward before the CLI starts.
"""
from __future__ import annotations

import base64
import json
import socket
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from rich.console import Console
from unifai_cli.config.app_config import AppConfig

_LOGIN_TIMEOUT_SECONDS = 120
_console = Console()


# ── Port helpers ──────────────────────────────────────────────────────────────

def _find_free_port() -> int:
    """Bind to port 0 to let the OS pick a free ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _assert_port_free(port: int) -> None:
    """Raise RuntimeError if *port* is already bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
        except OSError:
            raise RuntimeError(
                f"Port {port} is already in use on this host.\n"
                f"Choose a different port with --callback-port or AUTH_CALLBACK_PORT."
            )


def resolve_callback_port(requested: Optional[int]) -> int:
    """
    Return the port the callback server will listen on.

    Priority: explicit *requested* value > AUTH_CALLBACK_PORT env/config > auto.
    When an explicit port is given, validate it is free before returning.
    """
    config = AppConfig.get_instance()
    port = requested or config.auth_callback_port or 0
    if port:
        _assert_port_free(port)
        return port
    return _find_free_port()


# ── Callback HTTP handler ─────────────────────────────────────────────────────

def _make_handler(result: dict, done: threading.Event) -> type:
    """Return a BaseHTTPRequestHandler subclass that writes into shared state."""

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self._respond(404, b"<html><body>Not found</body></html>")
                return

            params = urllib.parse.parse_qs(parsed.query)
            auth_status = params.get("auth", [""])[0]

            if auth_status == "success":
                user_b64 = params.get("user", [""])[0]
                try:
                    # Restore padding stripped by the SSO backend before decoding
                    padded = user_b64 + "=" * (-len(user_b64) % 4)
                    user_data = json.loads(base64.urlsafe_b64decode(padded).decode())
                    result["user"] = user_data
                    body = (
                        b"<html><body style='font-family:sans-serif;text-align:center;"
                        b"margin-top:80px'>"
                        b"<h2>&#10003; Login successful!</h2>"
                        b"<p>You can close this tab and return to the terminal.</p>"
                        b"</body></html>"
                    )
                except Exception as exc:
                    result["error"] = f"Failed to parse auth response: {exc}"
                    body = b"<html><body><h2>Login error</h2><p>Could not parse the authentication response.</p></body></html>"
            else:
                result["error"] = "Authentication was not successful"
                body = (
                    b"<html><body style='font-family:sans-serif;text-align:center;"
                    b"margin-top:80px'>"
                    b"<h2>Login failed</h2>"
                    b"<p>Authentication was not successful. Close this tab and try again.</p>"
                    b"</body></html>"
                )

            self._respond(200, body)
            done.set()

        def _respond(self, code: int, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:  # silence server access logs
            pass

    return _CallbackHandler


# ── Public entry point ────────────────────────────────────────────────────────

def browser_login(
    port: Optional[int] = None,
    timeout: int = _LOGIN_TIMEOUT_SECONDS,
) -> dict:
    """
    Open the browser for SSO authentication and return the user info dict.

    Args:
        port:    Explicit callback port.  If None, resolved from config/env or
                 auto-selected.  When running over SSH, pass the port you have
                 already forwarded with ``ssh -L {port}:localhost:{port} <host>``.
        timeout: Seconds to wait for the browser callback before giving up.

    Raises:
        RuntimeError: on port conflict, timeout, or authentication failure.
    """
    config = AppConfig.get_instance()
    callback_port = resolve_callback_port(port)
    callback_url = f"http://localhost:{callback_port}/callback"

    state_payload = {"cli": True, "callbackUrl": callback_url}
    state_b64 = base64.b64encode(json.dumps(state_payload).encode()).decode()
    login_url = (
        f"{config.sso_url}/api/auth/login"
        f"?state={urllib.parse.quote(state_b64)}"
    )

    _console.print(
        f"[dim]Callback server listening on port [bold]{callback_port}[/bold].[/dim]"
    )
    _console.print(
        f"[dim]If you are on a remote host, forward this port from your laptop first:[/dim]\n"
        f"[dim]  ssh -L {callback_port}:localhost:{callback_port} <remote-host>[/dim]\n"
    )

    result: dict = {}
    done = threading.Event()

    server = HTTPServer(("localhost", callback_port), _make_handler(result, done))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    opened = webbrowser.open(login_url)
    if not opened:
        _console.print(
            f"[yellow]Could not open a browser automatically.[/yellow]\n"
            f"Please visit this URL to authenticate:\n\n  [bold]{login_url}[/bold]\n"
        )

    timed_out = not done.wait(timeout=timeout)
    server.shutdown()

    if timed_out:
        raise RuntimeError(
            f"Login timed out after {timeout} seconds. Please try again."
        )
    if "error" in result:
        raise RuntimeError(result["error"])

    return result["user"]
