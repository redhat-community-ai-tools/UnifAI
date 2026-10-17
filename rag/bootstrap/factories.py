"""
Factory classes for creating infrastructure instances.

Each factory encapsulates construction details for a specific component:
- DocumentConverterFactory / DocumentConnectorFactory  — document processing
- EmbeddingPortFactory / EmbeddingGeneratorFactory     — embedding generation
- VectorRepositoryFactory                              — vector storage

The from_app_config() classmethods on DocumentConnectorFactory and
EmbeddingGeneratorFactory encapsulate the local-vs-remote branching that
would otherwise leak into the composition root (app_container.py).
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from core.vector.domain.embedder import EmbeddingGenerator
from core.vector.domain.repository import VectorRepository
from core.connector.domain.base import DataConnector
from core.data_sources.types.document.domain.document_converter import DocumentConverterPort

logger = logging.getLogger(__name__)


class DocumentConverterFactory:
    """Factory for creating document converter port instances."""
    
    @staticmethod
    def create_local() -> DocumentConverterPort:
        """Create a local docling adapter."""
        from infrastructure.sources.document.converters import LocalDoclingAdapter
        return LocalDoclingAdapter()
    
    @staticmethod
    def create_remote(
        base_url: str,
        timeout: int = 300,
        poll_interval: int = 10,
        http_timeout: int = 60,
        image_export_mode: str = "placeholder",
        pdf_backend: str = "dlparse_v4",
    ) -> DocumentConverterPort:
        """Create a remote docling adapter."""
        from global_utils.docling import DoclingClient, DoclingService
        from infrastructure.sources.document.converters import RemoteDoclingAdapter
        
        client = DoclingClient(
            base_url=base_url,
            timeout=timeout,
            poll_interval=poll_interval,
            http_timeout=http_timeout,
        )
        service = DoclingService(
            client=client,
            image_export_mode=image_export_mode,
            pdf_backend=pdf_backend,
        )
        return RemoteDoclingAdapter(docling_service=service)


class DocumentConnectorFactory:
    """Factory for creating document connector instances."""
    
    @staticmethod
    def create(config: Dict[str, Any]) -> DataConnector:
        """
        Create a document connector instance.
        
        Args:
            config: Configuration dict with keys:
                - type: "local" or "remote"
                - service_url: URL (for remote)
                - timeout: Timeout in seconds (for remote)
                - config_manager: Optional DocConfigManager
        """
        from infrastructure.sources.document.connector import DocumentConnector
        from infrastructure.sources.document.config import DocConfigManager
        
        connector_type = config.get("type", "local")
        config_manager = config.get("config_manager") or DocConfigManager()
        
        if connector_type == "local":
            converter = DocumentConverterFactory.create_local()
        elif connector_type == "remote":
            service_url = config.get("service_url")
            if not service_url:
                raise ValueError(
                    "'service_url' is required for remote document connector type"
                )
            converter = DocumentConverterFactory.create_remote(
                base_url=service_url,
                timeout=config.get("timeout", 300),
                poll_interval=config.get("poll_interval", 10),
                http_timeout=config.get("http_timeout", 60),
                pdf_backend=config.get("pdf_backend", "dlparse_v4"),
            )
        else:
            raise ValueError(f"Unknown connector type: {connector_type}")
        
        return DocumentConnector(
            converter=converter,
            config_manager=config_manager,
        )


    @classmethod
    def from_app_config(cls, config) -> DataConnector:
        """
        Create the correct document connector based on AppConfig feature flags.

        Encapsulates the use_remote_docling decision so the composition root
        performs pure wiring without branching on configuration.

        Args:
            config: Application configuration with feature flags and service URLs.

        Returns:
            DocumentConnector wrapping RemoteDoclingAdapter if use_remote_docling
            is True, otherwise wrapping LocalDoclingAdapter.
        """
        if config.use_remote_docling:
            return cls.create({
                "type": "remote",
                "service_url": config.docling_service_url,
                "timeout": config.docling_service_timeout,
                "poll_interval": config.docling_poll_interval,
                "http_timeout": config.docling_http_timeout,
                "pdf_backend": config.docling_pdf_backend,
            })
        return cls.create({"type": "local"})


class EmbeddingPortFactory:
    """Factory for creating embedding port instances."""
    
    @staticmethod
    def create_local(
        model_name: str = "all-MiniLM-L6-v2",
        device_name: Optional[str] = None,
    ):
        """Create a local embedding adapter."""
        import torch
        from infrastructure.embedding.embedders import LocalEmbeddingAdapter

        resolved_device = device_name or ("cuda" if torch.cuda.is_available() else "cpu")
        return LocalEmbeddingAdapter(
            model_name=model_name,
            device=resolved_device,
        )
    
    @staticmethod
    def create_remote(
        base_url: str,
        timeout: int = 60,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_dim: int = 384,
    ):
        """Create a remote embedding adapter."""
        from global_utils.embedding import EmbeddingClient, EmbeddingService
        from infrastructure.embedding.embedders import RemoteEmbeddingAdapter
        
        client = EmbeddingClient(base_url=base_url, timeout=timeout)
        service = EmbeddingService(client=client, model_name=model_name)
        return RemoteEmbeddingAdapter(
            embedding_service=service,
            embedding_dim=embedding_dim,
        )


class EmbeddingGeneratorFactory:
    """Factory for creating embedding generator instances."""
    
    @staticmethod
    def create(config: Dict[str, Any]) -> EmbeddingGenerator:
        """
        Create an embedding generator instance.
        
        Args:
            config: Configuration dict with keys:
                - type: "local" or "remote"
                - model_name: Model name
                - batch_size: Batch size
                - device: Device (for local)
                - service_url: URL (for remote)
                - timeout: Timeout (for remote)
                - embedding_dim: Dimension (for remote)
        """
        from infrastructure.embedding.embedding_generator import DefaultEmbeddingGenerator
        
        generator_type = config.get("type", "local")
        batch_size = config.get("batch_size", 32)
        
        if generator_type == "local":
            port = EmbeddingPortFactory.create_local(
                model_name=config.get("model_name", "all-MiniLM-L6-v2"),
                device_name=config.get("device"),
            )
        elif generator_type == "remote":
            service_url = config.get("service_url")
            if not service_url:
                raise ValueError(
                    "'service_url' is required for remote embedding generator type"
                )
            port = EmbeddingPortFactory.create_remote(
                base_url=service_url,
                timeout=config.get("timeout", 60),
                model_name=config.get("model_name", "sentence-transformers/all-MiniLM-L6-v2"),
                embedding_dim=config.get("embedding_dim", 384),
            )
        else:
            raise ValueError(f"Unknown generator type: {generator_type}")
        
        return DefaultEmbeddingGenerator(port=port, batch_size=batch_size)


    @classmethod
    def from_app_config(cls, config) -> EmbeddingGenerator:
        """
        Create the correct embedding generator based on AppConfig feature flags.

        Encapsulates the use_remote_embedding decision so the composition root
        performs pure wiring without branching on configuration.

        Args:
            config: Application configuration with feature flags and service URLs.

        Returns:
            DefaultEmbeddingGenerator wrapping RemoteEmbeddingAdapter if
            use_remote_embedding is True, otherwise wrapping LocalEmbeddingAdapter.
        """
        if config.use_remote_embedding:
            return cls.create({
                "type": "remote",
                "service_url": config.embedding_service_url,
                "timeout": config.embedding_service_timeout,
                "model_name": config.embedding_service_model,
                "embedding_dim": config.embedding_dim,
            })
        return cls.create({"type": "local"})


class VectorRepositoryFactory:
    """Factory for creating vector repository instances."""
    
    @staticmethod
    def create(config: Dict[str, Any]) -> VectorRepository:
        """Create a vector repository instance."""
        from config.app_config import AppConfig
        from infrastructure.qdrant.qdrant_vector_repository import QdrantVectorRepository

        app_config = AppConfig.get_instance()
        storage_type = config.get("type", "qdrant")
        
        if storage_type == "qdrant":
            return QdrantVectorRepository(
                collection_name=config.get("collection_name", "default_collection"),
                embedding_dim=config.get("embedding_dim", 384),
                url=app_config.qdrant_ip or config.get("url"),
                port=int(app_config.qdrant_port) or config.get("port"),
                grpc_port=config.get("grpc_port"),
                api_key=config.get("api_key"),
                on_disk=config.get("on_disk", True),
                replication_factor=config.get("replication_factor", 1),
                write_consistency_factor=config.get("write_consistency_factor", 1),
                hybrid=config.get("hybrid", app_config.qdrant_hybrid_enabled),
            )
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")
