from typing import Any, Dict, Optional

from mas.core.identity import Identity


def identity_q(identity: Optional[Identity]) -> Dict[str, Any]:
    """Build a MongoDB filter scoped to an identity (type + id).

    Returns an empty dict when *identity* is ``None`` so the filter matches
    all documents — used by listing methods that are optionally scoped.
    """
    if identity is None:
        return {}
    return {
        "identity.type": identity.type.value,
        "identity.id": identity.id,
    }
