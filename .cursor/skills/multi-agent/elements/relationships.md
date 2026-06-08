---
name: elements-relationships
scope: Deep implementation details for elements crossing into graph state and receiving deps
parent: _index.md
when_to_load: Implementing cross-boundary data flow through elements (channels, workspace, delegation)
---

# Elements → Graph (Channel Access)

## Declaration and Validation

```python
class CustomAgentSpec(BaseElementSpec):
    reads = {Channel.FILE_ATTACHMENTS, Channel.MESSAGES}
    writes = {Channel.MESSAGES}
```

`ElementValidationService` checks all declared channels exist in `GraphState`.

## Workspace Variable Propagation (Delegation Chain)

```
UserQuestionNode → stores data as workspace variable
  → OrchestratorNode → reads workspace for context
  → DelegateTaskTool._propagate_*() → copies workspace to child thread
  → CustomAgentNode → reads workspace → uses data
```

Key method: `DelegateTaskTool._propagate_file_attachments(parent_thread, child_thread)`

## Rules

- Workspace data MUST be serializable (`.model_dump()` for Pydantic)
- Channel READS/WRITES MUST be accurate (validation relies on them)
- External channels populated by InputProjector only, never by nodes

---

# Elements ← Session (Dependency Injection)

## How Elements Receive Infrastructure

```
container.py creates factories/services
  → WorkflowSessionFactory receives them via constructor
  → build_session() creates ElementDeps
  → SessionElementBuilder passes deps as kwargs to element factories
  → Element factory extracts what it needs
```

Pattern for elements needing infrastructure:
- Define factory callable in ElementDeps (e.g., `file_retrieve_tool_factory`)
- Element calls the factory at runtime to get the tool/service
- Element NEVER imports adapter code directly

---

# Adding a New Data Type Through the Full Stack

If you need new data to flow from user → delegation → agents:

1. Define model in `elements/llms/common/chat/`
2. Add channel to `GraphState` (if globally needed) with `external: True`
3. Populate in `SessionInputProjector.apply()`
4. Store as workspace variable in `UserQuestionNode`
5. Propagate in `DelegateTaskTool._propagate_*()` to child threads
6. Consume in target node (read workspace, inject into context/tools)
7. Update element specs: add channel to `reads` ClassVar
