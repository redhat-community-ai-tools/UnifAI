SERVICE_CLASSES.temporal_worker = {
  description: `<p>The Temporal Worker runs inside the MAS codebase (<code>multi-agent/adapters/inbound/temporal/</code>). It registers workflows and activities, then polls the Temporal Server for work.</p>`,
  layers: [
    {
      name: 'Worker Registration',
      classes: [
        { name: 'run_worker()', file: 'adapters/inbound/temporal/worker.py', role: 'Registers workflows + activities on temporalio.Worker, starts polling', calls: ['mas:SessionWorkflow', 'mas:GraphTraversalWorkflow', 'mas:GraphNodeActivities', 'mas:SessionLifecycleActivities'], calledBy: ['entrypoint'] },
      ]
    },
    {
      name: 'Workflows',
      classes: [
        { name: 'SessionWorkflow', file: 'adapters/inbound/temporal/workflows/session_workflow.py', role: 'Parent: begin → graph traversal → complete/fail lifecycle', calls: ['mas:BackgroundSessionRunner', 'GraphTraversalWorkflow', 'SessionLifecycleActivities'], calledBy: ['Temporal: dispatch'] },
        { name: 'GraphTraversalWorkflow', file: 'adapters/inbound/temporal/workflows/graph_traversal_workflow.py', role: 'Child: BSP supersteps — plan, execute nodes, evaluate conditions, repeat', calls: ['mas:GraphTraversal', 'GraphNodeActivities'], calledBy: ['SessionWorkflow'] },
      ]
    },
    {
      name: 'Activities',
      classes: [
        { name: 'GraphNodeActivities', file: 'adapters/inbound/temporal/activities/graph_node_activities.py', role: 'Execute one graph node or evaluate edge condition', calls: ['mas:NodeExecutor', 'mas:ChannelFactory'], calledBy: ['GraphTraversalWorkflow'] },
        { name: 'SessionLifecycleActivities', file: 'adapters/inbound/temporal/activities/session_lifecycle_activities.py', role: 'Begin/complete/fail session transitions via handler', calls: ['BackgroundLifecycleHandler'], calledBy: ['SessionWorkflow'] },
      ]
    },
    {
      name: 'Engine (from MAS lib)',
      classes: [
        { name: 'NodeExecutor', file: 'lib/mas/engine/distributed/node_executor.py', role: 'Executes a single node: materializes mini-blueprint, runs via session factory', calls: ['mas:WorkflowSessionFactory', 'mas:SessionChannel'], calledBy: ['GraphNodeActivities'] },
        { name: 'GraphTraversal', file: 'lib/mas/engine/distributed/traversal.py', role: 'BSP superstep algorithm: which nodes are ready, execute, merge, evaluate', calls: ['GraphNodeActivities', 'mas:GraphDefinition'], calledBy: ['GraphTraversalWorkflow'] },
        { name: 'BackgroundLifecycleHandler', file: 'lib/mas/session/execution/lifecycle_handler.py', role: 'Thin adapter: session manager + lifecycle + channels for activities', calls: ['mas:UserSessionManager', 'mas:SessionLifecycle', 'mas:ChannelFactory'], calledBy: ['SessionLifecycleActivities'] },
      ]
    },
  ],
  scheme: {
    nodes: [
      { id: 'temporal_srv', label: 'Temporal Srv', x: 20, y: 55, w: 125, h: 34, color: '#86EFAC' },
      { id: 'session_wf', label: 'SessionWF', x: 215, y: 25, w: 115, h: 34, color: '#38BDF8' },
      { id: 'graph_wf', label: 'GraphWF', x: 215, y: 85, w: 105, h: 34, color: '#38BDF8' },
      { id: 'node_exec', label: 'NodeExecutor', x: 405, y: 25, w: 125, h: 34, color: '#BB86FC' },
      { id: 'lifecycle', label: 'Lifecycle', x: 405, y: 85, w: 110, h: 34, color: '#BB86FC' },
      { id: 'redis', label: 'Redis', x: 600, y: 25, w: 90, h: 34, color: '#86EFAC' },
      { id: 'mongo', label: 'MongoDB', x: 600, y: 85, w: 100, h: 34, color: '#86EFAC' },
    ],
    edges: [
      { from: 'temporal_srv', to: 'session_wf', label: 'dispatch' },
      { from: 'session_wf', to: 'graph_wf', label: 'child' },
      { from: 'graph_wf', to: 'node_exec', label: 'activity' },
      { from: 'session_wf', to: 'lifecycle', label: 'activity' },
      { from: 'node_exec', to: 'redis', label: 'events' },
      { from: 'lifecycle', to: 'mongo', label: 'state' },
    ],
  },
};
