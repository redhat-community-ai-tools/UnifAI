# GitHub Actions & CI/CD

This folder contains all CI/automation scripts and workflows for GitHub Actions.

## Overview

Workflows are configured to run automated tasks using GitHub Actions. For complex operations, we use dedicated scripts (in `.github/scripts/`) that are invoked from the workflow files.

## Available Workflows

- **backup-dbs.yaml** - Automated database backups for MongoDB and Qdrant (backups are being uploaded to internal gitlab and have no retention at the moment)
- **verify-agent-deps.yaml** - Dependency verification for agents



## Prerequisites

1. GitHub must be able to access the target cluster **OR** you must have a self-hosted runner that can access both GitHub and the cluster (see [Creating a Runner](#creating-a-runner) below)
2. GitHub Environments must be configured with the appropriate variables and secrets for each cluster (e.g., `PRE-PRODUCTION`, `PRODUCTION`)

### Important Notes

- Since every deployment is a bit different. the existing workflows won't necessarily work out of the box for deployment different from the one currently in use. Users wanting to deploy UnifAI in their own clusters should be aware of the infra and networking to either fit the workflow to their needs or create a new workflow that fits it. 
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
4. Add environment-specific secrets:
   - `ACCESS_TOKEN` - Kubernetes access token
   - Other sensitive credentials as needed

## Database Backup Details

### MongoDB Backup

MongoDB backups are performed using `mongodump`, which is straightforward:

```bash
mongodump --uri="mongodb://localhost:27017" --out="/tmp/backup"
```

**Parameters:**
- `--uri` - Connection string to the MongoDB instance to backup
- `--out` - Target directory for the backup (creates a new folder)
- `--db` (optional) - Specific database name (default: all databases)

### Qdrant Backup

Qdrant backups require creating snapshots via the API or UI. The workflow uses a Python script (`.github/scripts/qdrant_backup.py`) to:
1. Connect to the Qdrant cluster
2. Create snapshots for all collections
3. Download the snapshots locally
4. Upload them to the backup repository

For more details, see the [Qdrant documentation](https://qdrant.tech/documentation/database-tutorials/create-snapshot/).

## Running Workflows Manually

### Prerequisites

1. The workflow must have the `workflow_dispatch` trigger enabled
2. GitHub CLI must be installed and authenticated
3. The workflow file must exist in the `main` branch (workflows in feature branches cannot be manually triggered)

### Example Command

```bash
gh workflow run backup-dbs.yaml \
  -f target_cluster=PRE-PRODUCTION \
  -f target_branch=GENIE-1071/backup_dbs \
  -f target_namespace=tag-ai--pipeline
```

**Parameters:**
- `-f target_cluster` - The cluster environment to backup (must match a configured GitHub Environment)
- `-f target_branch` - The branch to checkout for the workflow
- `-f target_namespace` - The Kubernetes namespace to backup

## Appendix

### Creating a Runner

To create a new self-hosted runner:

1. Go to your repository's **Settings** tab
2. In the left sidebar, select **Actions** → **Runners**
3. Click **New self-hosted runner**
4. Follow the setup instructions (the authentication tokens are unique to your repository)

For more details, see the [GitHub documentation on self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners).


### Connecting to gitlab

Since the GitHub runners can't reach gitlab we ha to use a VM running on CNV.
To make gitlab "accessible" to this runner, we need to set a deploy token at the target repo (go to repository > deploy keys and set the VM public key as the deploy key). This allows the VM perform actions on the target repo without needing to specify credentials.

### UnifAI team infra structure

In the case if the Unifai team the lab structure is a bit "special" the code resides in a public GitHub repo whereas all the deployment resources reside inside the company intra-net. to overcome this we have a self-hosted runner with access to both domains so the code is downloaded from github (for example in order to run a workflow) and then all actions are being run against the intra resources.


