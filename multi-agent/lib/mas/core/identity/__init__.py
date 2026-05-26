"""
Identity domain package.

Re-exports the core symbols so that existing imports like
``from mas.core.identity import Identity, IdentityType`` continue to work.
"""
from mas.core.identity.models import Identity, IdentityType, resolve_identity
from mas.core.identity.ports import IdentityProvider

__all__ = ["Identity", "IdentityType", "IdentityProvider", "resolve_identity"]
