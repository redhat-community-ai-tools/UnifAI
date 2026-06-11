from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mas.core.execution_context import ExecutionContextHolder
    from mas.core.auth.service import AuthService
    from mas.core.platform_config import PlatformConfig


@dataclass
class ElementDeps:
    """Cross-cutting dependencies injected into elements at build time.

    Typed replacement for ``**kwargs`` in the build chain.  Adding a new
    cross-cutting concern means adding one field here — no signature
    changes anywhere else.
    """

    execution_ctx: Optional[ExecutionContextHolder] = field(default=None)
    auth_service: Optional[AuthService] = field(default=None)
    platform_config: Optional[PlatformConfig] = field(default=None)
