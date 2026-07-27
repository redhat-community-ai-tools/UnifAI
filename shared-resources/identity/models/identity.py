"""
Identity model re-export.

The canonical definition lives in ``global_utils.identity``.
This module re-exports it so that existing ``from mas.core.identity import …``
imports continue to work without modification.
"""
from global_utils.identity import Identity, IdentityType  # noqa: F401

__all__ = ["Identity", "IdentityType"]
