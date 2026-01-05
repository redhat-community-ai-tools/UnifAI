"""
resources/validation/resolver.py

DependencyResolver - resolves resources with their transitive dependencies.
Returns rids in topological order (dependencies first).
"""

from typing import List, Set

from resources.registry import ResourcesRegistry


class DependencyResolver:
    """
    Resolves resources with their transitive dependencies.
    
    Uses post-order traversal to ensure dependencies come before dependents.
    Handles circular references by tracking visited nodes.
    
    Returns a list of rids in dependency order (deps first, self last).
    """

    def __init__(self, resource_registry: ResourcesRegistry):
        """
        Initialize the resolver.
        
        Args:
            resource_registry: Registry for fetching resources
        """
        self._registry = resource_registry

    def resolve_with_deps(self, rid: str) -> List[str]:
        """
        Resolve a resource and all its transitive dependencies.
        
        Returns rids in dependency order (deps first, self last).
        Uses post-order traversal which naturally produces topological order.
        """
        visited: Set[str] = set()
        return self._resolve_recursive(rid, visited)

    def _resolve_recursive(
        self,
        rid: str,
        visited: Set[str],
    ) -> List[str]:
        """Post-order traversal for dependency resolution."""
        if rid in visited:
            return []  # Already processed (handles cycles)

        visited.add(rid)

        try:
            resource = self._registry.get(rid)
        except KeyError:
            return []  # Resource not found - skip

        result: List[str] = []

        # First: process all dependencies (depth-first)
        for dep_rid in resource.nested_refs:
            result.extend(self._resolve_recursive(dep_rid, visited))

        # Then: append self (post-order)
        result.append(rid)

        return result
