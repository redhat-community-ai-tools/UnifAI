"""Helpers for inspecting persisted, JSON-shaped resource configurations."""

from __future__ import annotations

from typing import Any


REF_PREFIX = "$ref:"


def extract_external_ref_ids(node: Any) -> set[str]:
    """Return IDs from explicit ``$ref:`` strings anywhere in *node*.

    Persisted resource configurations are plain dictionaries, so they no
    longer contain ``Ref`` model instances for ``RefWalker`` to inspect.  This
    is intentionally limited to explicit external references: ordinary string
    values must never be mistaken for resource dependencies.
    """
    refs: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, str):
            if value.startswith(REF_PREFIX):
                rid = value[len(REF_PREFIX):]
                if rid:
                    refs.add(rid)
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk(node)
    return refs
