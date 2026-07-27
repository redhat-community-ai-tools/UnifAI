"""
Gunicorn configuration for the identity service.

Key fix: os.register_at_fork() coordinates C-level fork calls from native
libraries (OpenSSL/cryptography used by joserfc for JWT verification).
Without this, the JWKS cache expiry at ~10 minutes triggers uncoordinated
forks that produce orphan processes and spurious "Worker exited with code 1"
log noise.
"""
import faulthandler
import logging
import os
import sys
import threading


def on_starting(server):
    """Register a fork-coordination handler in the master process."""
    def _before_fork():
        pass  # Coordinates C-level fork calls via pthread_atfork

    os.register_at_fork(before=_before_fork)


def post_fork(server, worker):
    """Per-worker setup: crash diagnostics and unhandled-exception logging."""
    faulthandler.enable(file=sys.stderr)

    _log = logging.getLogger("gunicorn.error")

    def _thread_exc_handler(args):
        _log.error(
            "Unhandled exception in background thread '%s'",
            args.thread.name if args.thread else "unknown",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_exc_handler

    def _unraisable_handler(unraisable):
        _log.error(
            "Unraisable exception: %s",
            unraisable.err_msg or unraisable.object,
            exc_info=(unraisable.exc_type, unraisable.exc_value, unraisable.exc_tb),
        )

    sys.unraisablehook = _unraisable_handler
