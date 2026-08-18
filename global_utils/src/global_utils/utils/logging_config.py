"""Unified structured logging for UnifAI services (OpenObserve-ready JSON)."""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional, Union

_EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_.]*$")

# ---------------------------------------------------------------------------
# Correlation context (populated by middleware / callers — Step 3)
# ---------------------------------------------------------------------------

_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)

_RESERVED_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }
)

_TOP_LEVEL_FIELDS = frozenset(
    {
        "timestamp",
        "level",
        "service",
        "environment",
        "logger",
        "message",
        "event",
        "request_id",
        "session_id",
        "pod",
        "deployment",
        "exception",
        "context",
    }
)

_LOCAL_ENVIRONMENTS = frozenset({"local", "development", "dev"})

_CONFIGURED = False


def set_request_id(request_id: Optional[str]) -> None:
    """Bind request_id for the current context (asyncio task / thread)."""
    _request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    return _request_id_var.get()


def set_session_id(session_id: Optional[str]) -> None:
    """Bind session_id for the current context."""
    _session_id_var.set(session_id)


def get_session_id() -> Optional[str]:
    return _session_id_var.get()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name)


def emit(
    logger: logging.Logger,
    level: Union[int, str],
    event: str,
    **fields: Any,
) -> None:
    """Log a structured event: message and ``event`` field are both ``event``."""
    if isinstance(level, str):
        level_no = getattr(logging, level.upper(), logging.INFO)
    else:
        level_no = level
    extra = {"event": event, **fields}
    logger.log(level_no, event, extra=extra)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _record_extras(record: logging.LogRecord) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in _RESERVED_RECORD_ATTRS or key.startswith("_"):
            continue
        extras[key] = value
    return extras


class UnifAIJSONFormatter(logging.Formatter):
    """Emit one JSON object per line for OpenObserve ingest."""

    def __init__(self, service_name: str, environment: str, pod: Optional[str], deployment: Optional[str]):
        super().__init__()
        self.service_name = service_name
        self.environment = environment
        self.pod = pod
        self.deployment = deployment

    def format(self, record: logging.LogRecord) -> str:
        extras = _record_extras(record)

        event = extras.pop("event", None)
        request_id = extras.pop("request_id", None)
        if request_id is None:
            request_id = get_request_id()
        session_id = extras.pop("session_id", None)
        if session_id is None:
            session_id = get_session_id()

        nested_context = extras.pop("context", None)
        context: dict[str, Any] = {}
        if isinstance(nested_context, dict):
            context.update(nested_context)
        for key, value in extras.items():
            if key in _TOP_LEVEL_FIELDS:
                continue
            context[key] = value

        message = record.getMessage()
        if event is None and _EVENT_NAME_RE.match(message):
            event = message
        payload: dict[str, Any] = {
            "timestamp": _utc_timestamp(),
            "level": record.levelname.lower(),
            "service": self.service_name,
            "environment": self.environment,
            "logger": record.name,
            "message": message,
            "event": event,
            "request_id": request_id,
            "session_id": session_id,
            "pod": self.pod,
            "deployment": self.deployment,
        }

        if context:
            payload["context"] = context

        if record.exc_info:
            exc_type, exc_val, exc_tb = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__ if exc_type else "Exception",
                "message": str(exc_val),
                "stacktrace": "".join(traceback.format_exception(exc_type, exc_val, exc_tb)),
            }

        return json.dumps(payload, ensure_ascii=False, default=str)


class UnifAIConsoleFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        extras = _record_extras(record)
        request_id = extras.pop("request_id", None) or get_request_id()
        session_id = extras.pop("session_id", None) or get_session_id()
        event = extras.pop("event", None)
        extras.pop("context", None)

        parts = [
            _utc_timestamp(),
            record.levelname,
            self.service_name,
            record.name,
            record.getMessage(),
        ]
        if event:
            parts.append(f"event={event}")
        if request_id:
            parts.append(f"request_id={request_id}")
        if session_id:
            parts.append(f"session_id={session_id}")
        if extras:
            parts.append(f"context={extras}")
        if record.exc_info:
            parts.append(self.formatException(record.exc_info))
        return " ".join(parts)


def configure_logging(
    service_name: str,
    *,
    log_level: Optional[str] = None,
    environment: Optional[str] = None,
    log_dir: Optional[str] = None,
    enable_file: Optional[bool] = None,
) -> None:
    """
    Idempotent process-wide setup. Call once at boot (create_app / worker entry).

    Env resolution (explicit args win):
      LOG_LEVEL      default "INFO"
      ENVIRONMENT    default "production"  # local|development|dev → console; else JSON
      LOG_DIR        default "/var/log/unifai"
      POD_NAME, APP_VERSION  → pod / deployment fields

    Handlers:
      - always: StreamHandler(sys.stdout)
      - file: RotatingFileHandler(LOG_DIR/app.log, 50MB, 10 backups)
        if enable_file is True, or (enable_file is None and LOG_DIR is writable)
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved_level = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    resolved_env = (environment or os.getenv("ENVIRONMENT", "production")).lower()
    resolved_log_dir = Path(log_dir or os.getenv("LOG_DIR", "/var/log/unifai"))
    pod = os.getenv("POD_NAME") or os.getenv("HOSTNAME") or None
    deployment = os.getenv("APP_VERSION") or None

    level = getattr(logging, resolved_level, logging.INFO)
    use_json = resolved_env not in _LOCAL_ENVIRONMENTS

    if use_json:
        formatter: logging.Formatter = UnifAIJSONFormatter(
            service_name=service_name,
            environment=resolved_env,
            pod=pod,
            deployment=deployment,
        )
    else:
        formatter = UnifAIConsoleFormatter(service_name=service_name)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setLevel(level)
    stdout.setFormatter(formatter)
    root.addHandler(stdout)

    should_file = enable_file
    if should_file is None:
        should_file = resolved_log_dir.is_dir() and os.access(resolved_log_dir, os.W_OK)

    if should_file:
        try:
            resolved_log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                resolved_log_dir / "app.log",
                maxBytes=50 * 1024 * 1024,
                backupCount=10,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            # Mount missing or not writable — stdout-only is fine (local / OO ingest).
            pass

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    _CONFIGURED = True
    logging.getLogger(__name__).info(
        "logging.configured",
        extra={
            "event": "logging.configured",
            "log_level": resolved_level,
            "log_environment": resolved_env,
            "file_logging": bool(should_file),
        },
    )


# Backward compatible module-level logger (celery helpers, etc.)
logger = logging.getLogger("global_utils")
