"""Immutable snapshot of "who is calling and what can they see".

Resolved once at the inbound (Flask) boundary and carried as a single
parameter through services and resolvers, replacing the ``identity`` +
``is_admin`` pair that was previously threaded individually through every
method signature along the resources/blueprints call chain.
"""
from dataclasses import dataclass
from typing import Optional

from mas.core.identity import Identity


@dataclass(frozen=True)
class CallerScope:
    """Immutable snapshot of the caller's identity and access level.

    ``frozen=True`` so it can never be accidentally mutated mid-chain.
    Lives in the domain layer (not Flask) because "who is this caller" is
    a domain concept, not an HTTP concern.
    """
    identity: Optional[Identity] = None
    is_admin: bool = False
