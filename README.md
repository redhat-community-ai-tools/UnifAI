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

### 1. 🔧 RAG Backend

This service is responsible for:

- Ingesting and chunking data from various sources like Slack, Docs, Jira, etc.
- Embedding and storing the data into a Vector Database (e.g., Qdrant, Milvus, or PostgreSQL with pgvector).
- Tracking metadata like:
  - Number of documents ingested per data source
  - Last time each data source was processed
  - Chunking and embedding status

📘 Reference Documentation:  
👉 [`RAG README`](backend/README.md)

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

#### a. RAG View
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

## 🧭 Getting Started – What to Explore First

To make your onboarding smooth, we recommend the following steps:

### ✅ 1. Read the Key READMEs

Start with the following:

- [`RAG README`](backend/README.md): Understand how we ingest and embed data.  
- [`Agentic AI README`](LINK 2): Learn about how our agentic system works and how execution plans are structured.

### ✅ 2. Explore the Code Repos

- Identify key modules: retrievers, vector DB interfaces, plan execution engine, etc.
- For GUI developers: explore components tied to Data Overview and Agentic Plan Builder UIs.

### ✅ 3. Understand Plan Structure

- Review some sample `.yaml` plans.
- Check how each node (retriever, summarizer, etc.) contributes to the overall response pipeline.

### ✅ 4. Run Locally (Optional but Helpful)

- Set up your environment to run the data pipeline and agentic backends independently.
- Launch the GUI and experiment with different plans and data sources.

💡 **Development Notes**  
The system is designed to be modular. New retrievers or plan nodes can be added without impacting the core execution engine.  
We aim to scale this to support more data sources in the near future.

---

## 📣 Final Words

This system is at the heart of building context-aware AI agents that help users get accurate, multi-source answers without manual data digging.  
Your contributions will directly enhance how users interact with internal knowledge in a smart, explainable, and visual way.

Feel free to reach out to the current maintainers for walkthroughs, design overviews, or setup help.

**Happy coding! 🚀**
