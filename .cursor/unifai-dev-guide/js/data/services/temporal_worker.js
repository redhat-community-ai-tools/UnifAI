SERVICES.temporal_worker = {
  id: 'temporal_worker',
  name: 'MAS Temporal Worker',
  icon: '🔄',
  role: 'Distributed graph execution',
  type: 'WORKER',
  x: 820, y: 540,
  w: 220, h: 60,
  detail: {
    subtitle: 'Temporal SDK • Task queue: graph-engine',
    job: `
      <p>The <strong>Temporal Worker</strong> is a separate process that executes blueprint graphs durably. When the Multi Agent System (MAS) submits a workflow, the Temporal Server dispatches it to this worker.</p>
      <h3>Why Temporal?</h3>
      <ul>
        <li><strong>Durability</strong> — workflows survive process restarts</li>
        <li><strong>Scalability</strong> — multiple workers can process graphs in parallel</li>
        <li><strong>Retry logic</strong> — built-in activity retries and timeouts</li>
      </ul>
      <h3>Workflow Structure</h3>
      <ul>
        <li><strong>SessionWorkflow</strong> — top-level orchestrator: begin → graph → complete/fail</li>
        <li><strong>GraphTraversalWorkflow</strong> — child workflow: runs BSP supersteps, calls activities for each node</li>
      </ul>
      <h3>Node Execution</h3>
      <p>Each graph node is executed as a Temporal activity. The <code>NodeExecutor</code> materializes a "mini-blueprint" for the node and runs it, streaming events via Redis.</p>
    `,
    interfaces: `
      <h3>Temporal Workflows</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method post">WF</span><span class="path">SessionWorkflow — orchestrates full session lifecycle</span></div>
        <div class="endpoint"><span class="method post">WF</span><span class="path">GraphTraversalWorkflow — executes graph traversal</span></div>
      </div>
      <h3>Temporal Activities</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method put">ACT</span><span class="path">execute_graph_node — run one node's logic</span></div>
        <div class="endpoint"><span class="method put">ACT</span><span class="path">evaluate_condition — check edge conditions</span></div>
        <div class="endpoint"><span class="method put">ACT</span><span class="path">begin_session / complete_session / fail_session</span></div>
      </div>
      <h3>Task Queue</h3>
      <p><code>"graph-engine"</code> (configurable via <code>temporal_task_queue</code>)</p>
    `,
    architecture: `
      <h3>Key Files</h3>
      <ul>
        <li><code>adapters/inbound/temporal/worker.py</code> — worker registration</li>
        <li><code>adapters/inbound/temporal/workflows/session_workflow.py</code></li>
        <li><code>adapters/inbound/temporal/workflows/graph_traversal_workflow.py</code></li>
        <li><code>adapters/inbound/temporal/activities/graph_node_activities.py</code></li>
        <li><code>lib/mas/engine/distributed/node_executor.py</code> — materializes + runs nodes</li>
        <li><code>lib/mas/engine/distributed/traversal.py</code> — BSP graph traversal</li>
      </ul>
      <h3>Execution Model</h3>
      <p>Activities run in a <code>ThreadPoolExecutor</code>. Each node execution creates its own element instances from a mini-blueprint, enabling full isolation.</p>
    `,
    _endpoints: [
    { method: 'WF', path: 'SessionWorkflow', summary: 'orchestrates full session lifecycle' },
    { method: 'WF', path: 'GraphTraversalWorkflow', summary: 'executes graph traversal' },
    { method: 'ACT', path: 'execute_graph_node', summary: 'run one node\'s logic' },
    { method: 'ACT', path: 'evaluate_condition', summary: 'check edge conditions' },
    { method: 'ACT', path: 'begin_session / complete_session / fail_session' },
  ],
  scheme: {
      nodes: [
        { id: 'temporal', label: 'Temporal Srv', x: 15, y: 55, w: 80, h: 26, color: '#86EFAC' },
        { id: 'worker', label: 'Temporal Worker', x: 145, y: 55, w: 95, h: 30, color: '#38BDF8' },
        { id: 'redis', label: 'Redis', x: 295, y: 15, w: 65, h: 24, color: '#86EFAC' },
        { id: 'llm', label: 'LLM APIs', x: 295, y: 45, w: 65, h: 24, color: '#FBBF24' },
        { id: 'rag', label: 'RAG', x: 295, y: 75, w: 65, h: 24, color: '#BB86FC' },
        { id: 'mcp', label: 'MCP Servers', x: 295, y: 105, w: 72, h: 24, color: '#FBBF24' },
        { id: 'mongo', label: 'MongoDB', x: 145, y: 115, w: 65, h: 24, color: '#86EFAC' },
      ],
      edges: [
        { from: 'temporal', to: 'worker', label: 'dispatch' },
        { from: 'worker', to: 'redis', label: 'stream events' },
        { from: 'worker', to: 'llm', label: 'completions' },
        { from: 'worker', to: 'rag', label: 'query' },
        { from: 'worker', to: 'mcp', label: 'tools' },
        { from: 'worker', to: 'mongo', label: 'state' },
      ],
    },
  },
};
