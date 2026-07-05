from typing import Protocol, runtime_checkable


@runtime_checkable
class RetrievalIdentity(Protocol):
    """Identity contract for access-controlled retrieval.

    Defined in the retriever layer (DIP — consumer owns the abstraction).
    ``ExecutionContextHolder`` satisfies this structurally via its
    forwarding ``.session_cookie`` property.
    """

    @property
    def session_cookie(self) -> str: ...
