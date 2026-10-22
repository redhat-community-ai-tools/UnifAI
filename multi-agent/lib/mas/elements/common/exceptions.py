from typing import Any, Optional


class PluginConfigurationError(Exception):
    """
    Raised when a plugin factory fails to accept or create an instance from a config.

    Attributes:
        message: explanation of the failure (server-side only: it may embed the
            original exception text and the config, never show it to a caller).
        config:   the config dict that caused the error.
        category: element category (e.g. ``tool``) when known; a plain identifier.
        element_type: element type (e.g. ``memory``) when known; a plain identifier.
    """

    def __init__(
        self,
        message: str,
        config: Any,
        *,
        category: Optional[str] = None,
        element_type: Optional[str] = None,
    ):
        super().__init__(f"{message} | config={config!r}")
        self.message = message
        self.config = config
        self.category = category
        self.element_type = element_type
