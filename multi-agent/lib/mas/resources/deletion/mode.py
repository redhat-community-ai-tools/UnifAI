from enum import Enum


class DeleteMode(str, Enum):
    """Force-delete modes for in-use resources."""

    REPLACE = "replace"
    DETACH = "detach"
    CASCADE = "cascade"
