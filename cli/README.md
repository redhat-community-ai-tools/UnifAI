# UnifAI CLI

A terminal interface for the UnifAI multi-agent platform. Lets you browse workflows and inventory, and run interactive agent sessions — directly from your shell.

**No additional UnifAI services required beyond MAS and MongoDB.** The CLI connects to the MAS API and authenticates through the SSO backend.

---

## Requirements

- Python 3.11+
- Access to a running MAS instance
- Network access to the SSO backend (for login)

---

## Installation

```bash
pip install ./cli
```

This installs the `unifai` command on your PATH.

---

## Authentication

Before using any command, authenticate with your SSO account:

```bash
unifai auth login
```

This opens a browser window. After you log in, the session is cached locally for 10 hours — you won't need to re-authenticate until it expires.

**Running on a remote host (VM, container)?**  
The OAuth callback server runs locally on the remote host, so you need to forward its port to your laptop first:

```bash
# Pick a fixed port and forward it before logging in
ssh -L 9000:localhost:9000 your-remote-host

# Then on the remote host:
unifai auth login --callback-port 9000
```

Other auth commands:

```bash
unifai auth status     # check who is logged in and when the session expires
unifai auth logout     # clear the local session
```

---

## Commands

### Workflows — Browse and run agent workflows

```bash
# List all workflows available to you
unifai blueprints list

# Inspect a workflow's full configuration
unifai blueprints inspect <blueprint-id>

# List workflows and pick one to inspect interactively
unifai blueprints list --interactive
```

### Inventory — Browse registered resources

Resources include LLMs, tools, agents, retrievers, providers, and conditions.

```bash
# List all inventory items
unifai inventory list

# Filter by category
unifai inventory list --category llms
unifai inventory list --category tools

# Inspect a specific resource
unifai inventory inspect <resource-id>

# List and select interactively
unifai inventory list --interactive
```

Available categories: `llms`, `tools`, `nodes`, `retrievers`, `providers`, `conditions`

### Workflow — Run a session

```bash
# Select a workflow interactively, then start a chat session
unifai workflow run

# Run a specific workflow by name or ID
unifai workflow run --blueprint-name "My Workflow"
unifai workflow run --blueprint-id <blueprint-id>

# Send a single prompt without entering interactive mode
unifai workflow run --blueprint-name "My Workflow" --question "Summarize the latest report"
```

Once a session starts, type your prompts at the `You:` prompt. Type `exit` or press Ctrl+C to end the session.

---

## Configuration

All settings can be overridden with environment variables or a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `MAS_URL` | `http://{MAS_IP}:{MAS_PORT}` | MAS server base URL |
| `SSO_URL` | `http://{SSO_IP}:{SSO_PORT}` | SSO backend URL |
| `AUTH_CALLBACK_PORT` | auto-select | Fixed port for the OAuth callback server |
| `UNIFAI_USER` | — | Skip auth prompt and use this username directly |

---

## Interactive mode

Running `unifai` with no arguments launches a menu-driven interface that walks through all the above commands without needing to remember flags:

```bash
unifai
```
