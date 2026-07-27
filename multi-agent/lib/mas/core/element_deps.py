from dataclasses import dataclass, field
from typing import Optional

from mas.core.execution_context import ExecutionContextHolder
from mas.core.auth.service import AuthService
from mas.core.platform_config import PlatformConfig


@dataclass
class ElementBuildContext:
    """Cross-cutting dependencies available during element construction.

    Carries stable services and runtime bridges that elements capture
    at build time.  NOT for per-run concerns (channel, HITL gate) —
    those flow through ``NodeRuntimeBinder`` at execution time.

    Adding a new build-time concern means adding one field here —
    no signature changes anywhere else.
    """

    execution_ctx: Optional[ExecutionContextHolder] = field(default=None)
    auth_service: Optional[AuthService] = field(default=None)
    platform_config: Optional[PlatformConfig] = field(default=None)
