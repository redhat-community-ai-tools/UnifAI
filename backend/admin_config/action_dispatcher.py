"""
ActionDispatcher — fires HTTP POST to other services when
an admin_config section is updated.

Routing is defined in the admin_config template via
``on_update_target`` (service key) and ``on_update_endpoint`` (path).
The dispatcher only needs a service-name → base-URL map so it can
resolve full URLs at runtime.
"""

import logging
from typing import Dict, Optional

import requests

from global_utils.flask.correlation import correlation_headers

logger = logging.getLogger(__name__)


class ActionDispatcher:
    """Dispatch side-effect HTTP calls to internal services."""

    def __init__(self, service_urls: Dict[str, str], timeout: int = 15):
        self._service_urls = service_urls
        self._timeout = timeout

    def dispatch(
        self,
        action: Optional[str],
        target: Optional[str],
        endpoint: Optional[str],
    ) -> bool:
        """
        POST to *target* service at *endpoint*.

        Returns True if the call succeeded (or if no routing is
        configured).  Returns False on HTTP / network errors.
        """
        if not target or not endpoint:
            return True

        base_url = self._service_urls.get(target)
        if base_url is None:
            logger.warning(
                "No base URL configured for service '%s' (action '%s')",
                target,
                action,
            )
            return False

        url = base_url.rstrip("/") + endpoint
        try:
            logger.info("Dispatching action '%s' → %s", action, url)
            resp = requests.post(
                url,
                json={},
                headers=correlation_headers() or None,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            logger.info(
                "Action '%s' dispatched successfully (status=%s)",
                action,
                resp.status_code,
            )
            return True
        except Exception:
            logger.exception("Failed to dispatch action '%s' to %s", action, url)
            return False
