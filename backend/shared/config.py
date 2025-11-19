from dataclasses import dataclass

@dataclass(frozen=True)
class ChunkerConfig:
    max_tokens_per_chunk: int = 500
    overlap_tokens: int       = 50
    time_window_seconds: int  = 300
    chunk_size: int           = 800
    chunk_overlap: int        = 100

@dataclass(frozen=True)
class EmbeddingConfig:
    type: str        = "sentence_transformer"
    model_name: str  = "all-MiniLM-L6-v2"
    batch_size: int  = 32

@dataclass(frozen=True)
class StorageConfig:
    type: str            = "qdrant"
    collection_name: str = "data_source" 