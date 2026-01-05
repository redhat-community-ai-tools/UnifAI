from typing import Any, Set
from pydantic import BaseModel
from core.ref.models import Ref


class RefWalker:
    """
    Pure utility: depth-first traversal that collects resource IDs (rid strings)
    from Ref objects found in an object graph.
    """

    @staticmethod
    def external_rids(root: Any) -> Set[str]:
        """Returns only external refs ($ref:xxx) - for saved resource dependencies."""
        bucket: set[str] = set()
        RefWalker._walk(root, bucket, external_only=True)
        return bucket

    @staticmethod
    def all_rids(root: Any) -> Set[str]:
        """Returns all refs (external + inline) - for blueprint internal dependencies."""
        bucket: set[str] = set()
        RefWalker._walk(root, bucket, external_only=False)
        return bucket

    @staticmethod
    def _walk(node: Any, bucket: set[str], external_only: bool) -> None:
        if isinstance(node, Ref):
            if not external_only or node.is_external_ref():
                bucket.add(node.ref)
            return

        if isinstance(node, BaseModel):
            for v in node.__dict__.values():
                RefWalker._walk(v, bucket, external_only)
            return

        if isinstance(node, dict):
            for v in node.values():
                RefWalker._walk(v, bucket, external_only)
            return

        if isinstance(node, (list, tuple)):
            for v in node:
                RefWalker._walk(v, bucket, external_only)
