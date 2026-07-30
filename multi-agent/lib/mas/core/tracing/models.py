from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class ObservationHandle:
    """Mutable handle yielded by tracing context managers.

    Callers use ``update()`` to attach output, token usage, or metadata
    to the current observation after the traced operation completes.
    """

    _update_fn: Callable[..., None] = field(repr=False)

    def update(
        self,
        *,
        output: Any = None,
        usage_details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        level: Optional[str] = None,
        status_message: Optional[str] = None,
    ) -> None:
        self._update_fn(
            output=output,
            usage_details=usage_details,
            metadata=metadata,
            level=level,
            status_message=status_message,
        )
