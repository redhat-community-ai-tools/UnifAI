# 🧭 UnifAI – Project Overview

Welcome aboard!

You're about to join the development of an Agentic AI platform designed to power knowledge retrieval across multiple internal data sources using Retrieval-Augmented Generation (RAG) techniques and dynamic agentic workflows.

This guide outlines the system architecture, provides setup instructions, and gives you direct entry points to help you understand the existing components and begin contributing effectively.

---

## 🧠 Project Goals

UnifAI is engineered to:

- Aggregate and process data from various enterprise sources (Slack, Jira, Docs, etc.).
- Store and index relevant data in a Vector Database.
- Enable users to interactively retrieve answers using AI agents structured as dynamic, plannable workflows.
- Provide clear, visual representations in a GUI interface of data readiness, plan execution, and retrieval results.

---

## 🧩 Architecture

The platform consists of three main components:

```
                    ┌──────────────────────────────────┐
                    │           UI (React)             │
                    │   Dashboard / Plan Builder /     │
                    │        Chat Interface            │
                    └──────┬───────────────┬───────────┘
                           │               │
              ┌────────────▼──┐      ┌─────▼──────────────┐
              │   Dataflow    │      │   Multi-Agent      │
              │   Backend     │      │   Backend           │
              │  (Flask/RAG)  │      │  (Flask/LangGraph) │
              └───┬───┬───┬───┘      └─────┬──────────────┘
                  │   │   │                │
           ┌──────┘   │   └──────┐         │
           ▼          ▼          ▼         ▼
       ┌────────┐ ┌────────┐ ┌────────┐
       │MongoDB │ │Qdrant  │ │RabbitMQ│
       └────────┘ └────────┘ └────────┘
```

### 1. 🔧 Dataflow Backend (`rag/`)

Handles data ingestion, processing, and vector storage. Built with a feature-sliced architecture and hexagonal design principles for document processing, embedding, and semantic search.

Supports Slack channels, PDF/Markdown documents, and Jira as data sources. Uses Celery with RabbitMQ for asynchronous pipeline execution and Qdrant for vector storage with 384-dimensional sentence transformer embeddings.

[RAG README](rag/README.md) | [RAG Diagrams](rag/DIAGRAMS.md)

### 2. 🤖 Multi-Agent Backend

Defines and executes agentic AI workflows using LangGraph. Agents are composed from reusable nodes (retrievers, summarizers, tools) defined in YAML blueprint files. Supports multi-step reasoning, tool execution, and session management.

Integrates with LangChain, OpenAI-compatible LLM providers, MCP servers, and the A2A SDK.

[Multi-Agent directory](multi-agent/)

### 3. 🖥️ Graphical User Interface (GUI)

React frontend built with Vite, TypeScript, and Tailwind CSS. Provides three main views:

- **Data Overview** -- Statistics per data source: document counts, embedding status, processing history.
- **Plan Builder** -- Visual drag-and-drop editor for constructing agent execution plans using ReactFlow.
- **Chat Interface** -- Interactive retrieval with real-time node execution monitoring.

Uses Shadcn/ui components, Zustand for state management, and TanStack Query for data fetching.

[UI README](ui/README.md)

---

## 🛠️ Prerequisites

- Python 3.11+
- Node.js 22+ with PNPM
- Docker or Podman (for infrastructure services)

### Infrastructure Services

Start MongoDB, RabbitMQ, and Qdrant:

```bash
# MongoDB
docker run -d --name mongo -p 27017:27017 -v mongo_data:/data/db mongo:5.0

# RabbitMQ
docker run -d --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=guest \
  -e RABBITMQ_DEFAULT_PASS=guest \
  rabbitmq:3-management

# Qdrant
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v ~/qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest
```

Management interfaces:
- RabbitMQ: http://localhost:15672 (guest/guest)
- Qdrant: http://localhost:6333/dashboard

---

## 🚀 Getting Started

### Dataflow Backend (RAG)

```bash
cd rag
python -m venv venv
source venv/bin/activate
pip install -e .

# Start Flask server
python -m bootstrap.flask_app

# Start Celery workers:
celery -A infrastructure.celery.app worker -Q document_queue,slack_queue -l info
```

### Multi-Agent Backend

```bash
cd multi-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e ../global_utils/

python app.py
```

### UI

```bash
cd ui/client
npm install -g corepack
corepack prepare pnpm@latest --activate
pnpm install --frozen-lockfile

# Development server (http://localhost:5173)
pnpm run start

# Production build
pnpm build
```

Configure backend proxies in `vite.config.ts` to route `/api1` to the dataflow backend and `/api2` to the multi-agent backend. See the [UI README](ui/README.md) for proxy configuration details.

---

## ⚙️ Configuration

Each component reads configuration from its `config/app_config.py`, with environment variable overrides:

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_IP` | `0.0.0.0` | MongoDB host |
| `MONGODB_PORT` | `27017` | MongoDB port |
| `QDRANT_IP` | `0.0.0.0` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `RABBITMQ_IP` | `0.0.0.0` | RabbitMQ host |
| `RABBITMQ_PORT` | `5672` | RabbitMQ port |
| `FRONTEND_URL` | `http://localhost:5000` | Frontend URL for CORS |
| `DEFAULT_SLACK_BOT_TOKEN` | -- | Slack bot OAuth token |
| `DEFAULT_SLACK_USER_TOKEN` | -- | Slack user OAuth token |

---

## 🐳 Deployment

UnifAI deploys to Kubernetes/OpenShift using Helm and Helmfile. Container images are built on Red Hat UBI9 base images.

```bash
cd helm

# Deploy infrastructure (MongoDB, RabbitMQ, Qdrant)
helmfile -f helmfile1.yaml.gotmpl apply

# Deploy application components
helmfile -f dataflow.yaml.gotmpl apply
helmfile -f multiagent.yaml.gotmpl apply
helmfile -f ui.yaml.gotmpl apply
```

CI/CD is handled through Jenkins pipelines for image building and application deployment.

[Helm Deployment Guide](helm/README.md) | [Helm Architecture](helm/ARCHITECTURE.md) | [CI/CD Guide](ci/README.md)

---

## 🧪 Testing

The multi-agent module includes a comprehensive test suite:

```bash
cd multi-agent
pytest tests/                # All tests
pytest -m unit               # Unit tests only
pytest -m integration        # Integration tests
pytest --cov=.               # With coverage
```

Test categories include unit, integration, end-to-end, chaos, and edge case tests. See `multi-agent/pytest.ini` for available markers.

---

## 📁 Project Structure

```
UnifAI/
├── backend/              # Data Pipeline Hub (Flask, Celery)
├── rag/                  # RAG Module (feature-sliced architecture)
├── multi-agent/          # Agentic AI Backend (LangGraph)
├── ui/
│   ├── client/           # React frontend (Vite, TypeScript)
│   └── deployment/       # Nginx container build
├── global_utils/         # Shared Python utilities
├── helm/                 # Kubernetes/OpenShift Helm charts
├── ci/                   # Jenkins CI/CD pipelines
├── shared-resources/     # SSO backend service
├── mcp_servers/          # MCP server implementations
└── scripts/              # Utility scripts
```

---

## 🤝 Contributing

1. Create a feature branch from `main`.
2. Follow code conventions documented in each component's `ARCHITECTURE.md`.
3. Add tests for new functionality.
4. Update relevant documentation.
5. Test locally with all services running.
6. Submit a pull request with a clear description.

---

## 📣 Final Words

This system is at the heart of building context-aware AI agents that help users get accurate, multi-source answers without manual data digging. The system is designed to be modular — new retrievers or plan nodes can be added without impacting the core execution engine.

Your contributions will directly enhance how users interact with internal knowledge in a smart, explainable, and visual way.

Feel free to reach out to the current maintainers for walkthroughs, design overviews, or setup help.

**Happy coding! 🚀**

---

## 📄 License

[Apache License 2.0](LICENSE)
