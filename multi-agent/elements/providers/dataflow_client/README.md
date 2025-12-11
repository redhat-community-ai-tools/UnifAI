# Dataflow Provider

Client for communicating with the Dataflow service (vector database) for document queries and metadata retrieval.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATAFLOW ECOSYSTEM                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

                         ┌──────────────────────────┐
                         │   Dataflow Service       │
                         │ (unifai-dataflow-server) │
                         │       :13456             │
                         └───────────┬──────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │  GET /api/   │  │  GET /api/   │  │  GET /api/   │
         │  docs/avail  │  │  docs/avail  │  │  docs/query  │
         │  able.tags   │  │  able.docs   │  │  .match      │
         │  .get        │  │  .get        │  │              │
         └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
                │                 │                 │
                └─────────────────┼─────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DataflowClient (client.py)                           │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐     │
│  │ get_available_tags  │  │ get_available_docs  │  │    query_match      │     │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DataflowProvider (dataflow_provider.py)                  │
│                                                                                  │
│  High-level sync API wrapping DataflowClient                                    │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐     │
│  │ get_available_tags  │  │ get_available_docs  │  │       query         │     │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    DataflowProviderFactory + DataflowProviderConfig              │
│                                                                                  │
│  Config defaults:                                                                │
│    base_url: http://unifai-dataflow-server:13456                                │
│    top_k: 10                                                                     │
│    timeout: 30.0                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
                 ▼                                 ▼
┌────────────────────────────┐     ┌────────────────────────────────────────────┐
│   DocsDataflowRetriever    │     │              ACTIONS                        │
│                            │     │                                             │
│  - Uses factory internally │     │  ┌─────────────────────────────────────┐   │
│  - Filters by threshold    │     │  │ dataflow.validate_connection        │   │
│  - Gets scope/user from    │     │  │ (uses DataflowClient directly)      │   │
│    context                 │     │  └─────────────────────────────────────┘   │
│                            │     │  ┌─────────────────────────────────────┐   │
│  retrieve(query) → matches │     │  │ dataflow.get_available_tags         │   │
└────────────────────────────┘     │  │ (uses factory)                      │   │
                                   │  └─────────────────────────────────────┘   │
                                   │  ┌─────────────────────────────────────┐   │
                                   │  │ dataflow.get_available_docs         │   │
                                   │  │ (uses factory)                      │   │
                                   │  └─────────────────────────────────────┘   │
                                   └────────────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/docs/available.tags.get` | GET | Paginated list of available tags |
| `/api/docs/available.docs.get` | GET | Paginated list of available documents |
| `/api/docs/query.match` | GET | Query vector database for matching documents |

## Usage

### Using the Provider directly

```python
from elements.providers.dataflow_client import DataflowProvider

provider = DataflowProvider(
    base_url="http://unifai-dataflow-server:13456",
    top_k=10,
    timeout=30.0,
)

# Query vector database
response = provider.query(
    query="How do I reset my password?",
    scope="my_scope",
    logged_in_user="user@example.com",
)

# Get available tags
tags = provider.get_available_tags(limit=50, search_regex="^test")

# Get available docs
docs = provider.get_available_docs(limit=50)
```

### Using the Factory (recommended)

```python
from elements.providers.dataflow_client.config import DataflowProviderConfig
from elements.providers.dataflow_client.dataflow_provider_factory import DataflowProviderFactory

config = DataflowProviderConfig(top_k=5)
factory = DataflowProviderFactory()
provider = factory.create(config)

response = provider.query(query="my search query")
```

## Files

| File | Purpose |
|------|---------|
| `identifiers.py` | Provider type key and metadata |
| `models.py` | Pydantic response models |
| `config.py` | `DataflowProviderConfig` with defaults |
| `client.py` | `DataflowClient` - sync HTTP client |
| `dataflow_provider.py` | `DataflowProvider` - high-level API |
| `dataflow_provider_factory.py` | Factory for creating provider from config |
| `spec/spec.py` | Element spec for auto-discovery |

