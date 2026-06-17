FEATURES.feat_workflows = {
  id: 'feat_workflows',
  name: 'Agentic AI Workflows',
  icon: '🔀',
  role: 'Build & manage blueprint graphs',
  type: 'FEATURE',
  x: 340, y: -140,
  w: 230, h: 56,
  services: ['ui', 'mas', 'mongodb'],
  detail: {
    subtitle: 'Visual blueprint builder with JointJS graph editor',
    job: `
      <p><strong>Workflows</strong> let users visually design AI agent graphs called <em>blueprints</em>. Each blueprint is a directed graph of nodes (agents, tools, retrievers) connected by edges with optional conditions.</p>
      <h3>What the User Sees</h3>
      <ul>
        <li>A list of saved blueprints with validation status</li>
        <li>A visual graph builder (drag-and-drop canvas using JointJS)</li>
        <li>A building-blocks sidebar showing available resources</li>
        <li>Validation panel showing graph errors before saving</li>
      </ul>
      <h3>Behind the Scenes</h3>
      <p>Blueprints are stored as YAML-serializable specs. On save, the graph is validated against the <code>ElementRegistry</code> schemas. On execution, the blueprint goes through a multi-step compilation: <strong>resolve</strong> (inject resources) → <strong>plan</strong> (build logical graph) → <strong>build</strong> (create runtime elements) → <strong>compile</strong> (Temporal by default, or LangGraph as fallback).</p>
    `,
    interfaces: `
      <h3>Blueprint CRUD (UI → MAS /api2)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/available.blueprints.summary.get?userId=</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/blueprint.info.get — full spec for editing</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/blueprints/blueprint.save</span></div>
        <div class="endpoint"><span class="method put">PUT</span><span class="path">/blueprints/blueprint.update</span></div>
        <div class="endpoint"><span class="method delete">DEL</span><span class="path">/blueprints/remove.blueprint?blueprintId=</span></div>
      </div>
      <h3>Validation</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method post">POST</span><span class="path">/graph/validation/all.validate — pre-save graph check</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/blueprints/blueprint.validate — full blueprint validation</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/blueprints/draft.validate</span></div>
      </div>
    `,
    architecture: `
      <h3>Blueprint Compilation Pipeline</h3>
      <p>When a blueprint is executed, it goes through a multi-stage compilation. Think of it like a compiler turning source code into an executable:</p>
      <ul>
        <li><strong>Resolve</strong> — Replace resource references with actual configs (API keys, model names, etc.). Handled by <code>BlueprintResolver</code>.</li>
        <li><strong>Plan</strong> — Build a logical graph plan: which nodes exist, what order they run in, what conditions control the edges. Handled by <code>PlanBuilder</code>.</li>
        <li><strong>Build</strong> — Create runtime element instances (actual agent/tool/LLM objects) in dependency order. Handled by <code>SessionElementBuilder</code>.</li>
        <li><strong>Compile</strong> — Turn the plan into a runnable executor: a Temporal workflow (default) or a LangGraph state machine (fallback). Handled by <code>GraphBuilderFactory</code>.</li>
      </ul>
      <h3>Why a Compilation Pipeline?</h3>
      <p>Blueprints are just data (a YAML-serializable spec). The compilation pipeline separates "what the user designed" from "how it actually runs." The same blueprint can target different backends (Temporal by default, LangGraph as fallback) and the user doesn't need to know which one is used.</p>
      <h3>Key Files</h3>
      <ul>
        <li><code>lib/mas/blueprints/resolver.py</code> — resolve resource refs</li>
        <li><code>lib/mas/graph/plan_builder.py</code> — build logical plan</li>
        <li><code>lib/mas/session/building/workflow_session_factory.py</code> — orchestrate the full pipeline</li>
        <li><code>UI: workspace/NewGraph.tsx</code> — the visual graph editor</li>
      </ul>
    `,
    flow: [
      { step: 1, label: 'User opens the workflow builder', actor: 'UI', detail: 'A drag-and-drop canvas (JointJS) opens with a sidebar of available building blocks' },
      { step: 2, label: 'UI loads the user\'s configured resources', actor: 'UI → MAS', detail: 'Populates the sidebar with agents, tools, and LLMs the user has set up' },
      { step: 3, label: 'User designs the graph', actor: 'UI', detail: 'Drags nodes onto the canvas, draws edges between them, and optionally sets conditions' },
      { step: 4, label: 'Graph is validated', actor: 'UI → MAS', detail: 'MAS checks the graph structure: are all node types valid? Are required connections present?' },
      { step: 5, label: 'User saves the blueprint', actor: 'UI → MAS → MongoDB', detail: 'The full graph definition is stored in MongoDB as a serializable blueprint spec' },
      { step: 6, label: 'Blueprint appears in the list', actor: 'UI', detail: 'The workflow list refreshes and shows the new blueprint ready for execution' },
    ],
    codeFlow: [
      { step: 1, label: 'NewGraph.tsx initializes JointJS canvas', actor: 'UI', detail: '<code>use-graph-creation-logic.ts</code> → sets up the visual editor + sidebar' },
      { step: 2, label: 'GET /resources/resources.list?userId=', actor: 'UI → MAS', detail: '<code>ResourceService.list()</code> → populates the building-blocks sidebar panel' },
      { step: 3, label: 'User designs via GraphCreation component', actor: 'UI', detail: 'JointJS cells → serialized to YAML-compatible <code>BlueprintSpec</code> format on each change' },
      { step: 4, label: 'POST /graph/validation/all.validate', actor: 'UI → MAS', detail: '<code>GraphValidationService.validate()</code> → checks node types, required refs, edge conditions against <code>ElementRegistry</code>' },
      { step: 5, label: 'POST /blueprints/blueprint.save', actor: 'UI → MAS', detail: '<code>BlueprintService.save()</code> → <code>MongoBlueprintRepository.insert()</code>' },
      { step: 6, label: 'GET /blueprints/available.blueprints.summary.get', actor: 'UI → MAS', detail: 'Summary reload → list page updates' },
    ],
      _endpoints: [
    { method: 'GET', path: '/blueprints/available.blueprints.summary.get?userId=' },
    { method: 'GET', path: '/blueprints/blueprint.info.get', summary: 'full spec for editing' },
    { method: 'POST', path: '/blueprints/blueprint.save' },
    { method: 'PUT', path: '/blueprints/blueprint.update' },
    { method: 'DEL', path: '/blueprints/remove.blueprint?blueprintId=' },
    { method: 'POST', path: '/graph/validation/all.validate', summary: 'pre-save graph check' },
    { method: 'POST', path: '/blueprints/blueprint.validate', summary: 'full blueprint validation' },
    { method: 'POST', path: '/blueprints/draft.validate' },
  ],
  scheme: {
      nodes: [
        { id: 'ui', label: 'UI', x: 20, y: 55, w: 90, h: 36, color: '#BB86FC' },
        { id: 'mas', label: 'Multi Agent System (MAS)', x: 180, y: 55, w: 110, h: 36, color: '#BB86FC' },
        { id: 'validator', label: 'GraphValidator', x: 370, y: 18, w: 145, h: 36, color: '#38BDF8' },
        { id: 'mongo', label: 'MongoDB', x: 370, y: 95, w: 120, h: 36, color: '#86EFAC' },
      ],
      edges: [
        { from: 'ui', to: 'mas', label: '/api2' },
        { from: 'mas', to: 'validator', label: 'validate graph' },
        { from: 'mas', to: 'mongo', label: 'blueprints CRUD' },
      ],
    },
    dataModel: `
      <h3>MongoDB Collections</h3>
      <div class="data-model-section">
        <div class="data-model-entry">
          <code>multiagent.blueprints</code>
          <p>Blueprint definitions — the full graph spec including nodes, edges, conditions, and resource references.</p>
          <div class="data-model-fields">Key fields: <code>userId</code>, <code>identityType</code>, <code>name</code>, <code>spec</code> (YAML-serializable graph), <code>validation_status</code></div>
        </div>
        <div class="data-model-entry">
          <code>multiagent.resources</code> <span style="color:var(--text-muted)">(read-only)</span>
          <p>Blueprints reference resources by ID. The sidebar populates from the user's saved resources.</p>
        </div>
      </div>
    `,
    devScenarios: `
      <h3>Common Dev Tasks</h3>
      <div class="dev-scenario">
        <h4>Add a new graph validation rule</h4>
        <ol>
          <li>Open <code>lib/mas/graph/validation/</code> and find the relevant validator</li>
          <li>Add a new check method or extend an existing one in <code>GraphValidationService</code></li>
          <li>The validation endpoint calls all registered checks — no wiring needed</li>
        </ol>
      </div>
      <div class="dev-scenario">
        <h4>Support a new node connection pattern</h4>
        <ol>
          <li>Update the edge condition logic in <code>PlanBuilder</code></li>
          <li>Add corresponding validation rules so invalid patterns are caught on save</li>
          <li>Update the UI's JointJS graph constraints if the canvas needs to enforce the pattern</li>
        </ol>
      </div>
    `,
    dependencies: {
      requires: [
        { featureId: 'feat_inventory', reason: 'Blueprints reference configured resources (agents, tools, LLMs) from the Inventory' },
      ],
      requiredBy: [
        { featureId: 'feat_chats', reason: 'Chat sessions execute blueprints created in Workflows' },
        { featureId: 'feat_overview', reason: 'Overview dashboards display workflow statistics and usage' },
      ],
    },
  },
};
