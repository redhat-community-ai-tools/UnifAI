SERVICES.mas = {
  id: 'mas',
  name: 'Multi Agent System (MAS)',
  icon: '🤖',
  role: 'Multi-agent orchestration',
  type: 'APP',
  x: 600, y: 380,
  w: 190, h: 60,
  detail: {
    subtitle: 'Flask • Gunicorn • LangGraph / Temporal • Claude SDK • Deep Agents • Port 8002',
    modal: {
      job: `
        <p>The <strong>Multi-Agent System (MAS)</strong> is the brain of UnifAI. It lets users design <em>blueprints</em> — visual graphs of AI agent workflows — and then execute them.</p>
        <h3>Core Concepts</h3>
        <ul>
          <li><strong>Blueprint</strong> — a saved graph definition with nodes (agents, tools, retrievers) and edges (conditions, routing)</li>
          <li><strong>Session</strong> — a running instance of a blueprint, with state and streaming output</li>
          <li><strong>Catalog</strong> — registry of available node types and providers</li>
          <li><strong>Resources</strong> — shared configurations (LLM keys, RAG connections, MCP servers)</li>
        </ul>
        <h3>Execution Mode</h3>
        <p>The default execution mode is <strong>Background (Temporal)</strong>, configured via <code>engine_name=temporal</code>.</p>
        <ul>
          <li><strong>Background (default)</strong> — submitted to Temporal, returns 202 with workflow ID</li>
          <li><strong>Foreground (fallback)</strong> — in-process via LangGraph, with NDJSON streaming response; used when Temporal is unavailable</li>
        </ul>
        <h3>Identity & Collaboration</h3>
        <ul>
          <li>All data is scoped by an <strong>Identity</strong> (user or team). Team mode routes through team-scoped identity.</li>
          <li><strong>Collaboration</strong>: session presence, edit locks, typing indicators (via Redis)</li>
          <li><strong>Sharing</strong>: clone resources/blueprints between workspaces; direct "share to team" support</li>
        </ul>
        <h3>Integrations</h3>
        <ul>
          <li>Calls <strong>RAG</strong> for document retrieval</li>
          <li>Calls <strong>LLM providers</strong> (OpenAI, Google Gemini) via LangChain</li>
          <li>Runs <strong>Claude Agent SDK</strong> sessions (autonomous coding via Vertex AI)</li>
          <li>Runs <strong>LangChain Deep Agents</strong> (planning + subagent delegation)</li>
          <li>Connects to <strong>remote agents</strong> via A2A protocol</li>
          <li>Invokes <strong>external tools</strong> via MCP protocol</li>
          <li>Calls <strong>Identity service</strong> for team authorization</li>
        </ul>
      `,
      interfaces: `
        <h3>Sessions</h3>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/api/sessions/user.session.submit — default (Temporal)</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/api/sessions/user.session.execute — foreground fallback</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/sessions/session.subscribe</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/sessions/session.state.get</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/sessions/session.status.get</span></div>
        </div>
        <h3>Blueprints & Graph</h3>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/blueprints/</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/api/blueprints/</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/graph/validation/</span></div>
        </div>
        <h3>Catalog, Resources & More</h3>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/catalog/</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/resources/</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/templates/</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/actions/</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/shares/</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/statistics/</span></div>
        </div>
        <h3>Collaboration & Workspace</h3>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/api/collaboration/* — presence, edit locks, typing</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/api/workspace/workspace.cleanup</span></div>
        </div>
        <h3>Streaming Protocol</h3>
        <p>When <code>stream: true</code>, the response is <code>application/x-ndjson</code> — newline-delimited JSON chunks with heartbeats.</p>
      `,
      architecture: `
        <h3>Design Pattern: Hexagonal Architecture</h3>
        <p>MAS uses <strong>ports and adapters</strong>. Domain logic (blueprints, sessions, graph engine) in <code>lib/mas/</code> doesn't depend on infrastructure.</p>
        <h3>How It's Organized</h3>
        <ul>
          <li><strong><code>lib/mas/</code></strong> — The hexagon: 17 domain cores (blueprints, sessions, graph engine, elements, IEM, auth, collaboration, sharing, templates, validation, actions).</li>
          <li><strong><code>adapters/inbound/</code></strong> — Flask HTTP routes, Temporal workflow handlers.</li>
          <li><strong><code>adapters/outbound/</code></strong> — MongoDB repos (7), Redis streams/collab, LangGraph, Temporal, Identity HTTP, OAuth2.</li>
          <li><strong><code>bootstrap/</code></strong> — Composition root (<code>container.py</code>) wires everything at startup.</li>
        </ul>
        <h3>Graph Engine (BSP model)</h3>
        <p>Executes in <strong>supersteps</strong> (Bulk Synchronous Parallel): Plan → Execute (parallel) → Merge → Evaluate conditions → Repeat.</p>
        <p>Two backends: <strong>Temporal</strong> (distributed, durable — default) and <strong>LangGraph</strong> (in-process — fallback). Same BSP algorithm in both.</p>
        <h3>Key Design Decision: ChannelFactory</h3>
        <p><code>ChannelFactory</code> port has two adapters: <strong>Redis Streams</strong> (distributed) and <strong>in-process Queues</strong> (single-worker). Same code runs locally or at scale.</p>
      `,
    },
    job: `
      <p>The <strong>Multi-Agent System (MAS)</strong> is the core orchestration engine of UnifAI. It lets users design <em>blueprints</em> — visual graphs of AI agent workflows — execute them against LLMs, tools, and retrievers, and stream results in real time.</p>

      <h3>Core Domain Concepts</h3>
      <ul>
        <li><strong>Blueprint</strong> — a declarative YAML graph definition with nodes (agents, tools, retrievers), edges, and conditional routing. Blueprints are portable, versionable, and shareable. <code>BlueprintDraft</code> uses <code>$ref:</code> to point to resources; <code>BlueprintSpec</code> is the fully-resolved form.</li>
        <li><strong>Resource</strong> — a configured building block in the agent inventory (LLMs, tools, providers, retrievers, conditions, nodes, auths). Each has a <code>cfg_dict</code> validated against its element schema.</li>
        <li><strong>Session</strong> — a running instance of a blueprint. Contains <code>GraphState</code> (messages, output, inter_packets, threads, workspaces) and streams events via NDJSON.</li>
        <li><strong>Element Catalog</strong> — auto-discovered plugin registry of all available element types across 8 categories.</li>
        <li><strong>Template</strong> — a parameterized blueprint factory. Users fill a form, and <code>materialize()</code> creates a blueprint + resources in one step.</li>
        <li><strong>Actions</strong> — independent operations (auth flows, MCP/RAG connection checks) linked to element types.</li>
      </ul>

      <h3>Element Categories</h3>
      <ul>
        <li><strong>Nodes</strong> — user_question, custom_agent (ReAct/Plan-and-Execute), orchestrator, a2a_agent, claude_agent (Claude SDK autonomous sessions), deep_agent (LangChain Deep Agents), merger, final_answer, branch_chooser</li>
        <li><strong>LLMs</strong> — openai, google_genai, mock</li>
        <li><strong>Tools</strong> — mcp_proxy, ssh_exec, web_fetch, oc_exec + builtins (workplan, topology, delegation, time)</li>
        <li><strong>Providers</strong> — mcp_server (auto-discovers tools), rag_client, a2a_agent</li>
        <li><strong>Conditions</strong> — router_boolean, router_direct (IEM-driven), threshold</li>
        <li><strong>Retrievers</strong> — docs_rag, slack</li>
        <li><strong>Auths</strong> — oauth_client, google_oauth, github_oauth, jira_oauth</li>
      </ul>

      <h3>Session Execution Flow</h3>
      <p>When a user sends a message, this is what happens end-to-end:</p>
      <ul>
        <li><strong>1.</strong> UI calls <code>POST /sessions/user.session.submit</code> → MAS returns 202 with workflow ID</li>
        <li><strong>2.</strong> MAS queues a Temporal workflow (or runs LangGraph in-process)</li>
        <li><strong>3.</strong> UI subscribes via <code>GET /sessions/session.subscribe</code> (NDJSON stream)</li>
        <li><strong>4.</strong> Worker executes <strong>graph supersteps</strong>: PLAN → EXECUTE (parallel) → UPDATE (merge)</li>
        <li><strong>5.</strong> <code>UserQuestionNode</code> broadcasts a <code>TaskPacket</code> via IEM to adjacent agents</li>
        <li><strong>6.</strong> <code>RouterDirectCondition</code> routes to agents with pending packets</li>
        <li><strong>7.</strong> <code>CustomAgentNode</code> runs ReAct loop: LLM → tool calls → respond via IEM</li>
        <li><strong>8.</strong> <code>FinalAnswerNode</code> collects results, merges into <code>output</code> + <code>messages</code></li>
        <li><strong>9.</strong> Events stream through Redis → NDJSON → UI (llm_token, tool_calling, complete)</li>
        <li><strong>10.</strong> Final <code>GraphState</code> persisted to MongoDB</li>
      </ul>

      <h3>IEM — Inter-Element Messaging</h3>
      <p>Nodes communicate via <strong>typed packets</strong> in <code>GraphState.inter_packets</code>, not by writing to shared state. The dominant type is <code>TaskPacket</code> — carries a natural-language <code>Task</code> with thread_id, correlation, and response tracking. Adjacency is enforced (non-adjacent sends raise <code>IEMAdjacencyException</code>). <code>RouterDirectCondition</code> follows IEM traffic to decide which nodes run next, enabling message-driven re-entrancy (orchestrator ↔ agents loops).</p>

      <h3>Execution Mode</h3>
      <p>The configured default is <strong>Background (Temporal)</strong> — <code>engine_name=temporal</code>.</p>
      <ul>
        <li><strong>Background (Temporal) — default</strong> — distributed, durable. <code>TemporalSessionEngine</code> submits <code>SessionWorkflow</code> → <code>GraphTraversalWorkflow</code>. Workers are stateless; each activity rebuilds the node from a serialized mini-blueprint.</li>
        <li><strong>Foreground (LangGraph) — fallback</strong> — in-process, callables bound in <code>RTGraphPlan</code>. Used when Temporal is unavailable or for dev/simple graphs.</li>
      </ul>

      <h3>Identity, Collaboration & Sharing</h3>
      <ul>
        <li>All data is scoped by <strong>Identity</strong> (user or team). Team mode uses <code>IdentityProvider</code> for membership checks.</li>
        <li><strong>Collaboration</strong> — session presence, edit locks, typing indicators via Redis. Team sessions enforce busy-state semantics (LOCKED / IN_USE).</li>
        <li><strong>Sharing</strong> — invite-based with <code>ShareCloner</code> deep-copy and RID remapping. Direct share-to-team also supported.</li>
        <li><strong>Templates</strong> — marketplace of parameterized blueprints for one-click workflow creation.</li>
      </ul>

      <h3>User Journey</h3>
      <ul>
        <li><strong>1. Define Goal</strong> — what problem, which data sources, how many agents</li>
        <li><strong>2. Know Building Blocks</strong> — browse <code>/inventory</code> catalog (LLMs, agents, tools, etc.)</li>
        <li><strong>3. Set Up Inventory</strong> — create and configure resources</li>
        <li><strong>4. Build Workflow</strong> — visual graph builder at <code>/agentic-ai</code> with live YAML validation</li>
        <li><strong>5. Chat with Workflow</strong> — real-time execution at <code>/agentic-chats</code></li>
      </ul>

      <h3>Integrations</h3>
      <ul>
        <li><strong>RAG</strong> — document retrieval via <code>docs_rag</code> and <code>slack</code> retrievers</li>
        <li><strong>LLM providers</strong> — OpenAI, Google Gemini via LangChain wrappers</li>
        <li><strong>Claude Agent SDK</strong> — autonomous coding agent sessions via Anthropic Claude on Vertex AI (<code>claude_agent_node</code>)</li>
        <li><strong>LangChain Deep Agents</strong> — planning-capable agent delegation with built-in subagents and shell/filesystem (<code>deep_agent_node</code>)</li>
        <li><strong>A2A protocol</strong> — remote agent delegation via <code>a2a_agent</code> nodes</li>
        <li><strong>MCP protocol</strong> — external tool invocation via <code>mcp_server</code> providers (SSE/HTTP)</li>
        <li><strong>Identity service</strong> — team membership, user directory, OAuth callback relay</li>
        <li><strong>SSH / OpenShift</strong> — remote command execution via <code>ssh_exec</code> and <code>oc_exec</code> tools</li>
      </ul>
    `,
    interfaces: `
      <p>All routes under <code>/api/</code>. Auth via <code>X-Authenticated-User</code> header + identity params. UI accesses via <code>/api2/</code> Nginx proxy.</p>

      <details>
        <summary>Sessions <span class="ep-count">14</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/user.session.create — create session record</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/user.session.submit — execute via Temporal (default, 202)</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/user.session.execute — foreground fallback, sync or NDJSON stream</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/session.cancel — cancel Temporal workflow</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.state.get — full GraphState</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.chat.get — messages + output + status</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.status.get — status enum</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.user.list — all sessions for identity</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.user.blueprints.get — blueprint IDs in use</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.subscribe — late-join NDJSON stream</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.stream.status — Redis stream metadata</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.stream.active — list active streams</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.meta — get session metadata</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/session.meta — update metadata + typing sync</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/sessions/session.delete</span></div>
        </div>
      </details>

      <details>
        <summary>Blueprints <span class="ep-count">11</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/blueprints/blueprint.save — save new draft</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/blueprints/blueprint.update — update existing</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/available.blueprints.get — full docs for workspace</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/available.blueprints.summary.get — lightweight list</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/available.blueprints.resolved.get — $ref resolved</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/blueprint.info.get — single doc by ID</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/blueprint.draft.schema.get — JSON Schema</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/blueprints/remove.blueprint</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/blueprints/blueprint.metadata.set</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/blueprints/blueprint.validate — validate all elements</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/blueprints/draft.validate — validate before saving</span></div>
        </div>
      </details>

      <details>
        <summary>Resources <span class="ep-count">11</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/resources/resource.save — create resource</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/resources/resource.get — single by ID</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/resources/resources.list — filtered + paginated</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/resources/resource.update — update config/name</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/resources/resource.delete — fails if in use</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/resources/resource.validate — validate + deps</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/resources/resources.validate — parallel batch</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/resources/resource.card — element card</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/resources/resources.cards — batch cards</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/resources/config.validate — pre-save validation</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/resources/resource.schema — JSON Schema</span></div>
        </div>
      </details>

      <details>
        <summary>Catalog <span class="ep-count">3</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/catalog/categories.list.get — all categories</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/catalog/elements.list.get — elements by category</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/catalog/element.spec.get — full spec + JSON Schema</span></div>
        </div>
      </details>

      <details>
        <summary>Templates <span class="ep-count">11</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/templates/templates.list — browse catalog</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/templates/templates.search — full-text search</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/templates/templates.count</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/templates/template.get — full template</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/templates/template.summary.get</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/templates/template.create</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/templates/template.delete</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/templates/template.schema.get — input JSON Schema</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/templates/template.input.validate</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/templates/template.instantiate — preview (no save)</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/templates/template.materialize — create blueprint + resources</span></div>
        </div>
      </details>

      <details>
        <summary>Shares <span class="ep-count">7</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/shares/share.create — create invitation</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/shares/share.accept — accept + clone</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/shares/share.decline</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/shares/share.to_team — direct team share</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/shares/share.cancel</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/shares/shares.list — sent/received invites</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/shares/share.get — single invite</span></div>
        </div>
      </details>

      <details>
        <summary>Collaboration — Presence <span class="ep-count">9</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/session.join</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/session.leave</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/session.heartbeat</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/collaboration/session.participants</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/collaboration/team.sessions</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/collaboration/user.active_sessions</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/session.typing — set indicator</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/collaboration/session.typing — get typing users</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/collaboration/health — Redis availability</span></div>
        </div>
      </details>

      <details>
        <summary>Collaboration — Edit Locks <span class="ep-count">5</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/edit_lock.acquire</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/edit_lock.release</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/edit_lock.heartbeat — renew</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/collaboration/edit_lock.status</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/edit_lock.statuses — batch</span></div>
        </div>
      </details>

      <details>
        <summary>Graph Validation <span class="ep-count">7</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/graph/validation/names.get — validator names</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/graph/validation/all.validate — full topology</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/graph/validation/channels.validate</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/graph/validation/dependencies.validate</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/graph/validation/cycles.validate</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/graph/validation/orphans.validate</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/graph/validation/required_nodes.validate</span></div>
        </div>
      </details>

      <details>
        <summary>Actions, Stats, Credentials, Health, Workspace <span class="ep-count">11</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/actions/actions.list — list available actions</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/actions/action.execute — sync execution</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/statistics/stats.get — user dashboard</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/statistics/stats.system.get — admin analytics</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/credentials/exchange — OAuth code exchange</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/credentials/status — credential health</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/credentials/client-config.save — OAuth client config</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/credentials/client-config.get</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/workspace/workspace.cleanup — purge identity data</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/health/ — liveness</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/health/version</span></div>
        </div>
      </details>

      <h3>Streaming Protocol</h3>
      <p>When <code>stream: true</code> or via <code>session.subscribe</code>, the response is <code>application/x-ndjson</code> — newline-delimited JSON events with heartbeats. Event types include <code>llm_token</code>, <code>tool_calling</code>, <code>node_start</code>, <code>node_complete</code>, <code>session_complete</code>.</p>
    `,
    architecture: `
      <h3>Design Pattern: Hexagonal Architecture</h3>
      <p>MAS uses <strong>ports and adapters</strong> (hexagonal architecture). Domain logic lives in <code>lib/mas/</code> with zero infrastructure imports. Technology adapters in <code>adapters/</code> implement the port interfaces. The composition root <code>bootstrap/container.py</code> wires everything at startup.</p>

      <h3>Directory Layout</h3>
      <ul>
        <li><strong><code>lib/mas/</code></strong> — The hexagon: 17 domain cores. ~200 Python files across blueprints, sessions, graph engine, elements, catalog, IEM, auth, collaboration, sharing, templates, validation, statistics, actions.</li>
        <li><strong><code>adapters/inbound/</code></strong> — Flask HTTP endpoints + Temporal worker (workflows + activities).</li>
        <li><strong><code>adapters/outbound/</code></strong> — MongoDB repos (7), Redis (streams, collab, auth state), LangGraph compiler, Temporal submitter, Identity HTTP, OAuth2.</li>
        <li><strong><code>bootstrap/</code></strong> — <code>container.py</code> (AppContainer singleton) + <code>cli.py</code> (Typer CLI).</li>
      </ul>

      <h3>All 17 Hexagonal Domain Cores</h3>
      <details>
        <summary>core/identity — Identity & Team Membership <span class="ep-count">port</span></summary>
        <div class="endpoint-list">
          <p><code>IdentityProvider</code> port: <code>is_member</code>, <code>get_team_ids</code>, <code>resolve_team_id</code>. Almost every entity carries an Identity. Adapters: IdentityPodProvider (HTTP), DevIdentityProvider, NoOpIdentityProvider.</p>
        </div>
      </details>
      <details>
        <summary>core/auth — Authentication & Credentials <span class="ep-count">5 ports</span></summary>
        <div class="endpoint-list">
          <p>Ports: <code>AuthStrategy</code>, <code>CredentialStore</code>, <code>ServerConfigStore</code>, <code>HttpClient</code>, <code>FlowStateStore</code>. Service: <code>AuthService</code> — OAuth2/PKCE/DCR, token refresh, API key. Elements depend on <code>AuthCredential</code> protocol, not OAuth specifics.</p>
        </div>
      </details>
      <details>
        <summary>core/channels — Event Streaming <span class="ep-count">port</span></summary>
        <div class="endpoint-list">
          <p><code>ChannelFactory</code> / <code>SessionChannel</code> ports. Decouples producers (nodes) from consumers (HTTP subscribers). Adapters: <code>RedisChannelFactory</code> (Redis Streams) or <code>LocalChannelFactory</code> (in-process). This is how the same code runs locally or at scale.</p>
        </div>
      </details>
      <details>
        <summary>core/iem — Inter-Element Messaging <span class="ep-count">port</span></summary>
        <div class="endpoint-list">
          <p><code>InterMessenger</code>: send_packet, inbox, process, acknowledge. Packets stored in <code>GraphState.inter_packets</code>. Types: <code>TaskPacket</code> (dominant), <code>SystemPacket</code>, <code>DebugPacket</code>. Adjacency-enforced. Enables orchestrator ↔ agent loops via <code>RouterDirectCondition</code>.</p>
        </div>
      </details>
      <details>
        <summary>core/ref — Reference Resolution <span class="ep-count">models</span></summary>
        <div class="endpoint-list">
          <p><code>Ref</code> hierarchy: NodeRef, LLMRef, ToolRef, ProviderRef, RetrieverRef, ConditionRef. <code>RefWalker</code> resolves <code>$ref:resource_id</code> during Draft → Spec transformation.</p>
        </div>
      </details>
      <details>
        <summary>blueprints — Workflow Definitions <span class="ep-count">port + svc</span></summary>
        <div class="endpoint-list">
          <p>Port: <code>BlueprintRepository</code>. Service: <code>BlueprintService</code> — save_draft, load_resolved, validate. Models: <code>BlueprintDraft</code> ($ref) → <code>BlueprintSpec</code> (resolved) → <code>GraphPlan</code>. Central to the build and execution lifecycle.</p>
        </div>
      </details>
      <details>
        <summary>resources — Agent Inventory <span class="ep-count">port + svc</span></summary>
        <div class="endpoint-list">
          <p>Port: <code>ResourceRepository</code>. Service: <code>ResourcesService</code> — CRUD with schema validation, dependency resolution, auth credential cleanup. Delete-guarded: cannot remove resources in use by blueprints.</p>
        </div>
      </details>
      <details>
        <summary>session — Session Lifecycle <span class="ep-count">2 ports + svc</span></summary>
        <div class="endpoint-list">
          <p>Ports: <code>SessionRepository</code>, <code>BackgroundSessionEngine</code>. Service: <code>SessionService</code> — create, submit (bg, default), run (fg, fallback), cancel. Two-phase: <code>SessionInputProjector</code> stages inputs, then <code>BackgroundSessionEngine</code> (default) or <code>ForegroundSessionRunner</code> (fallback) executes. Status: PENDING → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED.</p>
        </div>
      </details>
      <details>
        <summary>engine — Graph Execution <span class="ep-count">2 ports</span></summary>
        <div class="endpoint-list">
          <p>Ports: <code>BaseGraphBuilder</code>, <code>BaseGraphExecutor</code>. Shared BSP/Pregel algorithm (<code>GraphTraversal</code>): PLAN → EXECUTE (parallel) → UPDATE (channel merge). Two backends: Temporal (distributed, stateless workers — default) and LangGraph (in-process — fallback).</p>
        </div>
      </details>
      <details>
        <summary>graph — Construction & Validation <span class="ep-count">2 svcs</span></summary>
        <div class="endpoint-list">
          <p><code>GraphService</code> — build_plan from BlueprintSpec. <code>GraphValidationService</code> — topology validators: dependencies, cycles, orphans, channels, required_nodes. Plugin-based with <code>FixSuggestionProvider</code>.</p>
        </div>
      </details>
      <details>
        <summary>catalog / elements — Plugin Architecture <span class="ep-count">registry</span></summary>
        <div class="endpoint-list">
          <p><code>ElementRegistry</code> — in-process singleton, auto-populated via <code>SpecDiscoverer</code>. Each element type is its own mini-domain. <code>BaseElementSpec</code> declares category, type_key, config_schema, factory_cls. <code>CatalogService</code> provides read API.</p>
        </div>
      </details>
      <details>
        <summary>collaboration — Multi-User Coordination <span class="ep-count">port + svc</span></summary>
        <div class="endpoint-list">
          <p>Port: <code>CollaborationStore</code>. Service: <code>CollaborationService</code> — join/leave session, heartbeat, typing, edit locks. Redis keys: <code>mas:collab:session:{id}:*</code>, <code>mas:collab:editlock:*</code>. TTL-based presence.</p>
        </div>
      </details>
      <details>
        <summary>sharing — Cross-Identity Sharing <span class="ep-count">port + svc</span></summary>
        <div class="endpoint-list">
          <p>Port: <code>ShareRepository</code>. Service: <code>ShareService</code> — create/accept/decline invites, share_to_team. <code>ShareCloner</code> deep-copies with RID remapping. TTL auto-expiry via MongoDB index.</p>
        </div>
      </details>
      <details>
        <summary>templates — Blueprint Factories <span class="ep-count">port + svc</span></summary>
        <div class="endpoint-list">
          <p>Port: <code>TemplateRepository</code>. Service: <code>TemplateService</code> — create, instantiate (preview), materialize (saves blueprint + resources). Placeholder substitution engine. Text search index for catalog browsing.</p>
        </div>
      </details>
      <details>
        <summary>validation — Element Config Validation <span class="ep-count">svc</span></summary>
        <div class="endpoint-list">
          <p><code>ElementValidationService</code> — validates element configs (connectivity, credentials, deps) via per-spec <code>ElementValidator</code> plugins from registry. <strong>Separate from</strong> graph topology validation.</p>
        </div>
      </details>
      <details>
        <summary>statistics — Dashboard Aggregation <span class="ep-count">svc</span></summary>
        <div class="endpoint-list">
          <p><code>StatisticsService</code> — facade over BlueprintService, SessionService, ResourcesService. User scope + admin system-wide analytics. No own persistence.</p>
        </div>
      </details>
      <details>
        <summary>actions — Discoverable Operations <span class="ep-count">port + svc</span></summary>
        <div class="endpoint-list">
          <p>Port: <code>BaseAction</code>. Service: <code>ActionsService</code> — auto_discover, execute_action_sync. Registered: AuthenticateAction, ValidateConnectionAction, GetToolsNamesAction (MCP). Linked by (category, type).</p>
        </div>
      </details>

      <h3>Port → Adapter Wiring</h3>
      <table class="info-table">
        <tr><th>Port</th><th>Adapter</th><th>Tech</th></tr>
        <tr><td><code>BlueprintRepository</code></td><td>MongoBlueprintRepository</td><td>MongoDB</td></tr>
        <tr><td><code>ResourceRepository</code></td><td>MongoResourceRepository</td><td>MongoDB</td></tr>
        <tr><td><code>SessionRepository</code></td><td>MongoSessionRepository</td><td>MongoDB</td></tr>
        <tr><td><code>ShareRepository</code></td><td>MongoShareRepository</td><td>MongoDB</td></tr>
        <tr><td><code>TemplateRepository</code></td><td>MongoTemplateRepository</td><td>MongoDB</td></tr>
        <tr><td><code>CredentialStore</code></td><td>MongoCredentialStore</td><td>MongoDB + Fernet</td></tr>
        <tr><td><code>ServerConfigStore</code></td><td>MongoServerConfigStore</td><td>MongoDB</td></tr>
        <tr><td><code>FlowStateStore</code></td><td>RedisFlowStateStore</td><td>Redis</td></tr>
        <tr><td><code>ChannelFactory</code></td><td>Redis / LocalChannelFactory</td><td>Redis Streams / in-proc</td></tr>
        <tr><td><code>CollaborationStore</code></td><td>RedisCollaborationStore</td><td>Redis</td></tr>
        <tr><td><code>BackgroundSessionEngine</code></td><td>TemporalSessionEngine</td><td>Temporal</td></tr>
        <tr><td><code>IdentityProvider</code></td><td>IdentityPodProvider / Dev</td><td>HTTP / in-proc</td></tr>
        <tr><td><code>AuthStrategy</code></td><td>OAuth2Strategy / ApiKeyStrategy</td><td>httpx / in-proc</td></tr>
        <tr><td><code>BaseGraphBuilder</code></td><td>TemporalBuilder (default) / LangGraph (fallback)</td><td>Temporal / LangGraph</td></tr>
        <tr><td><code>HttpClient</code></td><td>HttpxAuthClient</td><td>httpx</td></tr>
      </table>

      <h3>MongoDB Collections (7)</h3>
      <table class="info-table">
        <tr><th>Collection</th><th>Key Fields</th><th>Notable</th></tr>
        <tr><td>blueprints</td><td>blueprint_id, identity, spec_dict, rid_refs</td><td>Unique on blueprint_id</td></tr>
        <tr><td>workflow_sessions</td><td>run_id, identity, blueprint_id, graph_state, status</td><td>Unique on run_id; compound identity+time index</td></tr>
        <tr><td>resources</td><td>rid, identity, category, type, name, cfg_dict</td><td>Unique on identity+category+type+name</td></tr>
        <tr><td>shares</td><td>share_id, sender/recipient_identity, status</td><td>TTL auto-expiry on expires_at</td></tr>
        <tr><td>templates</td><td>template_id, draft, placeholders, metadata</td><td>Text search on name+description</td></tr>
        <tr><td>credentials</td><td>user_id, server_identifier, tokens (encrypted)</td><td>Fernet-encrypted access/refresh tokens</td></tr>
        <tr><td>server_configs</td><td>server_identifier, client_id/secret, endpoints</td><td>OAuth client configurations</td></tr>
      </table>

      <h3>Two Validation Domains</h3>
      <p><strong>Element validation</strong> (<code>ElementValidationService</code>) checks individual resource configs — connectivity, credentials, dependency health. <strong>Graph validation</strong> (<code>GraphValidationService</code>) checks topology — cycles, orphans, missing channels, required start/end nodes. They run at different lifecycle stages and are a common source of confusion for new developers.</p>

      <h3>Blueprint Transformation Pipeline</h3>
      <p><code>BlueprintDraft</code> ($ref) → <code>RefWalker</code> → <code>BlueprintSpec</code> (resolved) → <code>GraphService.build_plan()</code> → <code>GraphPlan</code> → <code>SessionElementBuilder</code> (factories) → <code>RTGraphPlan</code> (bound callables) → <code>GraphBuilderFactory</code> → LangGraph or Temporal graph.</p>

      <h3>Key Configuration (AppConfig)</h3>
      <table class="info-table">
        <tr><th>Setting</th><th>Default</th><th>Purpose</th></tr>
        <tr><td><code>engine_name</code></td><td>temporal</td><td>Graph engine: temporal or langgraph</td></tr>
        <tr><td><code>temporal_task_queue</code></td><td>graph-engine</td><td>Temporal worker queue name</td></tr>
        <tr><td><code>redis_stream_ttl</code></td><td>3600</td><td>Redis stream TTL (seconds)</td></tr>
        <tr><td><code>identity_provider_mode</code></td><td>(auto)</td><td>pod / dev / noop</td></tr>
        <tr><td><code>credential_encryption_key</code></td><td>(empty)</td><td>Fernet key for token encryption</td></tr>
        <tr><td><code>collaboration_presence_ttl</code></td><td>300</td><td>Presence key TTL (seconds)</td></tr>
        <tr><td><code>collaboration_edit_lock_ttl_sec</code></td><td>180</td><td>Edit lock TTL (seconds)</td></tr>
      </table>

      <h3>Graceful Degradation</h3>
      <p>Redis, Temporal, and Identity degrade gracefully if unavailable. Without Temporal: falls back to foreground-only execution via LangGraph (no <code>submit()</code>). Without Redis: in-process channels only, no collaboration, no stream subscriptions. Without Identity pod: DevIdentityProvider (all team checks pass). The service remains functional in a minimal <strong>Mongo-only</strong> configuration, but the recommended production stack includes Temporal + Redis.</p>
    `,
    _ports: [
    { name: 'ResourcesService', role: 'CRUD with schema validation, dependency resolution, auth credential cleanup. Delete-guarded: cannot remove resources in use by blueprints.' },
    { name: 'TemplateService', role: 'create, instantiate (preview), materialize (saves blueprint + resources). Placeholder substitution engine. Text search index for catalog browsing.' },
    { name: 'StatisticsService', role: 'facade over BlueprintService, SessionService, ResourcesService. User scope + admin system-wide analytics. No own persistence.' },
    { name: 'ActionsService', role: 'auto_discover, execute_action_sync. Registered: AuthenticateAction, ValidateConnectionAction, GetToolsNamesAction (MCP). Linked by (category, type).' },
  ],
  _endpoints: [
    { method: 'POST', path: '/sessions/user.session.create', summary: 'create session record', group: 'Sessions' },
    { method: 'POST', path: '/sessions/user.session.submit', summary: 'execute via Temporal (default, 202)', group: 'Sessions' },
    { method: 'POST', path: '/sessions/user.session.execute', summary: 'foreground fallback, sync or NDJSON stream', group: 'Sessions' },
    { method: 'POST', path: '/sessions/session.cancel', summary: 'cancel Temporal workflow', group: 'Sessions' },
    { method: 'GET', path: '/sessions/session.state.get', summary: 'full GraphState', group: 'Sessions' },
    { method: 'GET', path: '/sessions/session.chat.get', summary: 'messages + output + status', group: 'Sessions' },
    { method: 'GET', path: '/sessions/session.status.get', summary: 'status enum', group: 'Sessions' },
    { method: 'GET', path: '/sessions/session.user.list', summary: 'all sessions for identity', group: 'Sessions' },
    { method: 'GET', path: '/sessions/session.user.blueprints.get', summary: 'blueprint IDs in use', group: 'Sessions' },
    { method: 'GET', path: '/sessions/session.subscribe', summary: 'late-join NDJSON stream', group: 'Sessions' },
    { method: 'GET', path: '/sessions/session.stream.status', summary: 'Redis stream metadata', group: 'Sessions' },
    { method: 'GET', path: '/sessions/session.stream.active', summary: 'list active streams', group: 'Sessions' },
    { method: 'GET', path: '/sessions/session.meta', summary: 'get session metadata', group: 'Sessions' },
    { method: 'POST', path: '/sessions/session.meta', summary: 'update metadata + typing sync', group: 'Sessions' },
    { method: 'DEL', path: '/sessions/session.delete', group: 'Sessions' },
    { method: 'POST', path: '/blueprints/blueprint.save', summary: 'save new draft', group: 'Blueprints' },
    { method: 'PUT', path: '/blueprints/blueprint.update', summary: 'update existing', group: 'Blueprints' },
    { method: 'GET', path: '/blueprints/available.blueprints.get', summary: 'full docs for workspace', group: 'Blueprints' },
    { method: 'GET', path: '/blueprints/available.blueprints.summary.get', summary: 'lightweight list', group: 'Blueprints' },
    { method: 'GET', path: '/blueprints/available.blueprints.resolved.get', summary: '$ref resolved', group: 'Blueprints' },
    { method: 'GET', path: '/blueprints/blueprint.info.get', summary: 'single doc by ID', group: 'Blueprints' },
    { method: 'GET', path: '/blueprints/blueprint.draft.schema.get', summary: 'JSON Schema', group: 'Blueprints' },
    { method: 'DEL', path: '/blueprints/remove.blueprint', group: 'Blueprints' },
    { method: 'PUT', path: '/blueprints/blueprint.metadata.set', group: 'Blueprints' },
    { method: 'POST', path: '/blueprints/blueprint.validate', summary: 'validate all elements', group: 'Blueprints' },
    { method: 'POST', path: '/blueprints/draft.validate', summary: 'validate before saving', group: 'Blueprints' },
    { method: 'POST', path: '/resources/resource.save', summary: 'create resource', group: 'Resources' },
    { method: 'GET', path: '/resources/resource.get', summary: 'single by ID', group: 'Resources' },
    { method: 'GET', path: '/resources/resources.list', summary: 'filtered + paginated', group: 'Resources' },
    { method: 'PUT', path: '/resources/resource.update', summary: 'update config/name', group: 'Resources' },
    { method: 'DEL', path: '/resources/resource.delete', summary: 'fails if in use', group: 'Resources' },
    { method: 'POST', path: '/resources/resource.validate', summary: 'validate + deps', group: 'Resources' },
    { method: 'POST', path: '/resources/resources.validate', summary: 'parallel batch', group: 'Resources' },
    { method: 'GET', path: '/resources/resource.card', summary: 'element card', group: 'Resources' },
    { method: 'POST', path: '/resources/resources.cards', summary: 'batch cards', group: 'Resources' },
    { method: 'POST', path: '/resources/config.validate', summary: 'pre-save validation', group: 'Resources' },
    { method: 'GET', path: '/resources/resource.schema', summary: 'JSON Schema', group: 'Resources' },
    { method: 'GET', path: '/catalog/categories.list.get', summary: 'all categories', group: 'Catalog' },
    { method: 'GET', path: '/catalog/elements.list.get', summary: 'elements by category', group: 'Catalog' },
    { method: 'GET', path: '/catalog/element.spec.get', summary: 'full spec + JSON Schema', group: 'Catalog' },
    { method: 'GET', path: '/templates/templates.list', summary: 'browse catalog', group: 'Templates' },
    { method: 'GET', path: '/templates/templates.search', summary: 'full-text search', group: 'Templates' },
    { method: 'GET', path: '/templates/templates.count', group: 'Templates' },
    { method: 'GET', path: '/templates/template.get', summary: 'full template', group: 'Templates' },
    { method: 'GET', path: '/templates/template.summary.get', group: 'Templates' },
    { method: 'POST', path: '/templates/template.create', group: 'Templates' },
    { method: 'DEL', path: '/templates/template.delete', group: 'Templates' },
    { method: 'GET', path: '/templates/template.schema.get', summary: 'input JSON Schema', group: 'Templates' },
    { method: 'POST', path: '/templates/template.input.validate', group: 'Templates' },
    { method: 'POST', path: '/templates/template.instantiate', summary: 'preview (no save)', group: 'Templates' },
    { method: 'POST', path: '/templates/template.materialize', summary: 'create blueprint + resources', group: 'Templates' },
    { method: 'POST', path: '/shares/share.create', summary: 'create invitation', group: 'Shares' },
    { method: 'POST', path: '/shares/share.accept', summary: 'accept + clone', group: 'Shares' },
    { method: 'POST', path: '/shares/share.decline', group: 'Shares' },
    { method: 'POST', path: '/shares/share.to_team', summary: 'direct team share', group: 'Shares' },
    { method: 'POST', path: '/shares/share.cancel', group: 'Shares' },
    { method: 'GET', path: '/shares/shares.list', summary: 'sent/received invites', group: 'Shares' },
    { method: 'GET', path: '/shares/share.get', summary: 'single invite', group: 'Shares' },
    { method: 'POST', path: '/collaboration/session.join', group: 'Collaboration — Presence' },
    { method: 'POST', path: '/collaboration/session.leave', group: 'Collaboration — Presence' },
    { method: 'POST', path: '/collaboration/session.heartbeat', group: 'Collaboration — Presence' },
    { method: 'GET', path: '/collaboration/session.participants', group: 'Collaboration — Presence' },
    { method: 'GET', path: '/collaboration/team.sessions', group: 'Collaboration — Presence' },
    { method: 'GET', path: '/collaboration/user.active_sessions', group: 'Collaboration — Presence' },
    { method: 'POST', path: '/collaboration/session.typing', summary: 'set indicator', group: 'Collaboration — Presence' },
    { method: 'GET', path: '/collaboration/session.typing', summary: 'get typing users', group: 'Collaboration — Presence' },
    { method: 'GET', path: '/collaboration/health', summary: 'Redis availability', group: 'Collaboration — Presence' },
    { method: 'POST', path: '/collaboration/edit_lock.acquire', group: 'Collaboration — Edit Locks' },
    { method: 'POST', path: '/collaboration/edit_lock.release', group: 'Collaboration — Edit Locks' },
    { method: 'POST', path: '/collaboration/edit_lock.heartbeat', summary: 'renew', group: 'Collaboration — Edit Locks' },
    { method: 'GET', path: '/collaboration/edit_lock.status', group: 'Collaboration — Edit Locks' },
    { method: 'POST', path: '/collaboration/edit_lock.statuses', summary: 'batch', group: 'Collaboration — Edit Locks' },
    { method: 'GET', path: '/graph/validation/names.get', summary: 'validator names', group: 'Graph Validation' },
    { method: 'POST', path: '/graph/validation/all.validate', summary: 'full topology', group: 'Graph Validation' },
    { method: 'POST', path: '/graph/validation/channels.validate', group: 'Graph Validation' },
    { method: 'POST', path: '/graph/validation/dependencies.validate', group: 'Graph Validation' },
    { method: 'POST', path: '/graph/validation/cycles.validate', group: 'Graph Validation' },
    { method: 'POST', path: '/graph/validation/orphans.validate', group: 'Graph Validation' },
    { method: 'POST', path: '/graph/validation/required_nodes.validate', group: 'Graph Validation' },
    { method: 'GET', path: '/actions/actions.list', summary: 'list available actions', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'POST', path: '/actions/action.execute', summary: 'sync execution', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'GET', path: '/statistics/stats.get', summary: 'user dashboard', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'GET', path: '/statistics/stats.system.get', summary: 'admin analytics', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'POST', path: '/credentials/exchange', summary: 'OAuth code exchange', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'GET', path: '/credentials/status', summary: 'credential health', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'POST', path: '/credentials/client-config.save', summary: 'OAuth client config', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'GET', path: '/credentials/client-config.get', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'DEL', path: '/workspace/workspace.cleanup', summary: 'purge identity data', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'GET', path: '/health/', summary: 'liveness', group: 'Actions, Stats, Credentials, Health, Workspace' },
    { method: 'GET', path: '/health/version', group: 'Actions, Stats, Credentials, Health, Workspace' },
  ],
  scheme: {
      nodes: [
        { id: 'identity', label: 'Identity', x: 20, y: 8, w: 100, h: 32, color: '#BB86FC' },
        { id: 'ui', label: 'UI /api2', x: 20, y: 100, w: 100, h: 32, color: '#BB86FC' },
        { id: 'mas', label: 'Multi Agent System (MAS)', x: 200, y: 95, w: 120, h: 38, color: '#BB86FC' },
        { id: 'mongo', label: 'MongoDB', x: 415, y: 8, w: 100, h: 32, color: '#86EFAC' },
        { id: 'redis', label: 'Redis', x: 415, y: 56, w: 100, h: 32, color: '#86EFAC' },
        { id: 'temporal', label: 'Temporal', x: 415, y: 104, w: 100, h: 32, color: '#86EFAC' },
        { id: 'rag', label: 'RAG', x: 415, y: 152, w: 100, h: 32, color: '#BB86FC' },
        { id: 'llm', label: 'LLM APIs', x: 415, y: 200, w: 100, h: 32, color: '#FBBF24' },
        { id: 'a2a', label: 'A2A Agents', x: 200, y: 200, w: 110, h: 32, color: '#FBBF24' },
        { id: 'mcp', label: 'MCP Servers', x: 20, y: 200, w: 115, h: 32, color: '#FBBF24' },
      ],
      edges: [
        { from: 'ui', to: 'mas', label: 'HTTP/NDJSON' },
        { from: 'mas', to: 'mongo', label: 'read/write' },
        { from: 'mas', to: 'redis', label: 'streams + collab' },
        { from: 'mas', to: 'temporal', label: 'submit' },
        { from: 'mas', to: 'rag', label: 'query.match' },
        { from: 'mas', to: 'llm', label: 'completions' },
        { from: 'mas', to: 'a2a', label: 'A2A protocol' },
        { from: 'mas', to: 'mcp', label: 'MCP tools' },
        { from: 'mas', to: 'identity', label: 'team auth' },
      ],
    },
  },
};
