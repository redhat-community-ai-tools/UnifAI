"""QdrantVectorRepository: hybrid (dense + BM25 sparse) search, stable point ids, collection checks.

Runs against qdrant-client's in-memory local mode, which implements named and sparse vectors,
the IDF modifier, prefetch and RRF fusion.
"""
from unittest.mock import MagicMock

import numpy as np
import pytest
import qdrant_client
from qdrant_client.http import models as qmodels

from core.vector.domain.embedder import EmbeddingGenerationError
from core.vector.domain.model import VectorChunk
from infrastructure.embedding.embedding_generator import DefaultEmbeddingGenerator
from infrastructure.qdrant.qdrant_vector_repository import (
    CollectionMismatchError,
    QdrantVectorRepository,
)
from infrastructure.qdrant.sparse_encoder import HashingBM25Encoder, tokenize

pytestmark = pytest.mark.unit

# Toy 3-d "embeddings": axis 0 = certificates/TLS, axis 1 = networking/routes, axis 2 = storage.
DOCS = [
    ("tls", "Rotate the router certificate when ERR_TLS_CERT_ALTNAME_INVALID appears.", [1.0, 0.0, 0.1]),
    ("route", "A Route exposes a Service outside the cluster through the ingress controller.", [0.0, 1.0, 0.0]),
    ("pvc", "Procédure: étendre un volume persistant attaché à un pod.", [0.0, 0.1, 1.0]),
]


def repo(client, hybrid=True, dim=3, name="docs"):
    r = QdrantVectorRepository(collection_name=name, embedding_dim=dim, url="http://unused", hybrid=hybrid, client=client)
    r.initialize()
    return r


def chunks(owner="alice"):
    return [VectorChunk(text=text, embedding=emb, metadata={"source_id": sid, "chunk_index": 0, "owner_id": owner})
            for sid, text, emb in DOCS]


@pytest.fixture
def client():
    return qdrant_client.QdrantClient(":memory:")


def test_tokenize_folds_case_and_accents_and_keeps_identifiers():
    assert tokenize("Procédure ÉTENDRE ERR_TLS_CERT x 4") == ["procedure", "etendre", "err_tls_cert", "4"]


def test_document_weights_saturate_and_query_weights_are_flat():
    enc = HashingBM25Encoder()
    doc = enc.encode_document("route route route ingress")
    assert len(doc.indices) == 2 and max(doc.values) < 2.2 and min(doc.values) == pytest.approx(1.0)
    q = enc.encode_query("route route ingress")
    assert q.values == [1.0, 1.0] and q.indices == sorted(q.indices)


def test_hybrid_collection_has_named_dense_and_idf_sparse_vectors(client):
    repo(client)
    params = client.get_collection("docs_hybrid").config.params
    assert params.vectors["dense"].size == 3
    assert params.sparse_vectors["sparse"].modifier == qmodels.Modifier.IDF


def test_rerunning_a_pipeline_overwrites_instead_of_duplicating(client):
    r = repo(client)
    r.store(chunks())
    r.store(chunks())
    assert r.count(exact=True) == len(DOCS)


def test_exact_identifier_is_found_by_the_sparse_side(client):
    r = repo(client)
    r.store(chunks())
    # The query embedding points at "storage": dense alone would rank pvc first.
    hits = r.search([0.0, 0.0, 1.0], top_k=2, filters={"metadata.owner_id": "alice"}, query_text="ERR_TLS_CERT_ALTNAME_INVALID")
    assert "tls" in [h.metadata["source_id"] for h in hits]


def test_paraphrase_is_found_by_the_dense_side(client):
    r = repo(client)
    r.store(chunks())
    hits = r.search([0.0, 1.0, 0.0], top_k=1, filters={"metadata.owner_id": "alice"}, query_text="publish an app to users")
    assert hits[0].metadata["source_id"] == "route"


def test_filters_apply_to_both_candidate_lists(client):
    r = repo(client)
    r.store(chunks("alice"))
    r.store([VectorChunk(text="ERR_TLS_CERT_ALTNAME_INVALID secret runbook", embedding=[1.0, 0.0, 0.0],
                         metadata={"source_id": "bob-doc", "chunk_index": 0, "owner_id": "bob"})])
    hits = r.search([1.0, 0.0, 0.0], top_k=5, filters={"metadata.owner_id": "alice"}, query_text="ERR_TLS_CERT_ALTNAME_INVALID")
    assert hits and all(h.metadata["owner_id"] == "alice" for h in hits)


def test_list_filters_match_any_value(client):
    r = repo(client, hybrid=False)
    r.store(chunks())
    hits = r.search([0.3, 0.3, 0.3], top_k=5, filters={"metadata.source_id": ["tls", "pvc"]})
    assert {h.metadata["source_id"] for h in hits} == {"tls", "pvc"}


def test_legacy_dense_collection_is_untouched_by_hybrid(client):
    legacy = repo(client, hybrid=False)
    legacy.store(chunks())
    repo(client, hybrid=True)
    assert {c.name for c in client.get_collections().collections} == {"docs", "docs_hybrid"}
    assert legacy.count(exact=True) == len(DOCS)


def test_existing_collection_with_another_dimension_is_refused(client):
    repo(client, hybrid=False, dim=3)
    with pytest.raises(CollectionMismatchError, match="3-dimension"):
        repo(client, hybrid=False, dim=1024)


def test_embedding_dimension_mismatch_fails_at_the_source():
    port = MagicMock(embedding_dim=1024, is_remote=True)
    port.encode_single.return_value = np.zeros(384)
    port.encode_texts.return_value = [np.zeros(384)]
    gen = DefaultEmbeddingGenerator(port)
    with pytest.raises(EmbeddingGenerationError, match="EMBEDDING_DIM"):
        gen.generate_query_embedding("q")
    with pytest.raises(EmbeddingGenerationError, match="EMBEDDING_DIM"):
        gen.generate_embeddings([{"text": "t"}])
