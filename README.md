# 🧭 Start With Guide: UnifAI – Project Overview

Welcome aboard!

You're about to join the development of a sophisticated Agentic AI platform designed to power knowledge retrieval across multiple internal data sources using Retrieval-Augmented Generation (RAG) techniques and dynamic agentic workflows.

This guide outlines the system architecture at a high level and provides you with direct entry points (READMEs and relevant documentation) to help you understand the existing components and begin contributing effectively.

---

## 🧠 Project Goals

UnifAI is engineered to:

- Aggregate and process data from various enterprise sources (Slack, Jira, Docs, etc.).
- Store and index relevant data in a Vector Database.
- Enable users to interactively retrieve answers using AI agents structured as dynamic, plannable workflows.
- Provide clear, visual representations in a GUI interface of data readiness, plan execution, and retrieval results.

---

## 🧩 System Architecture Overview

The application is divided into three main components:

### 1. 🔧 Data Preparation Backend

This service is responsible for:

- Ingesting and chunking data from various sources like Slack, Docs, Jira, etc.
- Embedding and storing the data into a Vector Database (e.g., Qdrant, Milvus, or PostgreSQL with pgvector).
- Tracking metadata like:
  - Number of documents ingested per data source
  - Last time each data source was processed
  - Chunking and embedding status

📘 Reference Documentation:  
👉 [`Data Preparation README`](DataPipelineHub/backend/README.md)

---

### 2. 🤖 Agentic AI Backend

This is the "AI" layer representation of the system responsible for:

- Defining and executing Agentic Plans via `.yaml` files.
- Each plan is composed of nodes (like Slack Retriever, Doc Retriever, etc.), which can be reused and combined in new workflows.
- Plans can be pre-defined or built by users via GUI using drag-and-drop functionality.
- Once executed, the plan retrieves data across multiple sources and composes a detailed answer.

📘 Reference Documentation:  
👉 [`Agentic AI README`](LINK 2)

---

### 3. 🖥️ Graphical User Interface (GUI)

The GUI is a React-based frontend that serves two main functions:

#### a. Data Preparation View
- Shows statistics and metadata per data source:
  - Number of documents available
  - Chunking/embedding status
  - Last processed time
- Helps users understand current data availability in the system.

#### b. Agentic AI View
- Allows users to:
  - Visualize and build executable plans using predefined building blocks.
  - Trigger executions and observe each node's input/output.
  - Receive final AI-generated answers based on plan execution across the available data.

---

## 🚀 **Deployment & Configuration**

UnifAI uses a **multi-source GitOps** approach with **centralized private configuration** for secure, scalable deployments across environments.

### **📁 Repository Structure**

| Repository | Purpose | Content |
|------------|---------|---------|
| **Main Repo** (`unifai.git`) | Application code & Helm charts | Source code, Docker images, Helm templates |
| **Private Config Repo** (`unifai-gitops-priv.git`) | Environment configuration | Secrets, environment-specific settings, service configurations |

### **🌍 Multi-Environment Support**

| Environment | Namespace | Git Branch | Configuration |
|-------------|-----------|------------|---------------|
| **Development** | `tag-ai--runtime-int` | `GENIE-727/story/gitops-unifai` | `environments/dev/` |
| **Production** | `unifai-prod` | `main` | `environments/prod/` |

### **⚙️ Service Architecture**

Deployed in **4 waves** for proper dependency management:

1. **Wave 1**: Shared Storage (EFS)
2. **Wave 2**: Core Services (MongoDB, Qdrant, RabbitMQ, Docling)
3. **Wave 3**: Configuration & Service Discovery
4. **Wave 4**: Application Layer (Dataflow, Celery, SSO)

### **🔧 Configuration Management**

**Centralized Configuration** - All environment-specific settings in private repo:
```
unifai-gitops-priv/environments/
├── dev/
│   ├── sensitive-values.yaml      # Secrets, API keys
│   ├── site-config.yaml           # Infrastructure settings
│   └── values/                    # Service configurations
│       ├── mongodb.values.yaml
│       ├── qdrant.values.yaml
│       ├── dataflow.values.yaml
│       └── ... (9 service files)
└── prod/
    └── (same structure)
```

### **📋 Quick Deployment**

**Development:**
```bash
kubectl apply -f gitops-updated/unifai-multisource-dev.yaml
```

**Production:**
```bash
kubectl create namespace unifai-prod
kubectl apply -f gitops-updated/unifai-multisource-prod.yaml
```

**📖 Detailed Documentation:**
- [`Private Repo Configuration Guide`](unifai-gitops-priv.ericz/README.md)
- [`Parameterized Setup Guide`](gitops-updated/PARAMETERIZED-SETUP-GUIDE.md)
- [`Environment Topology Comparison`](gitops-updated/ENVIRONMENT-TOPOLOGY-COMPARISON.md)

---

## 🧭 Getting Started – What to Explore First

To make your onboarding smooth, we recommend the following steps:

### ✅ 1. Read the Key READMEs

Start with the following:

- [`Data Preparation README`](DataPipelineHub/backend/README.md): Understand how we ingest and embed data.  
- [`Agentic AI README`](LINK 2): Learn about how our agentic system works and how execution plans are structured.
- [`Private Repo Configuration Guide`](unifai-gitops-priv.ericz/README.md): Learn about the GitOps deployment and configuration management.
- [`Deployment Documentation`](gitops-updated/): Explore environment setup and ArgoCD applications.

### ✅ 2. Explore the Code Repos

- Identify key modules: retrievers, vector DB interfaces, plan execution engine, etc.
- For GUI developers: explore components tied to Data Overview and Agentic Plan Builder UIs.

### ✅ 3. Understand Plan Structure

- Review some sample `.yaml` plans.
- Check how each node (retriever, summarizer, etc.) contributes to the overall response pipeline.

### ✅ 4. Deploy to Kubernetes (Recommended)

- **Development**: Deploy to your dev environment using `kubectl apply -f gitops-updated/unifai-multisource-dev.yaml`
- **Local Testing**: Set up your environment to run components independently
- **Production**: Follow production deployment guide for full-scale deployment

### ✅ 5. Run Locally (Optional)

- Set up your environment to run the data pipeline and agentic backends independently.
- Launch the GUI and experiment with different plans and data sources.

💡 **Development Notes**  
- **Modular Architecture**: New retrievers or plan nodes can be added without impacting the core execution engine.  
- **GitOps Workflow**: All configuration changes go through the private repository for proper security and audit trails.
- **Multi-Environment**: Identical topology across dev/prod environments with environment-specific configuration.
- **Scalability**: Designed to support more data sources and environments in the future.

🔧 **Recent Improvements**
- ✅ **Centralized Configuration**: All config files moved to private repository for better security
- ✅ **Clean File Naming**: Standardized `service.values.yaml` naming convention  
- ✅ **Multi-Environment**: Production topology created with identical structure to development
- ✅ **GitOps Integration**: Full ArgoCD multi-source deployment with automated sync

---

## 📣 Final Words

This system is at the heart of building context-aware AI agents that help users get accurate, multi-source answers without manual data digging.  

With our **GitOps-powered deployment infrastructure**, you can:
- 🔒 **Deploy Securely** - All sensitive config in private repositories
- 🌍 **Scale Across Environments** - Identical dev/prod topologies  
- ⚙️ **Configure Centrally** - Single source of truth for all environments
- 🚀 **Deploy Confidently** - Automated, reproducible deployments

Your contributions will directly enhance how users interact with internal knowledge in a smart, explainable, and visual way, while benefiting from enterprise-grade deployment practices.

Feel free to reach out to the current maintainers for walkthroughs, design overviews, or GitOps setup help.

**Happy coding! 🚀**
