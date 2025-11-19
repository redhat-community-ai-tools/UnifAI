from utils.embedding.embedding_generator_factory import EmbeddingGeneratorFactory
from utils.storage.vector_storage_factory import VectorStorageFactory

def embedding_flow():
    # Sample chunk
    sample_chunks = [
        {
            "text": "This is a sample Slack message about the project timeline.",
            "metadata": {
                "source_type": "slack_conversation",
                "channel_name": "project-updates",
                "time_range": "1609459200.000700-1609459230.000800",
                "message_count": 3
            }
        },
        {
            "text": "The new feature will be ready by next sprint according to the engineering team.",
            "metadata": {
                "source_type": "slack_thread",
                "channel_name": "engineering",
                "thread_id": "1609460000.001000",
                "time_range": "1609460000.001000-1609460120.001200",
                "message_count": 3
            }
        }
    ]
    
    # Create embedding generator
    embedding_config = {
        "type": "sentence_transformer",
        "model_name": "all-MiniLM-L6-v2",
        "batch_size": 32
    }
    
    embedding_generator = EmbeddingGeneratorFactory.create(embedding_config)
    
    # Generate embeddings
    enriched_chunks = embedding_generator.generate_embeddings(sample_chunks)
    
    # Create vector storage
    storage_config = {
        "type": "qdrant",
        "collection_name": "slack_data",
        "embedding_dim": embedding_generator.embedding_dim,
        "url": "http://localhost",
        "port": 6333
    }
    
    vector_storage = VectorStorageFactory.create(storage_config)
    
    # Initialize storage
    vector_storage.initialize()
    
    # Store embeddings
    vector_storage.store_embeddings(enriched_chunks)
    
    # Example search
    query = "When will the new feature be ready?"
    query_embedding = embedding_generator.generate_query_embedding(query)
    
    search_results = vector_storage.search(
        query_embedding=query_embedding,
        top_k=2,
        filters={"metadata.channel_name": "engineering"}
    )
    
    print(f"Search results for: '{query}'")
    for result in search_results:
        print(f"Score: {result['score']:.4f}, Text: {result['text']}")