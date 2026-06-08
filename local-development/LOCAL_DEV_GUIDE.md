# UnifAI — Local Development Guide

A step-by-step guide for running UnifAI locally — launch the **full stack** in tmux, a **group of services**, or a **single service** in your terminal.

## Quick Start

0. **[Prerequisites](#2-prerequisites)** — make sure you have Python 3.11–3.13, pipx, Node.js 22+, pnpm, tmux, and Podman/Docker installed (macOS Podman users: run `podman machine init` first)
1. **[Install the CLI](#install-the-cli)** (from the **repo root**):
   ```bash
   pipx install -e local-development/
   ```
2. **[Run first-time setup](#410-first-time-setup)** — creates venvs, generates `.env` files, auto-generates the Flask `secret_key`, starts infra, and prompts for Keycloak credentials:
   ```bash
   unifai-dev init
   ```
3. **[Run](#4-running-the-development-environment)** — start the dev environment:
   ```bash
   unifai-dev start              # full-stack
   unifai-dev start backend --fg # or single service
   ```

> Steps 0–2 are one-time setup. On subsequent runs, just use step 3.
>
> If you prefer manual control over each step, skip `init` and follow these instead:
> - `unifai-dev env generate` — generate `.env` files (also adds any missing keys to existing files)
> - Edit `shared-resources/identity/.env` — fill in `client_id` and `client_secret`
> - `unifai-dev venv setup` — create virtual environments
> - `unifai-dev start` — start services

---

## 1. Overview

UnifAI is composed of five services that run side-by-side during local development:


| Service         | Directory                       | Port  | Language   |
| --------------- | ------------------------------- | ----- | ---------- |
| RAG Backend     | `rag/`                          | 13457 | Python     |
| Identity        | `shared-resources/identity/`    | 13456 | Python     |
| Multi-Agent API | `multi-agent/`                  | 8002  | Python     |
| Backend         | `backend/`                      | 8005  | Python     |
| UI (Vite)       | `ui/`                           | 5000  | TypeScript |


In addition, two background workers run alongside the services:


| Worker          | Directory      | Purpose                                       |
| --------------- | -------------- | --------------------------------------------- |
| Celery Worker   | `rag/`         | Async RAG pipelines (document & Slack queues) |
| Temporal Worker | `multi-agent/` | Distributed agent workflow execution          |


### Architecture

The `local-development/` directory is a hexagonal-architecture Python package driven by a single `services.yaml` source of truth:

```
local-development/
├── services.yaml            # Single source of truth (services, infra, groups)
├── pyproject.toml           # Package definition (pipx install -e local-development/)
├── unifai-dev               # Fallback entry point (thin CLI script)
├── LOCAL_DEV_GUIDE.md       # This file
│
├── devtool/                 # Python package
│   ├── cli.py               # Typer CLI → orchestrator (entry point: main())
│   ├── domain/              # Pure domain — no I/O
│   │   ├── models.py        # Service, InfraComponent, ServiceStatus, etc.
│   │   ├── registry.py      # Pure domain class: typed lookups, parsing helpers
│   │   └── env.py           # Env-file domain logic (GenerateResult, expected_keys, constants)
│   ├── ports/               # Interfaces (ABCs)
│   │   ├── container_runtime.py
│   │   ├── session_manager.py
│   │   ├── process_manager.py
│   │   ├── venv_manager.py
│   │   ├── python_resolver.py
│   │   ├── health_probe.py
│   │   └── env_file_store.py   # .env file I/O abstraction
│   ├── adapters/            # Implementations
│   │   ├── container/          # Container runtime package
│   │   │   ├── base.py         # SubprocessContainerRuntime base class
│   │   │   ├── podman.py       # PodmanRuntime adapter
│   │   │   ├── docker.py       # DockerRuntime adapter
│   │   │   └── factory.py      # ContainerRuntimeFactory (auto-detection)
│   │   ├── tmux.py / foreground.py
│   │   ├── process.py          # Port detection + process killing
│   │   ├── venv.py
│   │   ├── python_detector.py  # Finds a suitable Python interpreter
│   │   ├── registry_loader.py  # Loads services.yaml → Registry
│   │   └── env_file_store.py   # FilesystemEnvFileStore (.env file I/O)
│   └── services/            # Application services
│       ├── orchestrator.py     # Thin facade delegating to focused services
│       ├── startup_service.py  # Start flow, shell, exec
│       ├── infra_service.py    # Infrastructure container management
│       ├── venv_service.py     # Virtual environment management
│       ├── env_service.py      # .env file orchestration (generate, inspect, resolve)
│       ├── diagnostic_service.py # Health status + doctor
│       ├── init_service.py     # First-time setup wizard
│       ├── health_checker.py   # Health probing and issue analysis
│       ├── recovery.py         # Dependency-aware restart engine
│       ├── pane_matcher.py     # Match tmux panes to services
│       ├── constants.py        # Session name, shared constants
│       └── shell_utils.py      # Bash resolution
│
└── tests/
    ├── test_orchestrator.py       # Orchestrator facade (attach, clean)
    ├── test_startup_service.py    # StartupService (layout, shell, exec)
    ├── test_registry.py
    ├── test_env.py                # EnvService logic (generate, inspect, align)
    ├── test_env_service.py        # EnvService orchestration (public API)
    ├── test_env_file_store.py     # FilesystemEnvFileStore adapter (integration)
    ├── test_health_checker.py
    ├── test_venv_service.py       # VenvService (setup, check, sync)
    ├── test_venv_adapter.py       # LocalVenvManager (create, verify, exists)
    ├── test_python_detector.py    # LocalPythonResolver (find_python)
    ├── test_infra_service.py      # InfraService (start, stop, reset, status)
    ├── test_init_service.py       # InitService (first-time wizard)
    ├── test_diagnostic_service.py # DiagnosticService (doctor, logs)
    ├── test_recovery.py           # Recovery (restart, restart_failed)
    ├── test_process_adapter.py    # LocalProcessManager (ports, kill)
    ├── test_container_runtime.py
    ├── test_graceful_stop.py
    └── test_cli_window_specs.py
```

All service definitions, infrastructure containers, port assignments, and service groups are declared in `services.yaml` — there is no per-service Python class or hardcoded bash logic.

---

## 2. Prerequisites

### Platform

The `unifai-dev` CLI requires **Linux** or **macOS**. It depends on bash, tmux, and Unix process management and does not run natively on Windows.

**Windows users:** install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) and run everything inside the Linux environment.

### Required


- **Python 3.11 – 3.13** (3.11 or 3.12 recommended; 3.14+ is **not** supported because PyO3's maximum supported version is 3.13)
- **pipx** — used to install the `unifai-dev` CLI in an isolated environment. If you don't have it:

  ```bash
  # Fedora / RHEL
  sudo dnf install pipx && pipx ensurepath

  # macOS (Homebrew)
  brew install pipx && pipx ensurepath

  # Ubuntu / Debian
  sudo apt install pipx && pipx ensurepath

  # Fallback (any system with pip)
  python3 -m pip install --user pipx && pipx ensurepath
  ```

  Restart your shell (or run `source ~/.bashrc`) after `ensurepath` so that the `~/.local/bin` path takes effect.

- **Node.js 22+** and **pnpm** (the UI's `package.json` pins `pnpm` via `packageManager`)
- **MongoDB** — used by all Python backends for persistence
- **Qdrant** — vector database for RAG embeddings
- **Redis** — used by Identity (session/cache) and Multi-Agent (streaming)
- **tmux** — used for multi-service mode (auto-created session with panes)

### Install the CLI

From the **repo root**, run:

```bash
pipx install -e local-development/
```

This installs the `unifai-dev` command globally in an isolated environment. You only need to do this once.

To **reinstall** (e.g. after a broken state, or to pick up new dependencies added to `pyproject.toml`):

```bash
pipx install -e local-development/ --force
```

> [!NOTE]
> The path is relative — you must run this from the repo root (the directory containing `local-development/`).
> Alternatively, use an absolute path from anywhere:
>
> ```bash
> pipx install -e /path/to/UnifAI/local-development/
> ```

> [!TIP]
> If your default `python3` is 3.14+, specify a supported interpreter so the CLI's own venv matches the service requirements:
>
> ```bash
> pipx install -e local-development/ --python python3.12
> ```

> [!TIP]
> Because the install is **editable** (`-e`), code changes in `local-development/devtool/` take effect immediately — no reinstall needed. You only need `--force` when the package metadata itself changes (new dependencies, entry points, etc.).

> [!TIP]
> Enable **tab autocompletion** for service names, group names, and infrastructure components:
>
> ```bash
> unifai-dev --install-completion    # bash/zsh/fish
> ```
>
> After restarting your shell, press `<TAB>` after any argument to see available options.

### Local Auth Mode

By default, `services.yaml` has `local_auth: true`. This means:

- **No SSO credentials needed** — the env generator skips Keycloak placeholder keys (`keycloak_base_url`, `client_id`, `client_secret`, `keycloak_realm`) for the identity service and writes `local_auth_enabled=true` instead.
- **No Red Hat SSO / VPN required** — the identity service runs with a `DevOAuthClient` that returns hardcoded dev-user responses.
- **Login page shows "Login as Dev User"** — click the button and you are instantly logged in as `dev-user` with a full session.

To use real Keycloak SSO instead:

1. Switch to SSO mode — either set `local_auth: false` in `services.yaml`, or override per-session with an environment variable:
   ```bash
   export UNIFAI_LOCAL_AUTH=false
   ```
2. **First time:** Run `unifai-dev init` — it regenerates `.env` files (adding the Keycloak placeholder keys) and prompts you to fill in `client_id` and `client_secret` interactively.
3. **Subsequent times:** `unifai-dev start` is enough — it re-runs env generation and your existing credentials are preserved.
4. The login page will show "Login using SSO" (the dev button is hidden).

To switch back to local auth, set `UNIFAI_LOCAL_AUTH=true` (or revert `services.yaml`) and run `unifai-dev start` — the `local_auth_enabled=true` line is added back automatically.

### Flask Secret Key *(Auto-Generated)*

All Flask services require a `secret_key` for signing session cookies. In local development, this is handled automatically:

- During `unifai-dev init`, you are prompted to **auto-generate** a shared key or **enter your own**.
- During `unifai-dev start`, any unresolved `secret_key` values are auto-generated silently.
- The generated key is stored in `local-development/.dev-secret-key` (gitignored) and shared across all services, so sessions are consistent and survive restarts.

You do not need to configure `secret_key` manually. If you want to reset it:

```bash
rm local-development/.dev-secret-key
unifai-dev env generate --force
unifai-dev start
```


### Optional

- **Temporal** — distributed workflow execution (multi-agent)
- **RabbitMQ** — async RAG pipelines (Celery broker)
- **Keycloak** — OAuth 2.0 / OIDC authentication

### Infrastructure via containers

The tool auto-creates containers for infrastructure services using **Podman** or **Docker**. Make sure at least one is installed and running.

> [!NOTE]
> **macOS users (Podman):** After installing Podman, you must initialize the Podman machine before running `unifai-dev init`:
>
> ```bash
> podman machine init
> ```
>
> This is a one-time step. The devtool will auto-start the machine when needed, but it cannot create one for you.

If your container runtime requires elevated privileges (e.g. `sudo docker`), set the `UNIFAI_CONTAINER_RUNTIME` environment variable to override auto-detection:

```bash
export UNIFAI_CONTAINER_RUNTIME='sudo docker'
```

When set, the tool uses this command instead of auto-detecting Podman/Docker. Add it to your shell profile (`.bashrc`, `.zshrc`, etc.) to persist across sessions.


| Container | Ports       | Notes                          |
| --------- | ----------- | ------------------------------ |
| MongoDB   | 27017       |                                |
| RabbitMQ  | 5672, 15672 | 15672 = management UI          |
| Qdrant    | 6333, 6334  | 6333 = HTTP API, 6334 = gRPC   |
| Redis     | 6379        |                                |
| Temporal  | 7233, 8233  | 7233 = gRPC API, 8233 = web UI |


Not every service needs every container. The tool starts only the required ones based on which services you launch:


| Service           | MongoDB | RabbitMQ | Qdrant | Redis | Temporal |
| ----------------- | ------- | -------- | ------ | ----- | -------- |
| `backend`         | x       |          |        |       |          |
| `rag`             | x       | x        | x      |       |          |
| `multi-agent`     | x       |          |        | x     | x        |
| `identity`        |         |          |        | x     |          |
| `ui`              |         |          |        |       |          |
| `celery-worker`   | x       | x        | x      |       |          |
| `temporal-worker` | x       |          |        | x     | x        |


---

## 3. Setting Up Virtual Environments

> [!NOTE]
> **This section is for manual control only.** If you ran `unifai-dev init` (recommended), virtual environments were already created — skip to [Section 4](#4-running-the-development-environment).
>
> You can also create venvs on demand with:
> - `unifai-dev venv setup` — create all venvs at once
> - `unifai-dev start --setup-venv` — create venvs and start services in one step

### 3.1 Automated setup

Create all venvs at once:

```bash
unifai-dev venv setup
```

Or for a single service:

```bash
unifai-dev venv setup backend
```

### 3.2 Manual setup

All commands assume you are in the **repo root**. Python must be 3.11–3.13 (see [Prerequisites](#2-prerequisites)).

Each Python service needs a venv with its own dependencies plus `global_utils` (a shared library) installed as an editable package. The pattern is the same for every service:

```bash
cd <service-dir>
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt   # or: pip install -e ".[all]" for multi-agent
pip install -e <path-to>/global_utils
deactivate && cd <back-to-root>
```

Service-specific values:


| Service     | Directory                       | Install command                   | `global_utils` path  |
| ----------- | ------------------------------- | --------------------------------- | -------------------- |
| multi-agent | `multi-agent/`                  | `pip install -e ".[all]"`         | `../global_utils`    |
| backend     | `backend/`                      | `pip install -r requirements.txt` | `../global_utils`    |
| rag         | `rag/`                          | `pip install -r requirements.txt` | `../global_utils`    |
| identity    | `shared-resources/identity/`    | `pip install -e .`                | `../../global_utils` |


For the **UI** (React/TypeScript — no Python venv):

```bash
cd ui && pnpm install && cd ..
```

---

## 4. Running the Development Environment

The `unifai-dev` CLI automates local development. Install it once with `pipx install -e local-development/` (see [Install the CLI](#install-the-cli)), then run from the **repo root**.

> [!NOTE]
> The `.env` files (`rag/.env`, `shared-resources/identity/.env`, `ui/.env.local`) are gitignored and safe — they will **not** appear in `git status`. No source files are modified by the tool.

### 4.1 CLI reference

```
unifai-dev <command> [options]
```

**Service lifecycle:**

| Command                          | Description                                                                   |
| -------------------------------- | ----------------------------------------------------------------------------- |
| `start [targets...] [flags]`    | Start services (tmux or `--fg` foreground). Defaults to group `all`.          |
| `stop`                           | Stop the tmux session                                                         |
| `restart [targets...] [--failed]`| Dependency-aware restart of one or more services/groups                       |
| `destroy`                        | Kill the tmux session and stop all infrastructure containers                  |

**Start flags:**

| Flag                              | Description                                                                      |
| --------------------------------- | -------------------------------------------------------------------------------- |
| `--fg`                            | Foreground mode — run a single primary service in your terminal                  |
| `--setup-venv`                    | Create virtual environments before starting                                      |
| `--window [name=]svc1,svc2,...`   | Group services into a custom tmux window (repeatable)                            |

**Targets** can be service names, group names, or a mix. When omitted, defaults to the `all` group.

**Context helpers:**

| Command                       | Description                                                        |
| ----------------------------- | ------------------------------------------------------------------ |
| `shell <service>`             | Open an interactive shell with the service's venv and env loaded   |
| `exec <service> <command...>` | Run a command inside the service's context, then exit              |
| `attach <service>`            | Jump to the tmux pane running a specific service                   |

**Discovery:**

| Command                        | Description                                                |
| ------------------------------ | ---------------------------------------------------------- |
| `list`                         | Show all services, groups, and infrastructure at a glance  |
| `info <service>`               | Deep-dive into a single service (ports, groups, infra, venv, env) |

**Monitoring:**

| Command                        | Description                           |
| ------------------------------ | ------------------------------------- |
| `status`                       | Health dashboard (infra + services)   |
| `logs <service>`               | Print log file for a service          |
| `logs <service> --follow`      | Tail log file in real time            |
| `doctor`                       | Full diagnostic (Python, venvs, infra, ports, env files) |

**Infrastructure:**

| Command                              | Description                                         |
| ------------------------------------ | --------------------------------------------------- |
| `infra start [containers...]`        | Start all or named containers                       |
| `infra start --for <service>`        | Start only the containers a service needs           |
| `infra stop`                         | Stop all infrastructure containers                  |
| `infra status`                       | Show status of all containers                       |
| `infra logs <component> [--follow]`  | View (or tail) a container's logs                   |
| `infra reset [components...]`        | Stop, remove, and recreate containers               |

**Virtual environments:**

| Command                       | Description                                          |
| ----------------------------- | ---------------------------------------------------- |
| `venv setup [service]`        | Create venv(s) — all or one service                  |
| `venv setup [service] --force`| Delete and recreate existing venvs                   |
| `venv sync [service]`         | Update dependencies in existing venv(s) without recreating |
| `venv check`                  | Verify Python versions match                         |

**Environment files:**

| Command                | Description                                    |
| ---------------------- | ---------------------------------------------- |
| `env generate`         | Create .env files; append missing keys to existing files |
| `env generate --force` | Regenerate .env files from scratch even if they exist    |
| `env show <service>`   | Print current env config for a service         |

**Setup and maintenance:**

| Command                  | Description                                              |
| ------------------------ | -------------------------------------------------------- |
| `init [--non-interactive]`| First-time setup (infra, venvs, env)                    |
| `clean [--dry-run]`      | Remove log files and stopped containers (venvs excluded by default) |
| `clean --logs`           | Only clean log files                                     |
| `clean --venvs`          | Only clean virtual environments (opt-in)                 |
| `clean --containers`     | Only clean stopped containers                            |

### 4.2 Service groups

Services can be launched individually by name or as predefined groups. Groups are defined in `services.yaml`:

| Group          | Services                                                              |
| -------------- | --------------------------------------------------------------------- |
| `all`          | backend, rag, multi-agent, identity, ui, celery-worker, temporal-worker |
| `services`     | backend, rag, multi-agent, identity, ui                                 |
| `workers`      | celery-worker, temporal-worker                                          |
| `agents`       | multi-agent, temporal-worker                                            |
| `rag-stack`    | rag, celery-worker                                                      |
| `backend-only` | backend, identity                                                       |

You can mix service names and group names freely:

```bash
unifai-dev start rag-stack          # rag + celery-worker
unifai-dev start agents backend     # multi-agent + temporal-worker + backend
unifai-dev start backend rag        # just those two
```

> [!NOTE]
> **Non-primary services** (`celery-worker`, `temporal-worker`) cannot be launched alone. They must always be part of a multi-service start — use a group like `rag-stack` or `agents`, or name them alongside their parent service.

### 4.3 Logging

All service output is captured to log files alongside live tmux pane output:

- **Log directory:** `/tmp/unifai-dev/logs/` (configurable in `services.yaml`)
- **Per-service logs:** `/tmp/unifai-dev/logs/<service>.log`
- **Infrastructure logs:** `/tmp/unifai-dev/logs/infra.log`

To view logs:

```bash
unifai-dev logs backend           # print log
unifai-dev logs backend --follow   # tail in real time
```

Log files are truncated on each `start` invocation — they capture the current session only.

> [!TIP]
> If a container fails to start with a "port already in use" error, check `/tmp/unifai-dev/logs/infra.log` for details.

### 4.4 Environment

The `start` command automatically generates `.env` files. If an `.env` file already exists, any keys defined in `services.yaml` but missing from the file are appended automatically (existing values are preserved). You can also run these independently:

```bash
unifai-dev env generate           # create .env files; add missing keys to existing
unifai-dev env generate --force    # regenerate .env files from scratch
unifai-dev env show identity        # inspect a service's env config
```

**Generated `.env` files (gitignored):**


| File                                | Contents                                                                             |
| ----------------------------------- | ------------------------------------------------------------------------------------ |
| `backend/.env`                      | `hostname_local=127.0.0.1`, `secret_key` (auto-generated)                            |
| `rag/.env`                          | `hostname_local=127.0.0.1`, `port=13457`, `secret_key` (auto-generated)              |
| `multi-agent/.env`                  | `secret_key` (auto-generated)                                                        |
| `shared-resources/identity/.env`    | `keycloak_base_url`, `keycloak_realm`, `client_id`, `client_secret` (placeholders), `hostname_local`, `port`, `frontend_url`, `backend_env`, `secret_key` (auto-generated) |
| `ui/.env.local`                     | `DEV_PORT=5000`, `DEV_HOST=0.0.0.0`, proxy targets for all backends                  |

> [!NOTE]
> The `secret_key` value is auto-generated on first run and shared across all Flask services. The generated key is stored in `local-development/.dev-secret-key` (gitignored). See [Flask Secret Key](#flask-secret-key-auto-generated) for details.


### 4.5 Python version enforcement

The tool auto-detects a Python interpreter (prefers `python3.11` → `python3.12` → `python3.13` → `python3`, and rejects anything outside 3.11–3.13). Before launching, it verifies that each service's venv was built with the **same Python minor version**.

To override auto-detection:

```bash
export UNIFAI_PYTHON=python3.11
unifai-dev start
```

To check your current venv versions:

```bash
unifai-dev venv check
```

---

### 4.6 Single-service foreground mode

Run **one primary service** in your terminal with live auto-reload using `--fg`. Only the infrastructure containers that service needs are started.

```bash
unifai-dev start backend --fg
```

The tool will:

1. Start only the required infrastructure containers
2. Generate `.env` files and auto-resolve `secret_key`
3. Verify the service's venv exists and its Python version matches
4. Check for port conflicts and prompt to kill occupants if needed
5. Launch the service in your foreground terminal with debug/auto-reload

Press `Ctrl+C` to stop.

**Examples:**

```bash
unifai-dev start rag --fg
unifai-dev start backend --fg
unifai-dev start multi-agent --fg
```

> [!NOTE]
> Workers (`celery-worker`, `temporal-worker`) cannot run in foreground mode — they are non-primary services. Use a group instead: `unifai-dev start rag-stack`

---

### 4.7 Multi-service tmux mode (default)

When you start multiple services (or omit `--fg`), the tool creates a tmux session with auto-windowed panes.

```bash
unifai-dev start                 # full stack (all services + workers)
unifai-dev start rag-stack       # rag + celery-worker
unifai-dev start services        # all 5 primary services (no workers)
```

> [!NOTE]
> This assumes you already ran `unifai-dev init` (which creates venvs, generates `.env` files, etc.). If you haven't, you can pass `--setup-venv` to create venvs on the fly: `unifai-dev start --setup-venv`.

If a previous tmux session is still open, destroy it first:

```bash
unifai-dev destroy
unifai-dev start
```

The tool will:

1. Start required infrastructure containers via Podman/Docker
2. Generate `.env` files and auto-resolve `secret_key`
3. Verify all venvs exist and Python versions match
4. Check for port conflicts — if any required ports are occupied, show the process name and PID and prompt to kill them (`[y/N]`)
5. Create a tmux session (`unifai-dev`) with auto-windowed panes:
   - **Window "services"** — one pane per primary service (tiled layout)
   - **Window "workers"** — one pane per worker (if any workers are selected)
6. All output is captured to log files via `tee`

**Useful tmux commands once attached:**


| Action                    | Keys                                                   |
| ------------------------- | ------------------------------------------------------ |
| Switch to next window     | `Ctrl-b n`                                             |
| Switch to previous window | `Ctrl-b p`                                             |
| Navigate between panes    | `Ctrl-b ←/→/↑/↓`                                       |
| Scroll pane output        | `Ctrl-b [` then arrow keys, `q` to exit                |
| Destroy session           | `unifai-dev destroy`               |


---

### 4.8 Managing infrastructure containers

You can manage infrastructure containers independently:

```bash
# Start only what a specific service needs
unifai-dev infra start --for backend       # → mongo
unifai-dev infra start --for rag            # → mongo, rabbitmq, qdrant
unifai-dev infra start --for multi-agent    # → mongo, redis, temporal

# Cherry-pick specific containers
unifai-dev infra start mongo qdrant

# Check what's running
unifai-dev infra status

# View container logs
unifai-dev infra logs mongo
unifai-dev infra logs mongo --follow        # tail in real time

# Reset a misbehaving container (stop → remove → recreate)
unifai-dev infra reset mongo

# Stop all infrastructure
unifai-dev infra stop
```

---

### 4.9 Health checks and diagnostics

Check the health of all running services and infrastructure:

```bash
unifai-dev status
```

This probes each service's port and shows container status.

For a full diagnostic (Python, venvs, containers, ports, env files):

```bash
unifai-dev doctor
```

To restart failed services (checks infra dependencies first):

```bash
unifai-dev restart backend
unifai-dev restart backend rag              # restart multiple services
unifai-dev restart agents                   # restart a group
unifai-dev restart --failed                 # auto-restart all unhealthy services
```

---

### 4.10 First-time setup

The `init` command runs the full first-time setup in one go:

```bash
unifai-dev init
```

It performs these steps in order:

1. **Check prerequisites** — Python version, container runtime, tmux
2. **Start infrastructure** — all containers (MongoDB, Redis, etc.)
3. **Create virtual environments** — for all Python services and the UI
4. **Generate `.env` files** — with defaults and placeholders
5. **Resolve auto-generated values and placeholders** — prompts for `secret_key`, `client_id`, and `client_secret`
6. **Shell completion** — offers to install tab autocompletion for your shell (bash/zsh/fish)

After `init` completes, you can run `unifai-dev start` directly — no additional setup flags needed.

In CI or scripted environments, use `--non-interactive` to skip credential prompts (you'll need to fill in placeholders manually afterwards):

```bash
unifai-dev init --non-interactive
```

---

### 4.11 Context helpers: shell, exec, attach

These commands let you interact with a service's environment without manually activating venvs or sourcing `.env` files.

**`shell`** — drop into an interactive bash session with the service's venv activated and env loaded:

```bash
unifai-dev shell backend
# You're now in backend/ with the venv active — run pytest, manage.py, etc.
```

**`exec`** — run a single command in the service's context:

```bash
unifai-dev exec backend python -m pytest tests/
unifai-dev exec rag pip list
```

**`attach`** — jump directly to a running service's tmux pane:

```bash
unifai-dev attach backend
```

---

### 4.12 Custom tmux window layouts

By default, `start` puts primary services in a "services" window and workers in a "workers" window. Use `--window` to override this layout:

```bash
# Put rag and celery-worker together in a named window; all remaining services
# go into the default "services" window automatically
unifai-dev start --window rag=rag,celery-worker --window agents=multi-agent,temporal-worker

# Only start specific services alongside the windows
unifai-dev start --window rag=rag,celery-worker backend identity

# Unnamed windows get auto-generated names
unifai-dev start --window backend,identity --window rag,celery-worker
```

Each `--window` creates a separate tmux window with the listed services as panes. Without positional arguments, all services are started and those not assigned to a `--window` go into a default "services" window. With positional arguments, only the specified services are started — unassigned ones go into a "services" window.

---

### 4.13 Cleaning up stale resources

Remove old log files, stopped containers, or virtual environments:

```bash
unifai-dev clean                    # remove logs + stopped containers
unifai-dev clean --dry-run          # preview what would be removed
unifai-dev clean --logs             # only clean log files
unifai-dev clean --venvs            # only clean virtual environments
unifai-dev clean --containers       # only clean stopped containers
```

---

### 4.14 Verifying the setup

Once all services are running, open a browser and navigate to:

```
http://127.0.0.1:5000
```

The Vite dev server proxies API requests to the backends automatically:


| UI Path   | Backend                  |
| --------- | ------------------------ |
| `/api1/*` | RAG (port 13457)         |
| `/api2/*` | Multi-Agent (port 8002)  |
| `/api3/*` | Identity (port 13456)    |
| `/api4/*` | Backend (port 8005)      |


---

## 5. Typical Development Workflows

### "I'm working on the Backend service"

```bash
# Single service in foreground — auto-starts MongoDB
unifai-dev start backend --fg

# Edit code in your IDE → Flask auto-reloads → see changes immediately
# Test: curl http://127.0.0.1:8005/api/health
```

### "I'm working on the RAG service"

```bash
# RAG + Celery worker together (auto-starts MongoDB + RabbitMQ + Qdrant)
unifai-dev start rag-stack

# Or just RAG in foreground
unifai-dev start rag --fg
```

### "I'm working on the UI"

```bash
# UI alone in foreground (no containers needed)
unifai-dev start ui --fg

# Need backends too? Start them alongside:
unifai-dev start ui backend rag
```

### "I'm working on Multi-Agent"

```bash
# Multi-Agent + Temporal worker (auto-starts MongoDB + Redis + Temporal)
unifai-dev start agents

# Or just multi-agent in foreground
unifai-dev start multi-agent --fg
```

### "Brand new clone — set up everything from scratch"

```bash
# 1. Install the CLI (one-time)
pipx install -e local-development/

# 2. Run first-time setup — creates venvs, generates .env, starts infra, prompts for credentials
unifai-dev init

# 3. Launch
unifai-dev start

# — or single-service:
unifai-dev start backend --fg
```

---

## 6. Comparison: Foreground vs Multi-Service


|                      | `start <name> --fg`          | `start` / `start <group>`   |
| -------------------- | ---------------------------- | ---------------------------- |
| **Use case**         | Working on one service       | Integration testing, demos   |
| **Services started** | Just the one you pick        | All selected (group or list) |
| **Containers**       | Only what's needed           | Union of all selected        |
| **Terminal**         | Foreground in your shell     | tmux session                 |
| **Auto-reload**      | Yes (Flask debug / Vite HMR) | Yes                          |
| **Venv check**       | Checks the one service       | Checks all Python venvs      |
| **Log files**        | `/tmp/unifai-dev/logs/`      | `/tmp/unifai-dev/logs/`      |
| **Workers**          | Not allowed alone            | Auto-windowed in "workers"   |


---

## 7. Port Reference


| Service     | Port  | URL                                              |
| ----------- | ----- | ------------------------------------------------ |
| Backend     | 8005  | [http://127.0.0.1:8005](http://127.0.0.1:8005)   |
| RAG         | 13457 | [http://127.0.0.1:13457](http://127.0.0.1:13457) |
| Multi-Agent | 8002  | [http://127.0.0.1:8002](http://127.0.0.1:8002)   |
| Identity    | 13456 | [http://127.0.0.1:13456](http://127.0.0.1:13456) |
| UI (Vite)   | 5000  | [http://127.0.0.1:5000](http://127.0.0.1:5000)   |



| Infrastructure | Port(s)                     |
| -------------- | --------------------------- |
| MongoDB        | 27017                       |
| RabbitMQ       | 5672, 15672 (management UI) |
| Qdrant         | 6333 (HTTP), 6334 (gRPC)    |
| Redis          | 6379                        |
| Temporal       | 7233 (gRPC), 8233 (web UI)  |


---

## 8. Known Issues

### Python & Virtual Environments

#### No suitable Python found

The tool auto-detects Python by trying `python3.11`, `python3.12`, `python3.13`, and `python3` in order. It requires a version between 3.11 and 3.13 (3.14+ is not supported). If no suitable version is found, install one:

```bash
# Fedora / RHEL
sudo dnf install python3.11

# macOS (Homebrew)
brew install python@3.11

# Ubuntu / Debian
sudo apt install python3.11 python3.11-venv
```

Make sure `python3` (or `python3.11` / `python3.12` / `python3.13`) is on your `PATH`. Do **not** use Python 3.14+.

#### Python version mismatch between venvs

The tool **enforces** that every venv's Python minor version matches the detected interpreter. If you see a mismatch error:

1. **Recreate the venvs** to match the detected interpreter:

```bash
unifai-dev venv setup
```

2. **Override the detected interpreter** to match your existing venvs:

```bash
export UNIFAI_PYTHON=python3.12   # ← match your venv version
unifai-dev start
```

3. **Check all venvs at once:**

```bash
unifai-dev venv check
```

#### `venv/bin/activate: No such file or directory`

You skipped the venv setup in [Section 3](#3-setting-up-virtual-environments). Create the venv for the failing service:

```bash
unifai-dev venv setup backend
```

Or use `--setup-venv` with start.

#### Dependencies out of date

If `requirements.txt` or `pyproject.toml` was updated, sync the venv without recreating it:

```bash
unifai-dev venv sync              # all services
unifai-dev venv sync backend      # single service
```

#### `ModuleNotFoundError: No module named 'global_utils'`

You forgot to install `global_utils` into that service's venv. Activate the venv and run:

```bash
pip install -e /path/to/UnifAI/global_utils
```

Or re-sync the venv (which reinstalls all dependencies including `global_utils`):

```bash
unifai-dev venv sync backend
```

#### `PyYAML is required`

If you installed via `pipx`, PyYAML is handled automatically. If you see this error, reinstall the CLI:

```bash
pipx install -e local-development/ --force
```

---

### Containers & Infrastructure

#### No working container runtime found

The tool auto-detects Podman and Docker by checking that the binary exists on `PATH` and that `<runtime> info` succeeds. Common reasons for failure:

- **Docker requires `sudo`** — the user isn't in the `docker` group, so `docker info` fails with a permission error. Either add yourself to the group (`sudo usermod -aG docker $USER`, then log out and back in) or set the override:

  ```bash
  export UNIFAI_CONTAINER_RUNTIME='sudo docker'
  ```

- **Binary not on `PATH`** — the runtime is installed in a non-standard location. Point the tool at it:

  ```bash
  export UNIFAI_CONTAINER_RUNTIME='/usr/local/bin/docker'
  ```

#### Podman machine not running

On macOS/remote Linux, Podman requires a running machine. If containers fail to start:

```bash
podman machine init    # first time only
podman machine start
```

Alternatively, install Docker and the tool will auto-detect it as a fallback.

> [!TIP]
> Container startup errors are captured in `/tmp/unifai-dev/logs/infra.log`. Check that file if containers silently fail to start.

#### Ghost Celery/Temporal workers after restart

When you run `unifai-dev start` again , the tmux session is terminated via SIGHUP. Celery interprets SIGHUP as a reload signal rather than a termination signal, so the worker process can survive as an orphan. (`destroy` / 'stop' sends Ctrl+C first, which Celery handles correctly — but if a task is mid-flight and the 10 s timeout expires, the same SIGHUP fallback applies.) Symptoms:

- The new worker shows a **pidbox warning**: `A node named celery@... is already using this process mailbox!`
- Tasks dispatched from RAG are consumed by the ghost (no output in your tmux pane)

**Fix — kill the ghost manually:**

```bash
pkill -TERM -f 'celery.*worker'
# or for temporal:
pkill -TERM -f 'temporal-worker'
```

Then restart:

```bash
unifai-dev start rag-stack
```

> [!NOTE]
> This only affects portless workers (celery-worker, temporal-worker). Port-based services (backend, rag, etc.) are detected and killed by the port-conflict check on every start.

---

#### Celery worker fails to connect

If the Celery worker crashes with a connection error, RabbitMQ is likely not running. Verify:

```bash
unifai-dev infra status
```

If RabbitMQ is missing, start it:

```bash
unifai-dev infra start rabbitmq
```

#### Temporal worker fails to connect

Similarly, if the Temporal worker crashes, ensure the Temporal container is running:

```bash
unifai-dev infra status
unifai-dev infra start temporal
```

---

### Networking & Ports

#### Port already in use

During `unifai-dev start`, the tool checks every required service port and shows which process is using it (name + PID). You are prompted to kill the occupants:

```
  ⚠ port 8005 (backend) — in use by: python3.12 (PID 54321)
  ✔ port 13457 (rag) — free

  Kill processes on occupied ports? [y/N]:
```

If you answer **y**, the tool sends `SIGTERM` first (graceful shutdown), then `SIGKILL` after 0.5 s if the process is still alive. If you answer **n**, the tool continues but the affected services will likely fail with "address already in use".

If you need to kill a port manually (e.g. outside of the tool), use `ss` (available on all Linux systems) or `lsof`:

```bash
# Find what's on a port (works without lsof)
ss -tlnp 'sport = :8005'

# Or with lsof (macOS / full Linux installs)
lsof -ti :8005 | xargs kill
```

If a **container** fails to bind a port (e.g. `pasta failed ... Address already in use`), check `/tmp/unifai-dev/logs/infra.log`. A common cause is a previously created container or a system-installed service (e.g. `mongod`) still holding the port:

```bash
unifai-dev infra stop             # stop all infra containers
sudo systemctl stop mongod                             # if system MongoDB is running
```

#### Port 5000 occupied by AirPlay on macOS

macOS uses port 5000 for the AirPlay Receiver service. The devtool's port-kill feature cannot terminate this system process. If the UI service fails to start on port 5000, disable AirPlay Receiver manually:

**System Settings → General → AirDrop & Handoff → AirPlay Receiver → Off**

#### Firewall blocking container ports

On Fedora/RHEL, `firewalld` may silently block connections to container-exposed ports (27017, 6333, 5672, etc.). If a service can't reach a container despite it running, check your firewall:

```bash
sudo firewall-cmd --list-ports
```

To temporarily open a port:

```bash
sudo firewall-cmd --add-port=27017/tcp    # MongoDB example
```

Or allow the entire Podman/Docker bridge interface:

```bash
sudo firewall-cmd --zone=trusted --add-interface=podman0   # Podman
sudo firewall-cmd --zone=trusted --add-interface=docker0   # Docker
```

If SELinux is blocking container access (check with `ausearch -m avc -ts recent`), you can temporarily set it to permissive mode:

```bash
sudo setenforce 0
```

To make it persistent across reboots, edit `/etc/selinux/config` and set `SELINUX=permissive`.

#### Vite proxy returns `502 Bad Gateway`

If the UI loads but API calls fail with `502`, the backend service that Vite is trying to proxy to is not running. Run the health check:

```bash
unifai-dev status
```

The proxy target mapping is:


| UI Path   | Expected Backend         |
| --------- | ------------------------ |
| `/api1/*` | RAG (port 13457)         |
| `/api2/*` | Multi-Agent (port 8002)  |
| `/api3/*` | Identity (port 13456)    |
| `/api4/*` | Backend (port 8005)      |


Also verify you are connected to the **Red Hat SSO** — authentication-related requests will fail without it.

---

### UI & Frontend

#### Node.js version too old

The UI requires **Node.js 22+**. If you use [nvm](https://github.com/nvm-sh/nvm) and your default version is older, `unifai-dev doctor` will report:

```
  ✖ Node.js: Node.js v18.17.0 is too old (requires 22+).
```

Fix it by switching to Node.js 22:

```bash
nvm install 22    # first time only
nvm use 22
```

To make Node.js 22 your default so you don't have to run `nvm use` every session:

```bash
nvm alias default 22
```

#### `pnpm: command not found`

Install pnpm globally:

```bash
npm install -g pnpm
```

Or enable Corepack (ships with Node.js 16+):

```bash
corepack enable
```
