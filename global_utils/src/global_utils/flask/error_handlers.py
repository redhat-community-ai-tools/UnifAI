"""App-level Flask error handlers with a standard JSON error shape."""
from __future__ import annotations

import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from global_utils.utils.logging_config import get_request_id

logger = logging.getLogger(__name__)


def _error_payload(message: str, error_type: str) -> dict:
    return {
        "error": message,
        "error_type": error_type,
        "request_id": get_request_id(),
    }


def register_error_handlers(app: Flask) -> None:
    """Register handlers for uncaught HTTPException and Exception."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        error_type = (exc.name or "HTTP_ERROR").upper().replace(" ", "_")
        payload = _error_payload(exc.description or exc.name or "HTTP error", error_type)
        return jsonify(payload), exc.code or 500

    @app.errorhandler(Exception)
    def handle_uncaught_exception(exc: Exception):
        logger.exception(
            "unhandled.exception",
            extra={"event": "unhandled.exception", "error_type": type(exc).__name__},
        )
        payload = _error_payload("Internal server error", "INTERNAL_ERROR")
        return jsonify(payload), 500
