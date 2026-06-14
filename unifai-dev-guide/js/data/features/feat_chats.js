FEATURES.feat_chats = {
  id: 'feat_chats',
  name: 'Chats (Sessions)',
  icon: '💬',
  role: 'Execute blueprints & stream responses',
  type: 'FEATURE',
  x: 650, y: -140,
  w: 260, h: 56,
  services: ['ui', 'mas', 'mongodb', 'redis', 'temporal', 'temporal_worker', 'rag'],
  detail: {
    subtitle: 'Real-time streaming execution of AI agent workflows',
    job: `
      <p><strong>Chats</strong> are live execution sessions of blueprints. Users send messages and watch AI agents work in real-time with streaming output.</p>
      <h3>What the User Sees</h3>
      <ul>
        <li>A list of chat sessions (each linked to a blueprint)</li>
        <li>A chat interface to send messages and see streaming responses</li>
        <li>An execution stream panel showing node-by-node progress</li>
        <li>The blueprint graph visualization alongside the chat</li>
      </ul>
      <h3>Execution Mode</h3>
      <p>Sessions run in <strong>Background</strong> mode by default (<code>engine_name=temporal</code>). The UI calls <code>submit</code>, Temporal executes the graph on distributed workers, and results stream back via Redis Streams.</p>
      <ul>
        <li><strong>Background (default)</strong> — submitted to Temporal as a durable workflow; UI subscribes via Redis Streams</li>
        <li><strong>Foreground (fallback)</strong> — in-process LangGraph execution with NDJSON streaming; used when Temporal is unavailable or for dev/simple graphs</li>
      </ul>
    `,
    interfaces: `
      <h3>Session Lifecycle (UI → MAS /api2)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/user.session.create</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/user.session.submit — execute via Temporal (default)</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/sessions/user.session.execute — foreground fallback (stream: true)</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.subscribe — Redis stream subscription</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.chat.get?sessionId= — full chat history</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.user.list?userId=</span></div>
      </div>
      <h3>Streaming Protocol</h3>
      <p>Response is <code>application/x-ndjson</code>. Each line is a JSON object: node progress events + <code>{"type":"heartbeat"}</code> keep-alives.</p>
    `,
    architecture: `
      <h3>Execution Paths</h3>
      <p>The configured default is <strong>Background (Temporal)</strong>. A foreground fallback exists for environments without Temporal.</p>
      <h3>Background — default (distributed, via Temporal)</h3>
      <ul>
        <li>The request returns immediately with a workflow ID (HTTP 202)</li>
        <li>Temporal dispatches <code>SessionWorkflow</code> → <code>GraphTraversalWorkflow</code> to a worker</li>
        <li>Each graph node runs as a separate Temporal activity with built-in retries</li>
        <li>Events are written to Redis Streams; the UI subscribes via <code>session.subscribe</code> (long-polling/SSE)</li>
      </ul>
      <h3>Foreground — fallback (in-process, via LangGraph)</h3>
      <ul>
        <li>The user's message is merged into the graph's input state</li>
        <li>The blueprint is resolved (inject configs) → compiled into a LangGraph executable</li>
        <li>A background thread runs the graph; the main thread reads events from an in-process channel and streams them as NDJSON</li>
        <li>Heartbeat JSON objects (<code>{"type":"heartbeat"}</code>) keep the HTTP connection alive between real events</li>
      </ul>
      <h3>Key Design Decision: Streaming</h3>
      <p>The streaming protocol uses NDJSON (one JSON object per line). This works natively with <code>fetch()</code> ReadableStream in the browser — no WebSockets needed. The UI's <code>StreamingDataContext</code> processes these events and updates the chat in real-time.</p>
    `,
    flow: [
      { step: 1, label: 'User picks a blueprint and starts a chat', actor: 'UI → MAS', detail: 'A new session is created in MongoDB, linked to the chosen blueprint' },
      { step: 2, label: 'User types a message and hits send', actor: 'UI → MAS', detail: 'The message is sent to MAS, which merges it into the graph\'s input state' },
      { step: 3, label: 'MAS compiles the blueprint into a runnable graph', actor: 'MAS', detail: 'Resolve resource configs → build a logical graph plan → create runtime elements → compile to an executor' },
      { step: 4, label: 'Graph nodes execute step by step', actor: 'MAS', detail: 'Each "superstep" runs eligible nodes in parallel, then merges their outputs before the next step' },
      { step: 5, label: 'Nodes call external services as needed', actor: 'MAS → LLM / RAG / MCP', detail: 'Agent nodes call LLMs (OpenAI, Gemini), retriever nodes search RAG, tool nodes invoke MCP servers' },
      { step: 6, label: 'Results stream back to the browser', actor: 'MAS → UI', detail: 'NDJSON streaming — each line is a JSON event; heartbeats keep the connection alive' },
      { step: 7, label: 'Chat history is saved', actor: 'MAS → MongoDB', detail: 'The final graph state and conversation are persisted for future reference' },
    ],
    codeFlow: [
      { step: 1, label: 'POST /sessions/user.session.create', actor: 'UI → MAS', detail: '<code>SessionService.create()</code> → <code>MongoSessionRepository</code> creates record linked to blueprint' },
      { step: 2, label: 'POST /sessions/user.session.submit', actor: 'UI → MAS', detail: '<code>SessionService.submit()</code> → <code>SessionInputProjector.apply()</code> merges user prompt → <code>TemporalSessionEngine.submit()</code> starts workflow → HTTP 202' },
      { step: 3, label: 'Temporal dispatches SessionWorkflow → GraphTraversalWorkflow', actor: 'Temporal → Worker', detail: 'Blueprint compiled via <code>TemporalGraphBuilder</code>; BSP supersteps run as activities on the <code>graph-engine</code> task queue' },
      { step: 4, label: 'UI subscribes via GET /sessions/session.subscribe', actor: 'UI → MAS → Redis', detail: 'Worker nodes stream events to Redis Streams; UI connects via NDJSON <code>session.subscribe</code> endpoint' },
      { step: 5, label: 'Element nodes invoke external calls', actor: 'MAS', detail: 'Agent elements use <code>ChatModel</code> (LangChain); retrievers call <code>RagClient.query_match()</code>; tools use <code>MCPClientAdapter</code>' },
      { step: 6, label: 'Events stream via Redis → NDJSON to UI', actor: 'Worker → Redis → MAS → UI', detail: '<code>SessionChannel.emit()</code> on worker → Redis Streams → <code>session.subscribe</code> endpoint → <code>application/x-ndjson</code> response to browser' },
      { step: 7, label: 'State persisted via MongoSessionRepository', actor: 'MAS → MongoDB', detail: 'Final state saved; UI calls <code>GET /sessions/session.chat.get</code> for full history' },
    ],
      _endpoints: [
    { method: 'POST', path: '/sessions/user.session.create' },
    { method: 'POST', path: '/sessions/user.session.submit', summary: 'execute via Temporal (default)' },
    { method: 'POST', path: '/sessions/user.session.execute', summary: 'foreground fallback (stream: true)' },
    { method: 'GET', path: '/sessions/session.subscribe', summary: 'Redis stream subscription' },
    { method: 'GET', path: '/sessions/session.chat.get?sessionId=', summary: 'full chat history' },
    { method: 'GET', path: '/sessions/session.user.list?userId=' },
  ],
  scheme: {
      nodes: [
        { id: 'ui', label: 'UI', x: 20, y: 105, w: 90, h: 36, color: '#BB86FC' },
        { id: 'mas', label: 'Multi Agent System (MAS)', x: 180, y: 105, w: 110, h: 36, color: '#BB86FC' },
        { id: 'langgraph', label: 'LangGraph', x: 370, y: 10, w: 120, h: 36, color: '#38BDF8' },
        { id: 'temporal', label: 'Temporal', x: 370, y: 65, w: 115, h: 36, color: '#86EFAC' },
        { id: 'worker', label: 'Worker', x: 560, y: 65, w: 100, h: 36, color: '#38BDF8' },
        { id: 'redis', label: 'Redis', x: 370, y: 125, w: 100, h: 36, color: '#86EFAC' },
        { id: 'mongo', label: 'MongoDB', x: 370, y: 185, w: 120, h: 36, color: '#86EFAC' },
      ],
      edges: [
        { from: 'ui', to: 'mas', label: 'submit' },
        { from: 'mas', to: 'temporal', label: 'default' },
        { from: 'mas', to: 'langgraph', label: 'fallback' },
        { from: 'temporal', to: 'worker', label: 'dispatch' },
        { from: 'mas', to: 'redis', label: 'stream events' },
        { from: 'mas', to: 'mongo', label: 'persist state' },
      ],
    },
    dataModel: `
      <h3>MongoDB Collections</h3>
      <div class="data-model-section">
        <div class="data-model-entry">
          <code>multiagent.sessions</code>
          <p>Chat session records linking a user to a blueprint execution.</p>
          <div class="data-model-fields">Key fields: <code>userId</code>, <code>identityType</code>, <code>blueprintId</code>, <code>status</code>, <code>created_at</code></div>
        </div>
        <div class="data-model-entry">
          <code>multiagent.session_chat_history</code>
          <p>Full conversation log — user messages and agent responses per session.</p>
          <div class="data-model-fields">Key fields: <code>sessionId</code>, <code>messages[]</code> (role, content, timestamp), <code>graph_state</code></div>
        </div>
      </div>
      <h3>Redis</h3>
      <div class="data-model-section">
        <div class="data-model-entry">
          <code>session:{sessionId}:stream</code>
          <p>Redis Stream for background execution events. UI subscribes via <code>session.subscribe</code> endpoint.</p>
        </div>
      </div>
    `,
    devScenarios: `
      <h3>Common Dev Tasks</h3>
      <div class="dev-scenario">
        <h4>Add a new streaming event type</h4>
        <ol>
          <li>Define the event in <code>SessionChannel</code> event types</li>
          <li>Emit it from the relevant graph node or executor</li>
          <li>Handle it in the UI's <code>StreamingDataContext</code> to update the chat view</li>
        </ol>
      </div>
      <div class="dev-scenario">
        <h4>Debug a stuck session</h4>
        <ol>
          <li>Check session status in MongoDB <code>sessions</code> collection</li>
          <li>For foreground: look at MAS logs for graph execution errors</li>
          <li>For background: check Temporal UI for workflow status and activity failures</li>
          <li>Check Redis for dangling stream keys if the UI stopped receiving events</li>
        </ol>
      </div>
      <div class="dev-scenario">
        <h4>Add a new executor backend</h4>
        <ol>
          <li>Implement a new builder in <code>GraphBuilderFactory</code></li>
          <li>The pipeline is: Resolve → Plan → Build → Compile — your backend plugs into Compile</li>
          <li>The rest of the pipeline stays the same — only the final executor changes</li>
        </ol>
      </div>
    `,
    dependencies: {
      requires: [
        { featureId: 'feat_workflows', reason: 'Sessions execute blueprints created in the Workflow builder' },
        { featureId: 'feat_inventory', reason: 'Blueprint execution resolves resource configs from the Inventory' },
      ],
      requiredBy: [
        { featureId: 'feat_overview', reason: 'Overview dashboards show session counts and activity' },
      ],
    },
  },
};
