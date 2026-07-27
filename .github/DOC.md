# GitHub Actions & CI/CD

This folder contains all CI/automation workflows and supporting scripts for GitHub Actions.

## Overview

Workflows are configured to run automated tasks using GitHub Actions. For complex operations, we use dedicated scripts (in `.github/scripts/`) that are invoked from the workflow files. The workflows are organized into four categories: **Backup**, **Security**, **Code Review**, and **Branch Governance**.

For Jenkins-based build and deployment pipelines, see [ci/README.md](../ci/README.md).

### Shared Patterns

- **Failure Analysis** — Three workflows (`backup-dbs.yaml`, `security-container-vulnerability-scanning.yaml`, `security-pip-auditing.yaml`) include an `analyze` job that triggers on any job failure. It uses [gha-failure-analysis](https://github.com/calebevans/gha-failure-analysis) with a Gemini LLM to automatically analyze the failure logs and produce a human-readable summary.
- **Self-hosted runners** — Some workflows run on self-hosted `linux` runners (labeled `linux`) that have access to both GitHub and the internal company network. See [UnifAI team infrastructure](#unifai-team-infrastructure) for details.

#### Failure Analysis Setup

The failure analysis step requires three repository-level secrets:

| Secret | Purpose |
|--------|---------|
| `LOG_ANALYZER_APP_ID` | GitHub App ID used to generate a scoped token for reading workflow logs |
| `LOG_ANALYZER_PRIVATE_KEY` | Private key for the GitHub App above |
| `GEMINI_API_KEY` | API key for Google Gemini (used by `gha-failure-analysis` to analyze logs) |

To configure:
1. Create a [GitHub App](https://docs.github.com/en/apps/creating-github-apps) with `actions: read` and `contents: read` permissions
2. Install it on the repository
3. Add `LOG_ANALYZER_APP_ID` and `LOG_ANALYZER_PRIVATE_KEY` as repository secrets under **Settings → Secrets and variables → Actions**
4. Add `GEMINI_API_KEY` as a repository secret (obtain from [Google AI Studio](https://aistudio.google.com/apikey))

> **Data-sharing notice:** When failure analysis runs, the workflow's job logs are sent to Google's Gemini API for LLM-based analysis. This may include environment names, error messages, stack traces, and other runtime output. Ensure this is acceptable under your organization's data handling policies before enabling these workflows. Do not log sensitive values (credentials, tokens, PII) in workflow steps — they will be included in the analysis payload.

---

## Available Workflows

### Backup

#### `backup-dbs.yaml` — Automated Database Backups

Backs up MongoDB and Qdrant databases, then uploads the backups to an internal GitLab repository.

| Property | Value |
|----------|-------|
| **Triggers** | Scheduled daily at 00:05 UTC (`cron: '5 0 * * *'`), manual dispatch |
| **Runs on** | Self-hosted `linux` runner (backup jobs), `ubuntu-latest` (setup & analyze) |
| **Environment** | Uses GitHub Environments (`PRE-PRODUCTION`, `PRODUCTION`) |

**Inputs (manual dispatch):**
- `target_branch` — Branch to checkout for the workflow (default: `main`)
- `target_cluster` — Choice of `PRE-PRODUCTION` or `PRODUCTION` (default: `PRODUCTION`)

**Jobs:**
1. `verify_agent_deps` — Calls the reusable `verify-agent-deps.yaml` workflow to check runner prerequisites
2. `setup_environment` — Resolves branch and cluster from inputs
3. `backup_mongo` — Runs `backup_mongo.py` to dump MongoDB via K8s pod exec
4. `backup_qdrant` — Runs `backup_qdrant.py` to snapshot all Qdrant collections
5. `upload_to_gitlab` — Runs `upload_to_gitlab.py` to push backups to the GitLab backup repository
6. `analyze` — (on failure) Gemini-based failure analysis

#### `verify-agent-deps.yaml` — Runner Dependency Verification

Verifies that the self-hosted runner has the required OS and Python dependencies installed. This is a **reusable workflow** (`workflow_call`) — it is called by `backup-dbs.yaml` before any backup job runs.

| Property | Value |
|----------|-------|
| **Triggers** | `workflow_dispatch`, `workflow_call`, push to its own file path |
| **Runs on** | Self-hosted `linux` runner |

**Checks:**
- OS: `kubectl` is available
- Python: `qdrant-client`, `requests`, `kubernetes`, and `GitPython` are installed

---

### Security

#### `security-container-vulerability-scanning.yaml` — Container Vulnerability Scanning

Builds container images for each component and scans them with [Trivy](https://github.com/aquasecurity/trivy) for CRITICAL and HIGH vulnerabilities. Results are uploaded to the GitHub Security tab as SARIF reports.

| Property | Value |
|----------|-------|
| **Triggers** | Manual dispatch (PR trigger is commented out) |
| **Runs on** | Self-hosted `linux` runner |
| **Permissions** | `security-events: write`, `contents: read` |

**Inputs:**
- `branch` — Branch to scan (default: `main`)

**Scanned components:**

| Component | Dockerfile | Context |
|-----------|------------|---------|
| `multiagentbackend` | `multi-agent/Dockerfile` | `.` |
| `identity` | `shared-resources/identity/Dockerfile` | `.` |
| `ui` | `ui/deployment/Dockerfile` | `.` |

The UI build requires certificates from the private `UnifAI-secrets` repository (accessed via `UNIFAI_SECRETS_TOKEN`).

#### `security-pip-auditing.yaml` — PIP Dependency Security Scanning

Runs [pip-audit](https://github.com/pypa/gh-action-pip-audit) against Python dependencies for each component to detect known vulnerabilities.

| Property | Value |
|----------|-------|
| **Triggers** | PRs to `main`, manual dispatch |
| **Runs on** | `ubuntu-latest` |

**Inputs (manual dispatch):**
- `branch` — Branch to scan (default: `main`)

**Scanned components:** `backend`, `rag`, `multi-agent`, `identity` — each in an isolated virtual environment with its own job.

#### `security-hashicorp-test.yaml` — HashiCorp Vault Integration Test *(experimental)*

Tests HashiCorp Vault secret retrieval using [vault-action](https://github.com/hashicorp/vault-action) with AppRole authentication. This is an experimental workflow for validating Vault integration.

| Property | Value |
|----------|-------|
| **Triggers** | Manual dispatch only |
| **Runs on** | Self-hosted `linux` runner |

**Inputs:**
- `target_branch` — Branch to use (default: `GENIE-948_hashicorp_integration`)

**Required secrets/variables:** `VAULT_URL`, `APPROLE_NAME`, `SECRET_ID`

---

### Code Review

#### `cr-assistant.yml` — AI Code Review Assistant

Runs two automated code reviewers on pull requests:
1. **CodeRabbit** — AI-powered reviewer via `coderabbitai/ai-pr-reviewer` (see [CODERABBIT.md](CODERABBIT.md) for details)
2. **Gemini CR Agent** — Custom Python-based reviewer (`scripts/review.py` at the repo root) that uses Google's Gemini API to analyze the diff and post a review comment

| Property | Value |
|----------|-------|
| **Triggers** | PR opened/reopened, manual dispatch, `/run-cr` comment on a PR |
| **Runs on** | `ubuntu-latest` |
| **Permissions** | `pull-requests: write`, `contents: read`, `issues: write` |

**Required secrets:** `GEMINI_API_KEY`, `GITHUB_TOKEN`

#### `cursor-pipeline.yml` — Cursor Pipeline Review

Multi-agent code review pipeline using the Cursor CLI. An orchestrator agent performs scout logic inline, then spawns two judge subagents in parallel: an Architecture Judge and a Code Judge. Results are evaluated by a gate script to produce a pass/fail commit status on the PR.

| Property | Value |
|----------|-------|
| **Triggers** | PRs to `main`, manual dispatch |
| **Runs on** | `ubuntu-latest` |
| **Timeout** | 45 minutes |
| **Concurrency** | Cancels in-progress runs for the same PR/branch |

**Models:**

| Role | Model | Purpose |
|------|-------|---------|
| Orchestrator | `composer-2.5-fast` | Scout logic, spawns judges |
| Architecture Judge | `claude-4.6-opus-high-thinking` | Architecture review |
| Code Judge | `claude-4.6-sonnet-medium-thinking` | Code quality review |

**Pipeline steps:**
1. Install Cursor CLI (pinned version with SHA256 verification)
2. Validate model availability
3. Run `/pipeline review` — produces `arch_review_output.txt` and `code_review_output.txt`
4. Publish review results to GitHub Actions Job Summary
5. Extract telemetry via `extract_pipeline_telemetry.py` (token usage, cost estimates)
6. Evaluate review gate via `evaluate_review_gate.py` (architecture verdict + code score)
7. Publish commit status — `Pipeline Review: Architecture: <verdict> | Code: <score>/10`

**Gate criteria:**
- Architecture review must return `APPROVE`
- Code review score must be ≥ 8/10 (configurable via `CODE_REVIEW_THRESHOLD`)

**Required secrets:** `CURSOR_API_KEY`

---

### Branch Governance

#### `enforce_staging_to_main_alignment.yaml` — Staging-to-Main Alignment Check *(experimental)*

Ensures that a PR branch has already been merged into `staging` before it can be merged into `main`. This enforces a staging-first workflow. Currently experimental — the `pull_request` trigger is commented out, only manual dispatch is active.

| Property | Value |
|----------|-------|
| **Triggers** | Manual dispatch only (PR trigger commented out) |
| **Runs on** | `ubuntu-latest` |

---

## Scripts (`.github/scripts/`)

All scripts are standalone Python modules invoked by the workflows. They are designed to be **reusable** — they read configuration entirely from environment variables, so they can be called from any workflow or run locally with the appropriate env vars set.

### Backup Scripts

#### `backup_mongo.py`

Performs a MongoDB backup by connecting to a Kubernetes cluster, running `mongodump` on the MongoDB pod, compressing the result, and copying the archive to the local filesystem.

| Used by | `backup-dbs.yaml` → `backup_mongo` job |
|---------|----------------------------------------|
| **Dependencies** | `kubernetes` Python package, `kubectl` CLI |

**Required environment variables:**
- `MONGO_POD` — Name of the MongoDB pod (e.g., `mongodb-0`)
- `NAMESPACE` — Kubernetes namespace
- `CLUSTER` — Cluster name (used for kubeconfig context)
- `API_URL` — Kubernetes API server URL
- `ACCESS_TOKEN` — Kubernetes bearer token
- `MONGO_URI` — MongoDB connection string

**Standalone usage:**
```bash
export MONGO_POD=mongodb-0 NAMESPACE=my-ns CLUSTER=my-cluster \
       API_URL=https://api.cluster:6443 ACCESS_TOKEN=<token> \
       MONGO_URI="mongodb://..." SKIP_VERIFY_TLS=true
python3 .github/scripts/backup_mongo.py
```

#### `backup_qdrant.py`

Creates snapshots for all collections in a Qdrant cluster, downloads them to a local directory, then deletes the remote snapshots to avoid storage buildup.

| Used by | `backup-dbs.yaml` → `backup_qdrant` job |
|---------|-----------------------------------------|
| **Dependencies** | `qdrant-client`, `requests` |

**Required environment variables:**
- `QDRANT_URL` — Qdrant cluster base URL
- `QDRANT_API_KEY` — (optional) API key for authenticated clusters
- `QDRANT_SNAPSHOTS_DIR` — Local directory to save snapshots (default: `/tmp/snapshots`)

**Standalone usage:**
```bash
export QDRANT_URL=http://qdrant:6333 QDRANT_SNAPSHOTS_DIR=/tmp/snapshots
python3 .github/scripts/backup_qdrant.py
```

#### `upload_to_gitlab.py`

Clones the GitLab backup repository, replaces old backups with fresh MongoDB archives and Qdrant snapshots, commits, and pushes. Requires the runner to have SSH access to the GitLab repo (via deploy key).

| Used by | `backup-dbs.yaml` → `upload_to_gitlab` job |
|---------|---------------------------------------------|
| **Dependencies** | `GitPython` |

**Required environment variables:**
- `BACKUP_REPO` — GitLab repository SSH/HTTPS URL
- `BACKUP_REPO_NAME` — Local directory name for the clone
- `QDRANT_SNAPSHOTS_DIR` — Path to the Qdrant snapshots directory

### Pipeline Review Scripts

#### `evaluate_review_gate.py`

Parses the architecture and code review output files produced by the Cursor Pipeline Review, extracts verdicts and scores, and gates the CI pipeline (exit 0 = pass, exit 1 = fail). Writes a summary table to the GitHub Actions Job Summary.

| Used by | `cursor-pipeline.yml` → `Evaluate Review Scores` step |
|---------|-------------------------------------------------------|
| **Dependencies** | None (stdlib only) |

**Parsed signals:**
- Architecture verdict: `APPROVE`, `NEEDS REVISION`, or `REJECT` (from `PIPELINE_VERDICT:` line)
- Code health score: `N/10` (from various patterns in the output)
- Exit status: `SUCCESS`, `REVISION_LIMIT`, `USER_INPUT_REQUIRED`, `ERROR`, `SKILL_NOT_FOUND`

**Environment variables (optional):**
- `CODE_REVIEW_THRESHOLD` — Minimum code score to pass (default: `8`)
- `CODE_REVIEW_FILE` — Path to code review output (default: `code_review_output.txt`)
- `ARCH_REVIEW_FILE` — Path to architecture review output (default: `arch_review_output.txt`)

#### `extract_pipeline_telemetry.py`

Extracts token usage from Cursor CLI JSON output, estimates costs using per-model pricing, and produces a `telemetry.json` artifact plus a Markdown summary table.

| Used by | `cursor-pipeline.yml` → `Extract Pipeline Telemetry` step |
|---------|-----------------------------------------------------------|
| **Dependencies** | None (stdlib only) |

**Environment variables:**
- `ORCHESTRATOR_MODEL` — Orchestrator model name (default: `composer-2.5-fast`)
- `ARCH_JUDGE_MODEL` — Architecture judge model name
- `CODE_JUDGE_MODEL` — Code judge model name
- `PR_NUMBER` — Pull request number (for telemetry metadata)
- `BRANCH_REF` — Branch reference (for telemetry metadata)

---

## Other Files

- **`CODEOWNERS`** — Defines code ownership for each directory. GitHub automatically requests reviews from the listed owners when a PR touches their paths.
- **`CODERABBIT.md`** — Documentation for the CodeRabbit automated code review integration.

---

## Prerequisites

1. GitHub must be able to access the target cluster **OR** you must have a self-hosted runner that can access both GitHub and the cluster (see [Creating a Runner](#creating-a-runner) below)
2. GitHub Environments must be configured with the appropriate variables and secrets for each cluster (e.g., `PRE-PRODUCTION`, `PRODUCTION`)

### Important Notes

- Since every deployment is a bit different, the existing workflows won't necessarily work out of the box for deployments different from the one currently in use. Users wanting to deploy UnifAI in their own clusters should be aware of the infra and networking to either fit the workflow to their needs or create a new workflow that fits it.
- When using runners, the `runs-on` field refers to **labels**, not runner names. Ensure matching labels exist before running workflows.
- Environment-specific variables (like `QDRANT_URL`, `MONGO_URI`, `API_URL`) must be configured in GitHub repository settings under **Environments**.

## GitHub Environments Setup

The workflows use GitHub Environments to manage cluster-specific configurations:

1. Go to **Settings** → **Environments** in your repository
2. Create environments matching your cluster names (e.g., `PRE-PRODUCTION`, `PRODUCTION`)
3. Add environment-specific variables:
   - `API_URL` - Kubernetes API server URL
   - `MONGO_URI` - MongoDB connection string
   - `QDRANT_URL` - Qdrant cluster URL
   - `SKIP_VERIFY_TLS` - Set to skip TLS verification for K8s API connections (used by MongoDB backup)
4. Add environment-specific secrets:
   - `ACCESS_TOKEN` - Kubernetes access token
   - Other sensitive credentials as needed

## Running Workflows Manually

### Prerequisites

1. The workflow must have the `workflow_dispatch` trigger enabled
2. GitHub CLI must be installed and authenticated
3. The workflow file must exist in the `main` branch (workflows in feature branches cannot be manually triggered)

### Example Command

```bash
gh workflow run backup-dbs.yaml \
  -f target_cluster=PRE-PRODUCTION \
  -f target_branch=main
```

**Parameters:**
- `-f target_cluster` - The cluster environment to backup (must match a configured GitHub Environment)
- `-f target_branch` - The branch to checkout for the workflow

---

## Appendix

### Runner Inventory

The following self-hosted runners are registered under the **applied-ai-enablement** organization runner group in GitHub. They are deployed on the CNV cluster and used for workflows that require access to the Red Hat internal network. All other workflows use GitHub-hosted runners.

| Runner Name | Labels | Purpose | Notes |
|-------------|--------|---------|-------|
| cnv-runner-1 | `linux`,`unifai` | Database backups, dependency verification |  |
| cnv-runner-2 | `linux`,`unifai`,`umami` | Container builds, vulnerability scanning, umami backups |  |

the connection to Github is invoked from the gituser user in each machine.
in addition a systemd service was created and enabled on each runner to invoke the runner upon restarts (service name: github-runner.service)

> **Credentials:** Runner VM access credentials (IP, user, password) are stored in Vault under the teams space. Do not commit them to this repository. Contact the CI/CD maintainers listed in `CODEOWNERS` for access.

### Creating a Runner

To create a new self-hosted runner:

1. Go to your repository's **Settings** tab
2. In the left sidebar, select **Actions** → **Runners**
3. Click **New self-hosted runner**
4. Follow the setup instructions (the authentication tokens are unique to your repository)

For more details, see the [GitHub documentation on self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners).

### Connecting to GitLab

Since the GitHub runners can't reach GitLab directly, we use a VM running on CNV. To make GitLab "accessible" to this runner, we need to set a deploy key at the target repo (go to repository > deploy keys and set the VM public key as the deploy key). This allows the VM to perform actions on the target repo without needing to specify credentials.

### UnifAI Team Infrastructure

In the case of the UnifAI team, the lab structure is a bit "special" — the code resides in a public GitHub repo whereas all the deployment resources reside inside the company intranet. To overcome this we have a self-hosted runner with access to both domains, so the code is downloaded from GitHub (for example in order to run a workflow) and then all actions are run against the internal resources.
