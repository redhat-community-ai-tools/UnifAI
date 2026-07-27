"""
Heartbeat decorator for Temporal activities.

Decorates a sync activity so that a background thread sends periodic
heartbeats to Temporal while the activity body runs.  This keeps the
activity alive and enables the SDK's built-in cancellation injection.

The SDK itself handles cancellation delivery: when a cancel is received
via heartbeat response, it injects temporalio.exceptions.CancelledError
into the sync activity thread automatically.  This decorator only needs
to keep heartbeating — the kill is the SDK's job.

Uses contextvars.copy_context() to propagate the Temporal activity
context to the heartbeat thread (activity.heartbeat() requires it).

Usage::

    @activity.defn(name="my_activity")
    @heartbeat(interval=5)
    def my_activity(self, params: Params) -> Result:
        return do_work(params)
"""
import contextvars
import threading
import functools
from typing import Any, Callable, TypeVar

from temporalio import activity

T = TypeVar("T")


def heartbeat(interval: float = 5):
    """
    Decorator that sends periodic heartbeats while a sync activity runs.

    Cancellation is handled by the Temporal SDK's built-in thread
    exception raiser — this decorator only keeps the activity alive
    so the server can deliver cancel signals.

    Args:
        interval: Seconds between heartbeat pings. Should be less than
                  half the heartbeat_timeout set on the activity call.
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            stop = threading.Event()
            ctx = contextvars.copy_context()

            def _beat():
                while not stop.wait(interval):
                    try:
                        ctx.run(activity.heartbeat, "running")
                    except Exception:
                        return

            t = threading.Thread(target=_beat, daemon=True)
            t.start()
            try:
                return fn(*args, **kwargs)
            finally:
                stop.set()

        return wrapper
    return decorator
