from typing import Protocol, runtime_checkable


@runtime_checkable
class RetrievalIdentity(Protocol):
    """Identity contract for access-controlled retrieval.

    Defined in the retriever layer (DIP — consumer owns the abstraction).
    ``ExecutionContextHolder`` satisfies this structurally via its
    forwarding ``.scope`` and ``.identity_id`` properties.
    """

    @property
    def scope(self) -> str: ...

    @property
    def identity_id(self) -> str: ...
