from utils.embedding.embedding_generator_factory import EmbeddingGeneratorFactory
from utils.storage.vector_storage_factory import VectorStorageFactory

def rag_flow():
    # Create embedding generator
    embedding_config = {
        "type": "sentence_transformer",
        "model_name": "all-MiniLM-L6-v2",
        "batch_size": 32
    }
    embedding_generator = EmbeddingGeneratorFactory.create(embedding_config)
    
    # Create vector storage
    storage_config = {
        "type": "qdrant",
        "collection_name": "pdf_doc_data",
        "embedding_dim": embedding_generator.embedding_dim,
        "url": "http://localhost",
        "port": 6333
    }
    vector_storage = VectorStorageFactory.create(storage_config)
    vector_storage.initialize()
    
    # Example search
    query = "Assuming I want to install docling, what should be my inital steps?"
    # query = "To use Docling, you can simply"
    
    query_embedding = embedding_generator.generate_query_embedding(query)
    
    search_results = vector_storage.search(
        query_embedding=query_embedding,
        top_k=2,
        # filters={"metadata.source_path": "./data/pdfs/2408.09869v5.pdf"}
    )
    
    print(f"Search results for: '{query}'")
    for result in search_results:
        print(f"Score: {result['score']:.4f}, Content: {result['content']}")