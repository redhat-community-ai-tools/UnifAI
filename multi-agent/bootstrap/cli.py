"""
MAS CLI — single entry point for all runtime commands.

Each command lazily imports only its own dependencies so that
``mas api`` works without temporalio and ``mas temporal-worker``
works without Flask.  The composition root (AppContainer) is
created here and passed into the adapters — adapters never
assemble the world themselves.

After ``pip install -e .`` (or ``pip install mas[all]``) run::

    mas --help
    mas api dev
    mas api serve --workers 4 --threads 2
    mas temporal-worker --threads 20
"""
from __future__ import annotations

import typer

app = typer.Typer(
    name="mas",
    help="MAS — Multi-Agent System orchestration engine.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

api_app = typer.Typer(
    name="api",
    help="HTTP API server commands.",
    no_args_is_help=True,
)
app.add_typer(api_app, name="api")


def _build_container():
    """Shared bootstrap: config → container."""
    import logging
    import os

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    from config.app_config import AppConfig
    from bootstrap.container import AppContainer

    cfg = AppConfig.get_instance()
    return AppContainer(cfg), cfg


# ── API: dev ─────────────────────────────────────────────────────

@api_app.command()
def dev(
    host: str = typer.Option(None, help="Bind address (default: from config)"),
    port: int = typer.Option(None, help="Bind port (default: from config)"),
):
    """Start the Flask development server with auto-reload."""
    container, cfg = _build_container()

    from inbound.flask.flask_app import create_app

    flask_app = create_app(container, config=cfg)
    bind_host = host or cfg.hostname
    bind_port = port or int(cfg.port)
    flask_app.run(host=bind_host, port=bind_port, debug=True)


# ── API: serve ───────────────────────────────────────────────────

@api_app.command()
def serve(
    host: str = typer.Option(None, help="Bind address (default: from config)"),
    port: int = typer.Option(None, help="Bind port (default: from config)"),
    workers: int = typer.Option(4, envvar="GUNICORN_WORKERS", help="Gunicorn worker processes"),
    threads: int = typer.Option(1, envvar="GUNICORN_THREADS", help="Gunicorn threads per worker"),
    timeout: int = typer.Option(120, envvar="GUNICORN_TIMEOUT", help="Gunicorn request timeout (seconds)"),
):
    """Start the production Gunicorn API server."""
    import sys

    _, cfg = _build_container()
    bind_host = host or cfg.hostname
    bind_port = port or int(cfg.port)

    sys.argv = [
        "gunicorn",
        "--bind", f"{bind_host}:{bind_port}",
        "--workers", str(workers),
        "--threads", str(threads),
        "--timeout", str(timeout),
        "--access-logfile", "-",
        "--error-logfile", "-",
        "run.wsgi:application",
    ]
    from gunicorn.app.wsgiapp import run as gunicorn_run
    gunicorn_run()


# ── Temporal worker ──────────────────────────────────────────────

@app.command("temporal-worker")
def temporal_worker(
    threads: int = typer.Option(10, help="Activity thread pool size and max concurrent activities"),
    max_workflow_tasks: int = typer.Option(0, help="Max concurrent workflow tasks (0 = unlimited)"),
    workflow_pollers: int = typer.Option(5, help="Workflow task poller count"),
    activity_pollers: int = typer.Option(5, help="Activity task poller count"),
):
    """Start a Temporal worker process."""
    import asyncio
    from inbound.temporal.worker import run_worker

    container, _ = _build_container()
    asyncio.run(run_worker(
        container,
        threads=threads,
        max_workflow_tasks=max_workflow_tasks or None,
        workflow_pollers=workflow_pollers,
        activity_pollers=activity_pollers,
    ))
