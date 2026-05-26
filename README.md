# UnifAI

**A platform for building and running multi-agent AI workflows over your enterprise knowledge.**

UnifAI lets you connect internal data sources — Slack, Jira, documents — into a unified vector store, then query them through composable, visual multi-agent pipelines. Define agent graphs as YAML blueprints or build them with a drag-and-drop UI, execute locally or at scale, and stream results in real time.

---

## What It Does

Most teams have knowledge scattered across Slack threads, Jira tickets, PDFs, and internal wikis. Finding answers means manually digging through multiple systems. UnifAI fixes this:

1. **Compose** — Build multi-agent workflows that reason across sources, route conditionally, and combine results
2. **Execute** — Run workflows locally or distributed, with real-time streaming
3. **Interact** — Use the web UI to build blueprints visually, trigger executions, and inspect every node's input/output
4. **Ingest** — Pull content from Slack, documents (PDF, Markdown), and more into a vector database for agents to search

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                     React / Vite / Tailwind UI                │
│                                                               │
│   ┌─────────────────────┐    ┌──────────────────────────┐     │
│   │   RAG Dashboard     │    │   Blueprint Builder &    │     │
│   │   Data source stats │    │   Agent Chat Interface   │     │
│   └─────────────────────┘    └──────────────────────────┘     │
└──────────┬───────────────────────────────┬────────────────────┘
           │ /api1                         │ /api2
           ▼                               ▼
  ┌─────────────────┐          ┌──────────────────────────┐
  │   RAG Backend   │◄────────►│  Multi-Agent Backend     │
  │                 │  search  │                          │
  │ • Ingestion     │          │ • Blueprint engine       │
  │ • Chunking      │          │ • Agent orchestration    │
  │ • Embedding     │          │ • LangGraph / Temporal   │
  │ • Vector search │          │ • Real-time streaming    │
  │ • Celery workers│          │ • A2A & MCP protocols    │
  └────────┬────────┘          └─────────────┬────────────┘
           │                                 │
           ▼                                 ▼
┌───────────────────────────────────────────────────────────────┐
│                    Shared Infrastructure                       │
│     MongoDB · Qdrant · RabbitMQ · Redis (opt) · Temporal      │
└───────────────────────────────────────────────────────────────┘
```

---

## Multi-Agent System — The Core

The heart of UnifAI is its **Multi-Agent System (MAS)**: a production-grade orchestration engine for defining, executing, and streaming multi-agent workflows.

### Blueprint-Driven Workflows

Agents are composed into directed graphs called **blueprints**. Each blueprint declares nodes, edges, conditions, and the tools/LLMs each agent can use — all in a single YAML file:

```yaml
name: "Multi-Source Knowledge Search"

llms:
  - rid: llm_rid
    type: openai
    config:
      model_name: gpt-4o
      base_url: https://api.openai.com/v1

retrievers:
  - rid: docs_retriever_rid
    type: docs_rag
    config: { top_k_results: 5 }
  - rid: slack_retriever_rid
    type: slack
    config: { top_k_results: 5 }

nodes:
  - rid: input_rid
    type: user_question_node
  - rid: docs_agent_rid
    type: custom_agent_node
    config:
      llm: llm_rid
      retriever: docs_retriever_rid
      system_message: "Search internal documentation..."
  - rid: slack_agent_rid
    type: custom_agent_node
    config:
      llm: llm_rid
      retriever: slack_retriever_rid
      system_message: "Search Slack messages..."
  - rid: merger_rid
    type: merger_node
  - rid: answer_rid
    type: final_answer_node

plan:
  - uid: input
    node: input_rid
  - uid: docs
    after: input
    node: docs_agent_rid
  - uid: slack
    after: input
    node: slack_agent_rid
  - uid: merge
    after: [docs, slack]
    node: merger_rid
  - uid: answer
    after: merge
    node: answer_rid
```

Blueprints can be pre-defined in YAML or built visually through the UI's drag-and-drop editor.

### Element Catalog

Blueprints are composed from a rich catalog of pluggable elements:

| Category | Available Types | Description |
|----------|----------------|-------------|
| **Nodes** | `custom_agent_node`, `orchestrator_node`, `merger_node`, `a2a_agent_node`, `branch_chooser_node`, `user_question_node`, `final_answer_node` | The building blocks of agent graphs |
| **LLMs** | `openai`, `google_genai` | LLM providers (any OpenAI-compatible API) |
| **Tools** | `ssh_exec`, `web_fetch`, `oc_exec`, `mcp_proxy` | Actions agents can perform |
| **Providers** | `mcp_server`, `a2a_agent`, `rag_client` | External service integrations |
| **Retrievers** | `docs_rag`, `slack` | RAG-powered context retrieval |
| **Conditions** | `router_direct`, `router_boolean`, `threshold` | Conditional edge routing |

The catalog is extensible — new elements are auto-discovered at startup.

### Execution Modes

| Mode | Engine | Best For |
|------|--------|----------|
| **Local** | LangGraph | Development, single-process execution |
| **Distributed** | Temporal | Production, horizontal scaling across workers |

Both modes use the same blueprint format. Switch between them with a single environment variable.

### Real-Time Streaming

Executions stream node-by-node output as **NDJSON over HTTP**, so clients can render progress as it happens. Two patterns are supported:

- **Synchronous streaming** — execute and stream results in a single request
- **Fire-and-forget** — submit a workflow, then subscribe to its event stream from any client

### Protocol Support

- **A2A (Agent-to-Agent)** — Delegate tasks to remote agents over the A2A protocol. Any A2A-compatible agent can be added as a node in a blueprint.
- **MCP (Model Context Protocol)** — Connect to MCP servers to give agents access to external tools (Jira, GitHub, databases, etc.). Configure once as a provider, then attach to any agent node.

### Templates

Pre-built workflow templates with **placeholders** let users instantiate complex blueprints without writing YAML — browse templates in the UI, fill in the blanks, and start executing.

---

## Web UI

A React-based interface with two primary views:

**Blueprint Builder** — Visual drag-and-drop editor for composing agent graphs. Select nodes from the element catalog, wire them together, configure LLMs and tools, then execute — all without writing YAML. During execution, inspect each node's input/output in real time.

**RAG Dashboard** — Monitor data source health: document counts, chunking/embedding status, last ingestion timestamps. Upload documents and register Slack channels.

---

## RAG Pipeline

The RAG module feeds the multi-agent system with indexed enterprise knowledge:

- **Sources** — PDF, Markdown documents, Slack channels and threads
- **Processing** — Intelligent chunking, metadata extraction, async background workers
- **Storage** — Vector embeddings in Qdrant, metadata in MongoDB
- **Search** — Semantic similarity search exposed to agents via retriever elements
- **Flexibility** — Document conversion and embedding services can run locally or as remote microservices, toggled via feature flags

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Multi-Agent Backend | Python 3.11+, Flask, LangGraph, Temporal, Redis |
| RAG Backend | Python 3.11+, Flask, Celery, Qdrant, RabbitMQ |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Radix UI |
| Auth | Keycloak (OAuth 2.0 / OIDC) |
| Storage | MongoDB, Qdrant (vectors), Redis (streams) |
| Deployment | Helm, Helmfile, OpenShift / Kubernetes, Docker |

---

## Quick Start

For a complete walkthrough — setting up virtual environments, installing dependencies, and running all services locally — see the **[Local Development Guide](local-development/LOCAL_DEV_GUIDE.md)**.

### Deployment

For Kubernetes/OpenShift deployment, see the [Helm Deployment Guide](helm/README.md).

---

## Project Structure

```
unifai/
├── multi-agent/          # Multi-Agent System — orchestration engine
│   └── lib/mas/
│       ├── elements/     # Nodes, tools, LLMs, providers, conditions
│       ├── engine/       # LangGraph & Temporal execution engines
│       ├── blueprints/   # Blueprint resolution & validation
│       ├── sessions/     # Session lifecycle & streaming
│       ├── templates/    # Template instantiation
│       └── catalog/      # Element auto-discovery
├── rag/                  # RAG pipeline — ingestion, chunking, search
│   ├── core/             # Business logic & domain services
│   ├── infrastructure/   # Adapters (MongoDB, Qdrant, Celery)
│   └── bootstrap/        # Dependency injection & app setup
├── ui/                   # React frontend
├── shared-resources/     # Identity service (Keycloak integration)
├── global_utils/         # Shared Python utilities
├── helm/                 # Helm charts & Helmfile for deployment
├── ci/                   # Jenkins CI/CD pipelines
└── tests/                # Test infrastructure
```

---

## Documentation

| Module | README |
|--------|--------|
| Multi-Agent System | [multi-agent/README.md](multi-agent/README.md) |
| RAG Pipeline | [rag/README.md](rag/README.md) |
| Web UI | [ui/README.md](ui/README.md) |
| Helm Deployment | [helm/README.md](helm/README.md) |
| Identity / Auth | [shared-resources/identity/README.md](shared-resources/identity/README.md) |
| CI/CD | [ci/README.md](ci/README.md) |

---

## Contributing

Contributions are welcome! The system is designed to be modular — new agent nodes, tools, LLM providers, retrievers, and data source adapters can be added without modifying the core engine.
