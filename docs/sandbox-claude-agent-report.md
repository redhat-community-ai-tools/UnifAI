# OpenShell Sandbox Integration — ClaudeAgent Analysis

## Branch: `openshell-sandbox-vm-sdk`

**Date:** June 28, 2026

---

## Part 1: The Problem

### What works today (DeepAgent)

DeepAgent has FULL sandbox support. When a `SandboxExecTool` is configured:
- Shell commands → run in sandbox
- File read/write/edit → run in sandbox
- Glob/Grep → run in sandbox
- MCP tools (Jira, etc.) → run in sandbox

**Why it works:** The `deepagents` framework has a pluggable `BackendProtocol`. We swap `LocalShellBackend` with `OpenShellSandboxBackend` and everything routes through the remote sandbox automatically.

### What doesn't work today (ClaudeAgent)

ClaudeAgent has PARTIAL sandbox support:
- MCP tools (Jira, etc.) → run in sandbox ✅
- Shell commands (Bash) → run LOCALLY on worker ❌
- File read/write/edit → run LOCALLY on worker ❌
- Glob/Grep → run LOCALLY on worker ❌

**Why it doesn't work:** The Claude Agent SDK has no `BackendProtocol`. Its built-in tools (`Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep`) are hardcoded — they always execute on the local machine. There is no way to redirect them.

### Your architecture constraint

You want:
- Agent reasoning (LLM thinking) → runs on the **worker pod** (local)
- Tool execution (shell, files, MCP) → runs on **OpenShell sandbox** (remote)

---

## Part 2: Mode 2 and Mode 3 (from the Red Hat Article)

Source: [Red Hat AI and OpenShell: Driving security-enhanced agent execution for enterprise AI](https://www.redhat.com/ko/blog/red-hat-ai-and-openshell-driving-security-enhanced-agent-execution-for-enterprise-ai)

---

### MODE 2: Sandbox as the Execution Environment

#### What it is

The agent's "brain" (reasoning) is completely separated from its "hands" (execution). A **platform** sits in the middle — it orchestrates the agent loop, and when the agent needs to execute something, the platform sends it to a disposable sandbox.

The key word is **platform-driven** — a platform API owns the sandbox lifecycle (create, run, teardown). The developer does NOT manage the sandbox.

#### How it looks

```
┌─────────────────────────────────┐
│  PLATFORM (owns everything)     │
│                                 │
│  - Hosts the LLM reasoning      │
│  - Makes tool decisions          │
│  - Creates sandboxes             │
│  - Routes execution to sandbox   │
│  - Tears down sandbox when done  │
└──────────────┬──────────────────┘
               │ "run this code"
┌──────────────▼──────────────────┐
│  SANDBOX (you control this)     │
│                                 │
│  - Executes code                 │
│  - File system access            │
│  - Network calls                 │
│  - Has NO credentials stored     │
│    (injected at network boundary)│
└─────────────────────────────────┘
```

#### Example 1: Anthropic Self-Hosted Environments

**Status: REAL — available in beta (`managed-agents-2026-04-01`)**

Verified via:
- [Anthropic docs: Self-hosted sandboxes](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes)
- [Poll for Work API reference](https://platform.claude.com/docs/en/api/beta/environments/work/poll)
- [Anthropic skills repo](https://github.com/anthropics/skills/blob/main/skills/claude-api/shared/managed-agents-self-hosted-sandboxes.md)

How it works:
1. You create a self-hosted environment via Anthropic's API
2. You generate an environment key for your worker
3. Your worker polls Anthropic for execution tasks
4. When Anthropic's agent decides to run code → your worker receives the task
5. Your worker executes the task (can route to OpenShell sandbox)
6. Result goes back to Anthropic → agent continues reasoning

```bash
# Create self-hosted environment
ant beta:environments create --name self-hosted --config '{"type": "self_hosted"}'

# Create agent on Anthropic cloud
ant beta:agents create --name secure-agent --model claude-sonnet-4-6

# Your worker polls for tasks
export ANTHROPIC_ENVIRONMENT_KEY=sk-ant-oat01-...
ant beta:worker poll --environment-id env_... --workdir /workspace
```

The worker provides a fixed built-in toolset (`bash`, `read`, `write`, `edit`, `glob`, `grep`). For custom tools, you use the SDK worker (`EnvironmentWorker`). You can also use `--on-work ./spawn.sh` to spin up a fresh container (or OpenShell sandbox) per session.

**Who runs what:**
- Anthropic cloud → agent reasoning (brain) + tool decisions
- Your worker → polls for tasks, executes them
- OpenShell sandbox → can be wired in via `--on-work` to run tasks in isolation

**Important:** The agent reasoning runs on ANTHROPIC'S CLOUD, not on your worker. Your worker is only an execution slave.

#### Mode 2 key properties

- Platform owns the sandbox lifecycle — developer writes no sandbox code
- Credentials are NEVER stored inside the sandbox — injected at network boundary
- ALL execution happens in the sandbox — not just some tools
- Agent-generated code NEVER runs on your infrastructure outside the sandbox
- Highest security level

---

### MODE 3: Sandbox Only the Code Execution

#### What it is

The agent runs freely on YOUR infrastructure with full access to everything (credentials, APIs, file system). When the agent generates code that needs to run, ONLY that code gets sent to a sandbox. The agent itself is NOT isolated.

The key word is **framework-driven** — the agent framework exposes a "sandbox extension point," and YOU (the developer) wire up a sandbox provider, manage sessions, and control teardown.

#### How it looks

```
┌─────────────────────────────────┐
│  YOUR INFRASTRUCTURE            │
│  (agent runs here, unsandboxed) │
│                                 │
│  - Agent reasoning (LLM)         │
│  - Has all credentials           │
│  - Has full API access           │
│  - Has file system access        │
│  - YOU manage sandbox lifecycle  │
│                                 │
│  When agent generates code: ────┼───┐
└─────────────────────────────────┘   │
                                       │
┌──────────────────────────────────────▼──┐
│  SANDBOX (only generated code runs here)│
│                                         │
│  - Code execution                        │
│  - Isolated from your infra              │
│  - Policy-controlled network             │
└─────────────────────────────────────────┘
```

#### Example from the article: OpenAI Agents SDK Sandbox Extensions

The article uses the OpenAI Agents SDK as its example for Mode 3. In that SDK, there is a native `SandboxRunConfig` extension point — you plug in `OpenShellSandboxClient` and all code execution routes through the sandbox automatically.

#### Applying Mode 3 to Claude Agent SDK (our implementation)

The Claude Agent SDK does NOT have a `SandboxRunConfig` extension point. Its built-in tools (`Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep`) are hardcoded to execute locally.

**However, we can achieve the same Mode 3 outcome** by:

1. **Disabling** the built-in tools via `disallowed_tools` config
2. **Creating replacement MCP tools** with the same functionality that route through `SandboxExecTool`
3. **Exposing them** via `create_sdk_mcp_server("sandbox-tools", tools=[...])`

The agent still runs on the worker (unsandboxed). But when it needs to execute code, read files, or run shell commands — those calls go to the sandbox instead of the local machine.

**What we'd build:**

```python
# Custom MCP tools that route through SandboxExecTool:
sandbox_bash(cmd)          # → session.exec(["bash", "-c", cmd])
sandbox_read(path)         # → session.exec(["cat", path])
sandbox_write(path, content) # → session.exec(["bash"], stdin=write_script)
sandbox_edit(path, old, new) # → session.exec(["sed"/script])
sandbox_glob(pattern)      # → session.exec(["find", ...])
sandbox_grep(pattern, path) # → session.exec(["grep", ...])
```

**In ClaudeAgentNode:**

```python
# Disable built-in tools that run locally
self._disallowed_tools = ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]

# Provide sandbox-backed replacements via MCP
sandbox_tools = create_sdk_mcp_server("sandbox-tools", tools=[
    sandbox_bash, sandbox_read, sandbox_write,
    sandbox_edit, sandbox_glob, sandbox_grep,
])
kwargs["mcp_servers"]["sandbox-tools"] = sandbox_tools
```

**Result:** Same architecture as what the OpenAI Agents SDK does natively, but implemented manually for the Claude Agent SDK.

```
┌─────────────────────────────────────────────────┐
│  Worker Pod (agent runs here)                   │
│                                                 │
│  ClaudeAgentNode                                │
│  - LLM reasoning (Claude via Vertex AI)         │
│  - Built-in tools: DISABLED                     │
│  - MCP tools exposed:                           │
│    sandbox_bash, sandbox_read, sandbox_write,   │
│    sandbox_edit, sandbox_glob, sandbox_grep      │
│    + existing MCP tools (Jira, etc.)            │
│                                                 │
│  All tool calls route through SandboxExecTool ──┼──┐
└─────────────────────────────────────────────────┘  │
                                                      │ gRPC
┌─────────────────────────────────────────────────────▼──┐
│  OpenShell Sandbox                                     │
│  - Shell execution                                     │
│  - File system (read/write/edit)                       │
│  - MCP tool calls (Jira, Confluence, etc.)             │
│  - Network policy: only reach configured endpoints     │
└────────────────────────────────────────────────────────┘
```

**This achieves parity with DeepAgent's sandbox integration.**

#### Mode 3 key properties

- Agent process runs UNSANDBOXED — it has full access to your infrastructure
- Only GENERATED CODE is sandboxed — not the agent's own operations
- Developer manages the sandbox lifecycle (not a platform)
- Framework exposes an extension point that you wire up (or in our case, we simulate it)
- Lower security than Mode 2 — the agent itself can still access credentials
- Article says: "reasonable starting point, plan to graduate to Mode 1 or Mode 2"

---

### Mode 2 vs Mode 3: Side-by-Side

| | Mode 2 | Mode 3 |
|---|---|---|
| **What's sandboxed** | ALL execution | Only generated code |
| **What's NOT sandboxed** | Only reasoning | Agent process + credentials + APIs |
| **Who manages sandbox** | Platform (automatic) | Developer (manual) |
| **Credential isolation** | Full — never in sandbox | None — agent has full access |
| **Developer sandbox code** | None (platform handles it) | You write it |
| **Security level** | High | Medium |
| **Article's advice** | Use for production, multi-tenant | Starting point, graduate to Mode 1/2 |

---

## Part 3: Can These Modes Apply to ClaudeAgent?

### Reality Check

| Mode | Applies to Claude Agent SDK? |
|---|---|
| Mode 2 (Anthropic Self-Hosted) | Requires Managed Agents API. Reasoning moves to Anthropic cloud. Breaks your architecture. |
| Mode 3 (pattern: sandbox extension point) | Claude SDK has no native extension point, BUT we can simulate it by disabling built-in tools and providing sandbox-backed MCP replacements. **This is the path forward.** |

---

## Part 4: Applicability to Your Architecture

You asked: can Mode 2 or Mode 3 from the article be used to implement sandbox for ClaudeAgent, while keeping the architecture where the agent runs on the worker and sandbox runs on OpenShell?

**Answer:**

- **Mode 2:** NO — it requires moving reasoning to Anthropic's cloud. Breaks your architecture.

- **Mode 3:** YES — by disabling built-in tools and providing sandbox-backed MCP tools as replacements. This keeps the Claude Agent SDK, keeps the Claude model, keeps your architecture (agent on worker, execution on sandbox).

---

## Part 5: Limitations and Risks of Mode 3 (Sandbox MCP Replacements)

### Built-in Tools vs Sandbox Replacements — Key Differences

| Tool | Built-in Behavior | Sandbox Replacement Difference |
|---|---|---|
| **Bash** | Persistent session, `run_in_background` support, schema baked into model weights, 2min default timeout, 30k char output limit | Same sandbox session = persistent state. Need to implement `run_in_background` via `nohup`. gRPC latency per call. |
| **Read** | Reads text, images, PDFs, notebooks. Supports `offset`/`limit` for chunked reading. Returns content with line numbers. | Text only — binary content (images/PDFs) hard to pass over gRPC stdout. Need `cat -n` or similar for line numbers. |
| **Write** | Creates new or overwrites existing. Simple `{"file_path", "content"}` schema. | Minimal difference. Implementable via `cat > file` with stdin pipe. |
| **Edit** | Exact string replacement. SDK validates `old_string` exists and is unique BEFORE executing. Context-window efficient (only sends diff). | Need to implement validation ourselves (read file → check uniqueness → apply). Multi-step = more latency. |
| **Glob** | Built-in pattern matching (`**/*.py`, `src/**/*.ts`) | `find` command in sandbox. Straightforward. |
| **Grep** | Built-in regex search over file contents | `grep -rn` in sandbox. Straightforward. |

### Risk Assessment

| Risk | Description | Severity |
|---|---|---|
| **Model training mismatch** | Claude is TRAINED on its built-in tools. It knows them by exact name from training data. Custom MCP tools have different names (e.g., `mcp__sandbox-tools__bash` instead of `Bash`). The model must learn them via description only — may reduce quality/reliability. | **HIGH** |
| **Tool naming confusion** | Claude may try to call disabled built-in names (`Bash`, `Read`) instead of the MCP replacements. The SDK would reject these calls, causing wasted turns. | **MEDIUM** |
| **Latency accumulation** | Every tool call adds 50-200ms gRPC round-trip. For file-heavy tasks (many reads/edits), latency adds up significantly. A task with 50 tool calls = 2.5-10s extra overhead. | **MEDIUM** |
| **Edit validation complexity** | Built-in Edit validates uniqueness natively. Our sandbox version needs a multi-step implementation (read file, check old_string uniqueness, then apply). More code, more failure points. | **MEDIUM** |
| **Binary file support** | Built-in Read handles images and PDFs natively. Sandbox version would only handle text unless we add base64 encoding for binary content transfer. | **LOW** (depends on use case) |
| **Background processes** | Built-in Bash has native `run_in_background` flag. Sandbox needs workaround (`nohup`, `&`). | **LOW** |
| **Error format mismatch** | Built-in tools return errors in a format Claude expects. Our MCP tools may return differently formatted errors, confusing the model. | **MEDIUM** |
| **Untested approach** | This "disable built-ins + replace with MCP" pattern has not been validated with the Claude Agent SDK in production. Unknown edge cases. | **HIGH** |

### Mitigation Strategies

| Risk | Mitigation |
|---|---|
| Model training mismatch | Use tool descriptions that closely match Claude's understanding of its built-in tools. Test thoroughly. |
| Tool naming confusion | Use a strong system prompt instructing Claude to use ONLY the provided MCP tools. Never mention built-in tool names. |
| Latency | Accept the trade-off (security > speed). Batch operations where possible. |
| Edit validation | Implement validation in the tool itself before applying the edit. Return clear error if old_string not found/not unique. |
| Binary files | For initial implementation, only support text files. Add base64 binary support later if needed. |
| Untested approach | Start with a PoC on a single use case. Validate Claude's behavior before committing to full implementation. |

---

## Appendix: Separate Reference — OpenAI Agents SDK Migration Guide

Source: [developers.openai.com/cookbook — Migrate from Claude Agent SDK](https://developers.openai.com/cookbook/examples/agents_sdk/migrate-from-claude-agent-sdk/readme)

This guide was explored as a separate question you asked. It is NOT from the Red Hat article. It's about **replacing the Claude Agent SDK entirely** with the OpenAI Agents SDK.

**Key point from the guide:**
- Claude Agent SDK puts harness + execution in the same boundary (no separation possible)
- OpenAI Agents SDK separates harness (trusted runtime) from compute (sandbox)
