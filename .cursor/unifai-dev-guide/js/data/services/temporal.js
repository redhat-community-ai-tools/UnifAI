SERVICES.temporal = {
  id: 'temporal',
  name: 'Temporal Server',
  icon: '⏱️',
  role: 'Workflow orchestration',
  type: 'INFRA',
  x: 940, y: 710,
  w: 200, h: 54,
  detail: {
    subtitle: 'Default engine • Durable workflow execution for MAS',
    job: `
      <p><strong>Temporal</strong> is the default execution engine for MAS (<code>engine_name=temporal</code>). It provides durable, distributed workflow execution. Without it, MAS falls back to in-process foreground execution via LangGraph.</p>
      <h3>Benefits</h3>
      <ul>
        <li>Workflows survive process crashes and restarts</li>
        <li>Built-in retry policies for activities</li>
        <li>Horizontal scaling via multiple workers on the same task queue</li>
        <li>Visibility UI for workflow debugging</li>
      </ul>
    `,
    interfaces: `<p>Temporal gRPC API. MAS uses the Python Temporal SDK (<code>temporalio</code>). Task queue: <code>graph-engine</code>.</p>`,
    architecture: `<p>Connection configured via <code>temporal_host</code>, <code>temporal_namespace</code> in MAS <code>AppConfig</code>. Worker registered in <code>adapters/inbound/temporal/worker.py</code>.</p>`,
    scheme: null,
  },
};
