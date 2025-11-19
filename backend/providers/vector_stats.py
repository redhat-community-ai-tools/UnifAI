from typing import Dict
from utils.storage.vector_storage_factory import VectorStorageFactory


def get_chunks_counts() -> Dict[str, int]:
    """Return exact slack/document/total chunk counts from Qdrant using shared storage factory."""
    # Build minimal storage instances for each collection to re-use client/config
    slack_storage = VectorStorageFactory.create({
        "type": "qdrant",
        "collection_name": "slack_data",
        "embedding_dim": 1,
    })
    doc_storage = VectorStorageFactory.create({
        "type": "qdrant",
        "collection_name": "document_data",
        "embedding_dim": 1,
    })

    slack = slack_storage.count(exact=True)
    document = doc_storage.count(exact=True)
    return {"slack": slack, "document": document, "total": slack + document}


