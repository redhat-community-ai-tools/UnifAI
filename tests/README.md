# UnifAI Test Runner

A containerised test runner for both **RAG** and **Multi-Agent** test suites.  
The image bundles Python 3.11, all application dependencies, and the pytest
framework so tests can be executed anywhere without local setup.

## What the Image Contains

```
UBI9 / Python 3.11
 |
 +-- venv/                    Python virtual environment
 |     +-- global_utils       Shared utilities (installed editable)
 |     +-- rag                RAG application + dependencies
 |     +-- multi-agent        Multi-Agent application + dependencies
 |     +-- pytest, aiohttp, reportlab, pymongo, ...
 |
 +-- rag/
 |     +-- tests/             RAG test suite (e2e, fixtures, factories)
 |     +-- pytest.ini         RAG pytest configuration
 |
 +-- multi-agent/
 |     +-- tests/             Multi-Agent test suite (unit, integration, e2e)
 |     +-- pytest.ini         Multi-Agent pytest configuration
 |
 +-- run_tests.sh             Entrypoint script (routes to test suites)
```

## Prerequisites

- **Podman** (or Docker)
- On Apple Silicon (M1/M2/M3), the image runs under `linux/amd64` emulation

## Build

Run from the **repository root** (`UnifAI/`), not from inside the `pytest/` folder.
The build context must be the repo root so that `rag/`, `multi-agent/`, and
`global_utils/` are accessible.

```bash
cd /path/to/UnifAI

podman build --platform linux/amd64 -f pytest/Dockerfile.pytest -t unifai-tests .
```

## Run Tests

The container entrypoint accepts a **suite name** as the first argument,
followed by optional pytest arguments.

### Available Suites

| Suite                    | Description                          |
|--------------------------|--------------------------------------|
| `all`                    | Run everything (RAG + Multi-Agent)   |
| `rag`                    | All RAG tests                        |
| `rag-e2e`                | RAG e2e / stress tests only          |
| `multi-agent`            | All Multi-Agent tests                |
| `multi-agent-e2e`        | Multi-Agent e2e tests only           |
| `multi-agent-unit`       | Multi-Agent unit tests only          |
| `multi-agent-integration`| Multi-Agent integration tests only   |
| `identity`               | All Identity tests                   |
| `identity-unit`          | Identity unit tests only             |
| `identity-smoke`         | Identity snmoke tests only           |

### Examples

**Run all tests:**

```bash
podman run --rm --platform linux/amd64 unifai-tests all
```

**Run RAG e2e stress tests against a live API:**

```bash
podman run --rm --platform linux/amd64 \
  -e API_BASE_URL=http://your-rag-server/api \
  -e MONGODB_HOST=your-mongo-host \
  unifai-tests rag-e2e --num-docs 10 --concurrent-uploads 5
```

**Run Multi-Agent unit tests only:**

```bash
podman run --rm --platform linux/amd64 unifai-tests multi-agent-unit
```

**Run with JUnit XML output (for CI):**

```bash
podman run --rm --platform linux/amd64 \
  -v $(pwd)/results:/tmp/results \
  unifai-tests all --junitxml=/tmp/results/report.xml
```

**Filter by pytest marker:**

```bash
podman run --rm --platform linux/amd64 unifai-tests rag -m stress
```

**Filter by test name pattern:**

```bash
podman run --rm --platform linux/amd64 \
  unifai-tests rag-e2e -k test_concurrent_document_upload
```

## Environment Variables

These can be passed via `-e` to configure RAG e2e tests without modifying code.

| Variable             | Default                      | Description                        |
|----------------------|------------------------------|------------------------------------|
| `API_BASE_URL`       | `http://localhost:13457/api`  | RAG API base URL                   |
| `MONGODB_HOST`       | `0.0.0.0`                    | MongoDB host for Celery monitoring |
| `MONGODB_PORT`       | `27017`                      | MongoDB port                       |
| `MONGODB_DB`         | `celery`                     | MongoDB database name              |
| `NUM_DOCUMENTS`      | `100`                        | Number of documents to upload      |
| `CONCURRENT_UPLOADS` | `10`                         | Parallel uploads per batch         |
| `UPLOAD_TIMEOUT`     | `300`                        | Per-upload timeout (seconds)       |
| `TEST_USER`          | `stress_test_user`           | User sent in pipeline requests     |

Alternatively, the same values can be passed as **pytest CLI flags**
(append after the suite name):

```
--api-base-url, --mongodb-host, --mongodb-port, --mongodb-db,
--num-docs, --concurrent-uploads, --upload-timeout, --celery-timeout, --test-user
```

## How It Works

```
podman run unifai-tests <suite> [pytest-args]
          |
          v
      run_tests.sh
          |
          +-- selects suite (rag, multi-agent, etc.)
          +-- cd into the correct project folder
          +-- exec pytest with the right test path
          |
          v
      pytest discovers tests via pytest.ini
          |
          +-- conftest.py loads fixtures, registers markers
          +-- fixtures provide config, PDF documents, DB connections
          +-- test classes inherit from base classes (BaseE2ETest, etc.)
          +-- assertions produce PASSED / FAILED per test
          |
          v
      exit code 0 (all passed) or 1 (any failed)
```

## Files in This Folder

| File               | Purpose                                              |
|--------------------|------------------------------------------------------|
| `Dockerfile.pytest` | Builds the test image with all deps and source code  |
| `run_tests.sh`     | Entrypoint script that routes to the correct suite    |
| `README.md`        | This file                                            |
