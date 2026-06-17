SERVICES.ui = {
  id: 'ui',
  name: 'UI / Nginx',
  icon: '🖥️',
  role: 'React SPA + reverse proxy',
  type: 'APP',
  x: 700, y: 190,
  w: 190, h: 60,
  detail: {
    subtitle: 'React 18 + TypeScript + Vite • Nginx reverse proxy',
    modal: {
      job: `
        <p>The <strong>UI</strong> is the single entry point for all browser traffic — a React SPA with Nginx reverse proxy.</p>
        <h3>Path Routing</h3>
        <ul>
          <li><code>/api1/*</code> → RAG</li>
          <li><code>/api2/*</code> → Multi Agent System (MAS)</li>
          <li><code>/api3/*</code> → Identity (307)</li>
          <li><code>/api4/*</code> → Platform Backend</li>
        </ul>
        <h3>Streaming</h3>
        <p>Streaming endpoints get 600s timeout and <code>proxy_buffering off</code>.</p>
      `,
      interfaces: `
        <h3>Axios Clients</h3>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">queryClient — /api1 (RAG)</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">axiosAgentConfig — /api2 (MAS)</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">authClient — /api3 (Identity)</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">backendClient — /api4 (Platform)</span></div>
        </div>
        <h3>Nginx Locations</h3>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">PROXY</span><span class="path">/api1/ → RAG</span></div>
          <div class="endpoint"><span class="method get">PROXY</span><span class="path">/api2/ → MAS</span></div>
          <div class="endpoint"><span class="method post">307</span><span class="path">/api3/ → Identity</span></div>
          <div class="endpoint"><span class="method get">PROXY</span><span class="path">/api4/ → Platform</span></div>
        </div>
      `,
      architecture: `
        <h3>Tech Stack</h3>
        <ul>
          <li>React 18 + TypeScript + Vite</li>
          <li>Tailwind CSS + Radix UI (shadcn)</li>
          <li>TanStack Query, Wouter, JointJS</li>
        </ul>
        <h3>Key Directories</h3>
        <ul>
          <li><code>components/ui/</code> — 51 shadcn primitives</li>
          <li><code>http/</code> — 4 axios clients</li>
          <li><code>contexts/</code> — 8 app providers</li>
        </ul>
      `,
    },
    job: `
      <p>The <strong>UI</strong> is the single entry point for all browser traffic. It's a React 18 SPA (~280 TypeScript files) that provides the blueprint builder, real-time agent chat, RAG dashboard, team collaboration, template catalog, and admin configuration panel.</p>
      <p>In production, <strong>Nginx</strong> serves static assets and reverse-proxies API requests to 4 backend services based on URL path prefix.</p>

      <h3>Key Features</h3>
      <ul>
        <li><strong>Visual Graph Builder</strong> — JointJS canvas for building agent workflows with drag-and-drop nodes, edges, and conditions. YAML-backed, with dagre auto-layout on load.</li>
        <li><strong>Real-Time Agent Chat</strong> — NDJSON streaming from MAS via Redis Streams. Live graph node status overlays. Multi-session hub.</li>
        <li><strong>Team Collaboration</strong> — Shared workspaces with real-time presence, typing indicators, edit locks, and session busy-state.</li>
        <li><strong>RAG Dashboard</strong> — Document upload, Slack channel management, pipeline monitoring, chunk analytics.</li>
        <li><strong>Template Marketplace</strong> — Browse, preview, and materialize parameterized blueprint templates into ready-to-use workflows.</li>
        <li><strong>Sharing System</strong> — Share blueprints and resources between users/teams with invitation-based cloning and notification panel.</li>
        <li><strong>Agent Inventory</strong> — CRUD for all resource types (LLMs, tools, providers, retrievers, conditions, nodes, auths) with schema-driven dynamic forms.</li>
        <li><strong>Admin Config</strong> — Template-driven admin settings page (admin gated via Platform Backend).</li>
      </ul>

      <h3>Nginx Path Routing</h3>
      <ul>
        <li><code>/api1/*</code> → RAG (port 13457)</li>
        <li><code>/api2/*</code> → Multi Agent System (MAS) (port 8002) — streaming endpoints get 600s timeout + <code>proxy_buffering off</code></li>
        <li><code>/api3/*</code> → Identity (307 redirect to external host)</li>
        <li><code>/api4/*</code> → Platform Backend (port 8005)</li>
      </ul>

      <h3>Application Routes (15+)</h3>
      <ul>
        <li><strong>Agentic Routes</strong> (AgenticLayout + team gating):
          <ul>
            <li><code>/agentic-overview</code> — dashboard: stats, workflow list, resource charts</li>
            <li><code>/agentic-ai</code> — graph builder + execution preview</li>
            <li><code>/inventory</code> — resource CRUD (workspace elements)</li>
            <li><code>/agentic-chats</code> — personal ExecutionTab or team CollaborationHubView</li>
            <li><code>/templates</code> — template catalog → materialize → session</li>
          </ul>
        </li>
        <li><strong>RAG Routes</strong>:
          <ul>
            <li><code>/rag-overview</code> — RAG dashboard with pipeline polling</li>
            <li><code>/documents</code> — document upload/embed pipeline</li>
            <li><code>/slack</code> + <code>/slack/add-source</code> — Slack channel management</li>
          </ul>
        </li>
        <li><strong>Other</strong>: <code>/</code> (Get to Know), <code>/login</code>, <code>/configuration</code> (admin), <code>/analytics</code> (system stats), <code>/guides</code>, <code>/jira</code></li>
        <li><strong>Public</strong>: <code>/chat/:token</code> — public blueprint chat (no auth required)</li>
      </ul>

      <h3>Session Streaming Architecture</h3>
      <ul>
        <li><strong>1.</strong> <code>POST /sessions/user.session.submit</code> → 202 with workflow ID</li>
        <li><strong>2.</strong> <code>fetch(/api2/sessions/session.subscribe)</code> → NDJSON stream via <code>ReadableStream</code></li>
        <li><strong>3.</strong> <code>useSessionStream</code> hook parses line-delimited JSON with reconnect logic</li>
        <li><strong>4.</strong> <code>StreamingDataContext</code> holds <code>Map&lt;nodeId, NodeEntry&gt;</code> for live graph overlays</li>
        <li><strong>5.</strong> <code>ChatInterface</code> renders LLM tokens, tool calls, node transitions in real-time</li>
      </ul>

      <h3>Workspace Identity Pattern</h3>
      <p><code>useWorkspaceIdentity()</code> is the single source of truth for <code>userId</code>, <code>identityType</code> (user vs team), and <code>displayName</code>. It feeds API params for every identity-scoped call. Backed by <code>AuthContext</code> (session) + <code>ViewContext</code> (team switching).</p>

      <h3>Graph Builder</h3>
      <p>Built on <strong>JointJS</strong> (<code>@joint/core</code> + <code>@joint/layout-directed-graph</code> + dagre). Two modes:</p>
      <ul>
        <li><strong>Creation</strong> (<code>useGraphCreationLogic</code> + <code>useGraphCreationCanvas</code>) — canvas editing, YAML serialization via <code>js-yaml</code>, draft validation, save/update blueprint.</li>
        <li><strong>Display</strong> (<code>useGraphDisplay</code>) — read-only graph with live status overlays from StreamingDataContext.</li>
      </ul>
      <p>Team mode adds <strong>edit locks</strong> — only one user can edit a blueprint at a time.</p>
    `,
    interfaces: `
      <p>The UI communicates with 4 backend services via typed API modules in <code>api/</code>. 19 API files, 60+ unique endpoints.</p>

      <details>
        <summary>Sessions — /api2 <span class="ep-count">8</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/user.session.create</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/user.session.submit — trigger execution</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/session.cancel</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.stream.status</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.subscribe — NDJSON stream (raw fetch)</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.user.list</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.chat.get</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/sessions/session.delete</span></div>
        </div>
      </details>

      <details>
        <summary>Blueprints — /api2 <span class="ep-count">10</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/available.blueprints.get</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/available.blueprints.summary.get</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/available.blueprints.resolved.get</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/blueprint.info.get</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/blueprints/blueprint.save</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/blueprints/blueprint.update</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/blueprints/blueprint.metadata.set</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/blueprints/blueprint.validate</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/blueprints/draft.validate</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/blueprints/remove.blueprint</span></div>
        </div>
      </details>

      <details>
        <summary>Resources & Catalog — /api2 <span class="ep-count">8</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/resources/resources.list — filtered by category</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/resources/resource.save</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/resources/resource.update</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/resources/resource.delete</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/resources/resource.validate</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/catalog/elements.list.get</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/catalog/categories.list.get</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/actions/action.execute</span></div>
        </div>
      </details>

      <details>
        <summary>Templates — /api2 <span class="ep-count">5</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/templates/templates.list</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/templates/template.get</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/templates/template.schema.get</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/templates/template.input.validate</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/templates/template.materialize</span></div>
        </div>
      </details>

      <details>
        <summary>Shares & Collaboration — /api2 <span class="ep-count">11</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/shares/share.create</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/shares/shares.list</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/shares/share.accept / share.decline / share.to_team</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/session.join / session.leave / session.heartbeat</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/collaboration/session.participants</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/session.typing</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/edit_lock.acquire / release / heartbeat</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/edit_lock.statuses — batch status check</span></div>
        </div>
      </details>

      <details>
        <summary>Statistics — /api2 <span class="ep-count">3</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/statistics/stats.get — user dashboard</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/statistics/stats.system.get — admin analytics</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.user.blueprints.get</span></div>
        </div>
      </details>

      <details>
        <summary>Graph Validation — /api2 <span class="ep-count">1</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/graph/validation/all.validate — full topology check</span></div>
        </div>
      </details>

      <details>
        <summary>Auth & Teams — /api3 <span class="ep-count">8</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/auth/user — current session user</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/auth/user/groups — LDAP groups</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/auth/logout</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/auth/refresh</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/teams/team.create</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/teams/teams.list / team.get</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/teams/team.update</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/teams/team.delete + /workspace/workspace.cleanup</span></div>
        </div>
      </details>

      <details>
        <summary>Directory — /api3 <span class="ep-count">4</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/directory/directory.status</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/directory/directory.search_users</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/directory/directory.search — users + groups</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/directory/directory.get_group</span></div>
        </div>
      </details>

      <details>
        <summary>RAG — /api1 <span class="ep-count">10</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/data_sources/data.sources.get</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/data_sources/data.source.details.get</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/docs/upload — multipart file upload</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/docs/validate</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/pipelines/embed</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/data_sources/data.source.delete</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/docs/supported-extensions</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/slack/available.slack.channels.get</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/vector/chunks.counts</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/health/service.readiness.get</span></div>
        </div>
      </details>

      <details>
        <summary>Admin Config — /api4 <span class="ep-count">3</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/admin_config/config.get</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/admin_config/config.section.update</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/admin_config/access.check</span></div>
        </div>
      </details>

      <h3>Nginx Proxy Locations</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">PROXY</span><span class="path">/api1/ → RAG_IP:RAG_PORT/api/</span></div>
        <div class="endpoint"><span class="method get">PROXY</span><span class="path">/api2/ → MULTIAGENT_IP:MULTIAGENT_PORT/api/</span></div>
        <div class="endpoint"><span class="method post">307</span><span class="path">/api3/* → IDENTITY_HOST/api/*</span></div>
        <div class="endpoint"><span class="method get">PROXY</span><span class="path">/api4/ → BACKEND_IP:BACKEND_PORT/api/</span></div>
      </div>
    `,
    architecture: `
      <h3>Tech Stack</h3>
      <ul>
        <li><strong>Core</strong>: React 18, TypeScript, Vite</li>
        <li><strong>Styling</strong>: Tailwind CSS + shadcn/ui (51 Radix-based primitives in <code>components/ui/</code>)</li>
        <li><strong>Routing</strong>: Wouter (lightweight client router)</li>
        <li><strong>Server State</strong>: TanStack React Query v5</li>
        <li><strong>Graph Canvas</strong>: JointJS (<code>@joint/core</code> + dagre layout). <em>Note: react-flow-renderer in deps but fully migrated to JointJS.</em></li>
        <li><strong>Forms</strong>: react-hook-form + zod validation</li>
        <li><strong>Charts</strong>: Recharts (analytics, resource distribution)</li>
        <li><strong>Streaming</strong>: Native <code>fetch</code> + <code>ReadableStream</code> for NDJSON, oboe for JSON parsing</li>
        <li><strong>Animations</strong>: Framer Motion</li>
        <li><strong>Markdown</strong>: react-markdown + remark-gfm (chat rendering)</li>
      </ul>

      <h3>Source Layout (~280 TS/TSX files)</h3>
      <ul>
        <li><code>api/</code> (19 files) — typed API modules, one per domain</li>
        <li><code>components/</code> (162 files) — <code>agentic-ai/</code> (51), <code>ui/</code> (51 shadcn), <code>shared/</code> (22), <code>analytics/</code> (11), <code>dashboard/</code> (10), <code>layout/</code> (4), <code>auth/</code> (4)</li>
        <li><code>hooks/</code> (23 files) — domain-specific custom hooks</li>
        <li><code>contexts/</code> (7 files) — 8 app-level React context providers</li>
        <li><code>http/</code> (4 files) — axios client instances + React Query client</li>
        <li><code>features/</code> (22 files) — feature slices (slack, docs, configuration)</li>
        <li><code>pages/</code> (12 files) — route-level page components</li>
        <li><code>types/</code> (8 files) — shared TypeScript types (graph, session, workspace, templates, validation)</li>
        <li><code>stores/</code> (1 file) — Zustand pagination store (currently unused)</li>
      </ul>

      <h3>Context Provider Tree</h3>
      <p>The app wraps routes in a nested provider hierarchy:</p>
      <ul>
        <li><code>QueryClientProvider</code> → <code>ThemeProvider</code> → <code>AuthProvider</code> → <code>SharedProvider</code> → <code>ViewProvider</code> → <code>ProjectProvider</code> → <code>NotificationProvider</code> → routes</li>
        <li>Route-scoped: <code>AgenticAIProvider</code> (agentic routes), <code>StreamingDataProvider</code> (chat/execution views)</li>
      </ul>
      <table class="info-table">
        <tr><th>Context</th><th>Hook</th><th>Responsibility</th></tr>
        <tr><td>AuthContext</td><td><code>useAuth</code></td><td>User session, login/logout, token refresh, sets <code>X-Authenticated-User</code></td></tr>
        <tr><td>ViewContext</td><td><code>useView</code></td><td>Private vs team workspace, selected team, user groups</td></tr>
        <tr><td>ThemeContext</td><td><code>useTheme</code></td><td>Dark/light toggle, primary color CSS vars (localStorage)</td></tr>
        <tr><td>SharedContext</td><td><code>useShared</code></td><td>Share panel open/close, item being shared</td></tr>
        <tr><td>NotificationContext</td><td><code>useNotifications</code></td><td>Share invites (received/sent), accept/decline</td></tr>
        <tr><td>AgenticAIContext</td><td><code>useAgenticAI</code></td><td>Resource UUID↔name maps, validation caches, dependency revalidation (~760 LOC)</td></tr>
        <tr><td>StreamingDataContext</td><td><code>useStreamingData</code></td><td>In-memory node stream map for live graph/chat updates</td></tr>
        <tr><td>ProjectContext</td><td><code>useProject</code></td><td>Legacy mock/sample project data for dashboard</td></tr>
      </table>

      <h3>Custom Hooks (23)</h3>
      <table class="info-table">
        <tr><th>Hook</th><th>Domain</th><th>Summary</th></tr>
        <tr><td><code>useWorkspaceIdentity</code></td><td>Identity</td><td>Single source of truth for userId, identityType, displayName</td></tr>
        <tr><td><code>useSessionStream</code></td><td>Streaming</td><td>NDJSON Redis stream: submit → subscribe → reconnect</td></tr>
        <tr><td><code>useSessionHub</code></td><td>Sessions</td><td>Shared session list/CRUD/execution for ExecutionTab</td></tr>
        <tr><td><code>useGraphCreationLogic</code></td><td>Graph</td><td>Canvas state, YAML, validation, save/update (~1471 LOC)</td></tr>
        <tr><td><code>useGraphCreationCanvas</code></td><td>Graph</td><td>JointJS paper sync for creation canvas</td></tr>
        <tr><td><code>useGraphDisplay</code></td><td>Graph</td><td>Read-only JointJS + live status overlays</td></tr>
        <tr><td><code>useLoadBlueprint</code></td><td>Blueprints</td><td>Load spec → canvas nodes/edges with dagre layout</td></tr>
        <tr><td><code>useTemplates</code></td><td>Templates</td><td>List, detail, schema, validate, materialize</td></tr>
        <tr><td><code>useWorkspaceData</code></td><td>Inventory</td><td>Category-based element CRUD</td></tr>
        <tr><td><code>useTeamEditLockPoll</code></td><td>Collaboration</td><td>Poll edit lock statuses for team resources</td></tr>
      </table>

      <h3>State Management</h3>
      <ul>
        <li><strong>React Context</strong> — primary global state (auth, workspace, agentic mappings, notifications, streaming)</li>
        <li><strong>TanStack React Query v5</strong> — server state for all API calls (RAG dashboard, MAS resources, admin config, analytics)</li>
        <li><strong>Local useState/useRef</strong> — heavy use in graph builder, chat, collaboration hub</li>
        <li><strong>localStorage</strong> — theme, primary color</li>
      </ul>

      <h3>Dynamic Field System</h3>
      <p>Agent inventory forms are schema-driven: <code>FieldRenderer</code>, <code>FieldValidation</code>, <code>FieldPopulation</code>, and <code>AuthFieldRenderer</code> call backend via registered actions (<code>/actions/action.execute</code>) and schema-driven <code>ApiHint</code> endpoints.</p>
    `,
    _endpoints: [
    { method: 'POST', path: '/sessions/user.session.create', group: 'Sessions — /api2' },
    { method: 'POST', path: '/sessions/user.session.submit', summary: 'trigger execution', group: 'Sessions — /api2' },
    { method: 'POST', path: '/sessions/session.cancel', group: 'Sessions — /api2' },
    { method: 'GET', path: '/sessions/session.stream.status', group: 'Sessions — /api2' },
    { method: 'GET', path: '/sessions/session.subscribe', summary: 'NDJSON stream (raw fetch)', group: 'Sessions — /api2' },
    { method: 'GET', path: '/sessions/session.user.list', group: 'Sessions — /api2' },
    { method: 'GET', path: '/sessions/session.chat.get', group: 'Sessions — /api2' },
    { method: 'DEL', path: '/sessions/session.delete', group: 'Sessions — /api2' },
    { method: 'GET', path: '/blueprints/available.blueprints.get', group: 'Blueprints — /api2' },
    { method: 'GET', path: '/blueprints/available.blueprints.summary.get', group: 'Blueprints — /api2' },
    { method: 'GET', path: '/blueprints/available.blueprints.resolved.get', group: 'Blueprints — /api2' },
    { method: 'GET', path: '/blueprints/blueprint.info.get', group: 'Blueprints — /api2' },
    { method: 'POST', path: '/blueprints/blueprint.save', group: 'Blueprints — /api2' },
    { method: 'PUT', path: '/blueprints/blueprint.update', group: 'Blueprints — /api2' },
    { method: 'PUT', path: '/blueprints/blueprint.metadata.set', group: 'Blueprints — /api2' },
    { method: 'POST', path: '/blueprints/blueprint.validate', group: 'Blueprints — /api2' },
    { method: 'POST', path: '/blueprints/draft.validate', group: 'Blueprints — /api2' },
    { method: 'DEL', path: '/blueprints/remove.blueprint', group: 'Blueprints — /api2' },
    { method: 'GET', path: '/resources/resources.list', summary: 'filtered by category', group: 'Resources & Catalog — /api2' },
    { method: 'POST', path: '/resources/resource.save', group: 'Resources & Catalog — /api2' },
    { method: 'PUT', path: '/resources/resource.update', group: 'Resources & Catalog — /api2' },
    { method: 'DEL', path: '/resources/resource.delete', group: 'Resources & Catalog — /api2' },
    { method: 'POST', path: '/resources/resource.validate', group: 'Resources & Catalog — /api2' },
    { method: 'GET', path: '/catalog/elements.list.get', group: 'Resources & Catalog — /api2' },
    { method: 'GET', path: '/catalog/categories.list.get', group: 'Resources & Catalog — /api2' },
    { method: 'POST', path: '/actions/action.execute', group: 'Resources & Catalog — /api2' },
    { method: 'GET', path: '/templates/templates.list', group: 'Templates — /api2' },
    { method: 'GET', path: '/templates/template.get', group: 'Templates — /api2' },
    { method: 'GET', path: '/templates/template.schema.get', group: 'Templates — /api2' },
    { method: 'POST', path: '/templates/template.input.validate', group: 'Templates — /api2' },
    { method: 'POST', path: '/templates/template.materialize', group: 'Templates — /api2' },
    { method: 'POST', path: '/shares/share.create', group: 'Shares & Collaboration — /api2' },
    { method: 'GET', path: '/shares/shares.list', group: 'Shares & Collaboration — /api2' },
    { method: 'POST', path: '/shares/share.accept / share.decline / share.to_team', group: 'Shares & Collaboration — /api2' },
    { method: 'POST', path: '/collaboration/session.join / session.leave / session.heartbeat', group: 'Shares & Collaboration — /api2' },
    { method: 'GET', path: '/collaboration/session.participants', group: 'Shares & Collaboration — /api2' },
    { method: 'POST', path: '/collaboration/session.typing', group: 'Shares & Collaboration — /api2' },
    { method: 'POST', path: '/collaboration/edit_lock.acquire / release / heartbeat', group: 'Shares & Collaboration — /api2' },
    { method: 'POST', path: '/collaboration/edit_lock.statuses', summary: 'batch status check', group: 'Shares & Collaboration — /api2' },
    { method: 'GET', path: '/statistics/stats.get', summary: 'user dashboard', group: 'Statistics — /api2' },
    { method: 'GET', path: '/statistics/stats.system.get', summary: 'admin analytics', group: 'Statistics — /api2' },
    { method: 'GET', path: '/sessions/session.user.blueprints.get', group: 'Statistics — /api2' },
    { method: 'POST', path: '/graph/validation/all.validate', summary: 'full topology check', group: 'Graph Validation — /api2' },
    { method: 'GET', path: '/auth/user', summary: 'current session user', group: 'Auth & Teams — /api3' },
    { method: 'GET', path: '/auth/user/groups', summary: 'LDAP groups', group: 'Auth & Teams — /api3' },
    { method: 'POST', path: '/auth/logout', group: 'Auth & Teams — /api3' },
    { method: 'POST', path: '/auth/refresh', group: 'Auth & Teams — /api3' },
    { method: 'POST', path: '/teams/team.create', group: 'Auth & Teams — /api3' },
    { method: 'GET', path: '/teams/teams.list / team.get', group: 'Auth & Teams — /api3' },
    { method: 'PUT', path: '/teams/team.update', group: 'Auth & Teams — /api3' },
    { method: 'DEL', path: '/teams/team.delete + /workspace/workspace.cleanup', group: 'Auth & Teams — /api3' },
    { method: 'GET', path: '/directory/directory.status', group: 'Directory — /api3' },
    { method: 'GET', path: '/directory/directory.search_users', group: 'Directory — /api3' },
    { method: 'GET', path: '/directory/directory.search', summary: 'users + groups', group: 'Directory — /api3' },
    { method: 'GET', path: '/directory/directory.get_group', group: 'Directory — /api3' },
    { method: 'GET', path: '/data_sources/data.sources.get', group: 'RAG — /api1' },
    { method: 'GET', path: '/data_sources/data.source.details.get', group: 'RAG — /api1' },
    { method: 'POST', path: '/docs/upload', summary: 'multipart file upload', group: 'RAG — /api1' },
    { method: 'POST', path: '/docs/validate', group: 'RAG — /api1' },
    { method: 'PUT', path: '/pipelines/embed', group: 'RAG — /api1' },
    { method: 'DELETE', path: '/data_sources/data.source.delete', group: 'RAG — /api1' },
    { method: 'GET', path: '/docs/supported-extensions', group: 'RAG — /api1' },
    { method: 'GET', path: '/slack/available.slack.channels.get', group: 'RAG — /api1' },
    { method: 'GET', path: '/vector/chunks.counts', group: 'RAG — /api1' },
    { method: 'GET', path: '/health/service.readiness.get', group: 'RAG — /api1' },
    { method: 'GET', path: '/admin_config/config.get', group: 'Admin Config — /api4' },
    { method: 'PUT', path: '/admin_config/config.section.update', group: 'Admin Config — /api4' },
    { method: 'GET', path: '/admin_config/access.check', group: 'Admin Config — /api4' },
    { method: 'PROXY', path: '/api1/ → RAG_IP:RAG_PORT/api/', group: 'Nginx Routing' },
    { method: 'PROXY', path: '/api2/ → MULTIAGENT_IP:MULTIAGENT_PORT/api/', group: 'Nginx Routing' },
    { method: '307', path: '/api3/* → IDENTITY_HOST/api/*', group: 'Nginx Routing' },
    { method: 'PROXY', path: '/api4/ → BACKEND_IP:BACKEND_PORT/api/', group: 'Nginx Routing' },
  ],
  scheme: {
      nodes: [
        { id: 'browser', label: 'Browser', x: 20, y: 80, w: 100, h: 34, color: '#FBBF24' },
        { id: 'nginx', label: 'Nginx', x: 190, y: 80, w: 100, h: 34, color: '#BB86FC' },
        { id: 'rag', label: 'RAG', x: 380, y: 15, w: 100, h: 32, color: '#BB86FC' },
        { id: 'mas', label: 'Multi Agent System (MAS)', x: 380, y: 62, w: 100, h: 32, color: '#BB86FC' },
        { id: 'identity', label: 'Identity', x: 380, y: 109, w: 100, h: 32, color: '#BB86FC' },
        { id: 'platform', label: 'Platform', x: 380, y: 156, w: 100, h: 32, color: '#86EFAC' },
      ],
      edges: [
        { from: 'browser', to: 'nginx', label: 'static assets' },
        { from: 'nginx', to: 'rag', label: '/api1' },
        { from: 'nginx', to: 'mas', label: '/api2' },
        { from: 'nginx', to: 'identity', label: '/api3 (307)' },
        { from: 'nginx', to: 'platform', label: '/api4' },
      ],
    },
  },
};
