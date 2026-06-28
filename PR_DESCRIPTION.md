# OpenShell Sandbox Integration for AI Agents

## Yosi's Words

> We gave our AI agents a secure room to work in. Before this PR, when an agent needed to run code, search files, or call external tools — it did everything directly on the worker pod, with no isolation. Now, the agent gets its own sandbox container (via OpenShell) with a locked-down network policy that only allows it to reach the specific MCP servers it needs. The agent doesn't even know it's in a sandbox — the same tool names, same behavior — just running somewhere safe. Think of it as putting the agent inside a controlled environment where we decide exactly what it can access.

---

## Summary

This PR introduces OpenShell sandbox support for the multi-agent system. AI agents (starting with DeepAgent, with Claude Agent next) can now execute all their tools inside a remote, policy-controlled sandbox container instead of running directly on the worker pod.

**Key outcome:** Full tool isolation with zero LLM behavior change — the agent sees the same tool names and schemas, but everything runs inside a sandboxed container with network-level enforcement.

---

## What is `sandbox_exec`?

The `sandbox_exec` package (`multi-agent/lib/mas/elements/tools/sandbox_exec/`) provides the infrastructure for running agent operations inside OpenShell sandboxes:

| File | Purpose |
|------|---------|
| `sandbox_exec.py` | **SandboxExecTool** — manages sandbox lifecycle (create, reconnect, exec, close) via gRPC. Lazy creation with deterministic naming per session+agent. |
| `openshell_backend.py` | **OpenShellSandboxBackend** — adapts the deepagents framework's `BaseSandbox` interface to route all built-in file/shell tools through the sandbox. |
| `client.py` | SDK client factory — creates `SandboxClient` from in-memory PEM strings (mTLS). |
| `config.py` | Configuration for sandbox gateway endpoint and TLS credentials. |
| `sandbox_exec_factory.py` | Factory for creating `SandboxExecTool` instances from blueprint config. |
| `validator.py` | Validates sandbox configuration at blueprint build time. |
| `spec/` | Spec definitions for the sandbox tool configuration schema. |
| `identifiers.py` | Constants and naming utilities. |

---

## How Agents Use the Sandbox

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Worker Pod                                             │
│                                                         │
│  ┌─────────────┐     ┌──────────────────────────────┐  │
│  │  Agent Node │     │  SandboxExecTool             │  │
│  │  (DeepAgent)│────▶│  - _get_or_create_session()  │  │
│  │             │     │  - gRPC connection            │  │
│  └─────────────┘     └──────────┬───────────────────┘  │
│                                  │ gRPC (mTLS)          │
└──────────────────────────────────┼──────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  OpenShell Gateway           │
                    │  - Sandbox lifecycle         │
                    │  - Policy enforcement        │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Sandbox Container           │
                    │  - Network namespace         │
                    │  - Landlock filesystem       │
                    │  - OPA network policy        │
                    │  - L7 HTTP inspection        │
                    │                              │
                    │  Only allowed to reach:      │
                    │  ✅ MCP Atlassian server     │
                    │  ❌ Everything else          │
                    └─────────────────────────────┘
```

### Two Routing Mechanisms

| Mechanism | What it routes | How |
|-----------|---------------|-----|
| **OpenShellSandboxBackend** | DeepAgent's 7 built-in tools (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `execute`) | Implements `BaseSandbox` — framework auto-routes all file/shell operations to `execute()` and `upload_files()` |
| **SandboxToolProxy** | MCP tools (e.g., `jira_search`, `jira_create_issue`) | Wraps each MCP tool call in `exec_python()` inside the sandbox |

### Agent Integration Pattern

```python
# When SandboxExecTool is in the agent's domain tools:

# 1. Built-in tools → OpenShellSandboxBackend
#    LLM calls write_file("/report.md", content)
#    → framework calls backend.upload_files(...)
#    → session.exec(["bash"], stdin=content) via gRPC
#    → file written inside sandbox

# 2. MCP tools → SandboxToolProxy
#    LLM calls jira_search(query="...")
#    → SandboxToolProxy.run(...)
#    → session.exec_python(tool_function) via gRPC
#    → HTTP POST to MCP server FROM sandbox (policy-controlled)

# When NO SandboxExecTool is present:
#    → LocalShellBackend (subprocess on pod) — unchanged behavior
```

### Network Policy (Auto-Generated)

When `SandboxExecTool` detects MCP providers, it automatically generates a network policy that only allows the sandbox to reach those specific endpoints:

```yaml
network_policies:
  mcp_atlassian:
    endpoints:
      - host: mcp-server.example.com
        port: 443
        protocol: rest
        tls: terminate
        enforcement: enforce
        access: full
    binaries:
      - path: /usr/bin/python3.12
      - path: /usr/bin/python3
```

No manual policy configuration needed — the system figures out what the agent needs access to and locks everything else down.

---

## Supported Agents

| Agent | Status | Mechanism |
|-------|--------|-----------|
| **DeepAgent** | Implemented | `OpenShellSandboxBackend` + `SandboxToolProxy` |
| **Claude Agent** | Planned | we need to think about it!@!! calude agent work via cli where the SDk exists! currently not support BaseSandbox as Deepagent |
| **Custom Agent** | Planned | TBD |

The integration is agent-agnostic — any node that has `SandboxExecTool` in its domain tools can use the sandbox. The detection logic is a simple `isinstance` check.

---

## Backward Compatibility

- No sandbox tool configured → `LocalShellBackend` (current behavior, unchanged)
- No gateway credentials provisioned → no `SandboxExecTool` created → local execution
- Tool names and schemas are identical — the LLM sees no difference
- Existing workflows without sandbox config are completely unaffected

---

## Files Changed

| File | Change |
|------|--------|
| `multi-agent/lib/mas/elements/tools/sandbox_exec/openshell_backend.py` | **New** — `OpenShellSandboxBackend(BaseSandbox)` adapter |
| `multi-agent/lib/mas/elements/nodes/deep_agent/deep_agent_node.py` | **Modified** — `_build_backend()` detects sandbox tool |
