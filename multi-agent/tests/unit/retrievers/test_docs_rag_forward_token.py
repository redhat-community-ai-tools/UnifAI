"""docs_rag retriever: forward_user_token sends the user's own token to the RAG service."""
from unittest.mock import MagicMock

from mas.core.element_deps import ElementBuildContext
from mas.core.execution_context import ExecutionContext, ExecutionContextHolder
from mas.core.identity import resolve_identity
from mas.core.identity_forwarding import IdentityTokenSource
from mas.elements.retrievers.docs_rag.config import DocsRagRetrieverConfig
from mas.elements.retrievers.docs_rag.docs_rag_retriever_factory import DocsRagRetrieverFactory


class Source(IdentityTokenSource):
    def bind(self, session_id, identity_session_id, username):
        pass

    def get_access_token(self, session_id, username):
        return f"tok-{username}"


def _deps():
    holder = ExecutionContextHolder()
    holder.context = ExecutionContext(session_id="s1", identity=resolve_identity("alice", "user"))
    return ElementBuildContext(execution_ctx=holder, identity_token_source=Source())


def _retriever(forward):
    r = DocsRagRetrieverFactory().create(DocsRagRetrieverConfig(forward_user_token=forward), deps=_deps())
    r._provider = MagicMock()
    r._provider.query.return_value = MagicMock(matches=[])
    return r


def test_forwarding_adds_the_users_bearer_token():
    r = _retriever(True)
    r.retrieve("q")
    kwargs = r._provider.query.call_args.kwargs
    assert kwargs["extra_headers"] == {"Authorization": "Bearer tok-alice"}
    assert kwargs["authenticated_user"] == "alice"


def test_default_sends_no_token():
    r = _retriever(False)
    r.retrieve("q")
    assert r._provider.query.call_args.kwargs["extra_headers"] is None
