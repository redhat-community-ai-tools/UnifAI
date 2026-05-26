"""Outbound identity adapters — implementations of the IdentityProvider port."""
from outbound.identity.dev_provider import DevIdentityProvider
from outbound.identity.noop_provider import NoOpIdentityProvider

__all__ = ["DevIdentityProvider", "NoOpIdentityProvider"]
