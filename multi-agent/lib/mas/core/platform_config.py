from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformConfig:
    """Static platform infrastructure settings exposed to elements.

    Constructed by the composition root from AppConfig.
    Domain code never imports AppConfig — only this contract.

    Adding a new platform concern means adding one field here and
    wiring it in the container.
    """

    shared_storage: str = "/app/shared"
