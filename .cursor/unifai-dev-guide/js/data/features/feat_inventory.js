FEATURES.feat_inventory = {
  id: 'feat_inventory',
  name: 'Agentic AI Inventory',
  icon: '🧩',
  role: 'Browse & configure AI building blocks',
  type: 'FEATURE',
  x: 40, y: -140,
  w: 260, h: 56,
  services: ['ui', 'mas', 'mongodb'],
  detail: {
    subtitle: 'Catalog of agents, tools, LLMs, retrievers, and providers',
    job: `
      <p>The <strong>Inventory</strong> (also called "User Workspace") is where developers browse the catalog of all available AI building blocks and create their own configured instances.</p>
      <h3>What the User Sees</h3>
      <ul>
        <li>A sidebar with categories: <strong>Nodes</strong> (agents), <strong>Tools</strong> (MCP, built-in), <strong>LLMs</strong> (OpenAI, Gemini), <strong>Retrievers</strong> (RAG, Slack), <strong>Providers</strong> (A2A, MCP servers), <strong>Conditions</strong></li>
        <li>A grid of element cards for the selected category</li>
        <li>A form to create/edit a configured instance (called a <em>Resource</em>)</li>
      </ul>
      <h3>Behind the Scenes</h3>
      <p>The catalog is built by <strong>auto-discovery</strong>: on startup, MAS scans all Python packages under <code>lib/mas/elements/</code> and registers every <code>BaseElementSpec</code> subclass into the <code>ElementRegistry</code>. The UI fetches this catalog and the user's saved resources via separate API calls.</p>
    `,
    interfaces: `
      <h3>API Calls (UI → MAS /api2)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/catalog/categories.list.get</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/catalog/elements.list.get — element types by category</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/catalog/element.spec.get?category=&type= — JSON Schema</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/resources/resources.list?userId=&category= — user instances</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/resources/resource.save — create new resource</span></div>
        <div class="endpoint"><span class="method put">PUT</span><span class="path">/resources/resource.update</span></div>
        <div class="endpoint"><span class="method delete">DEL</span><span class="path">/resources/resource.delete?resourceId=</span></div>
      </div>
    `,
    architecture: `
      <h3>Auto-Discovery System</h3>
      <p>MAS doesn't hard-code what building blocks exist. Instead, on startup, a <code>SpecDiscoverer</code> scans all Python packages under <code>lib/mas/elements/</code> and finds every class that extends <code>BaseElementSpec</code>. These are registered in a singleton <code>ElementRegistry</code>.</p>
      <p>This means adding a new agent type is just writing a new Python class in the right folder — no registration code needed.</p>
      <h3>Resources = Configured Instances</h3>
      <p>A "resource" is a user's configured instance of a catalog element. For example:</p>
      <ul>
        <li>Catalog element: "OpenAI LLM" (the type)</li>
        <li>Resource: "My GPT-4 instance" (the user's config with their API key and model choice)</li>
      </ul>
      <p>Resources are stored in MongoDB and referenced by blueprints. Each resource's config is validated against the element's JSON Schema before saving.</p>
      <h3>Key Files</h3>
      <ul>
        <li><code>lib/mas/catalog/element_registry.py</code> — singleton registry of all element types</li>
        <li><code>lib/mas/catalog/spec_discoverer.py</code> — auto-discovery at startup</li>
        <li><code>adapters/outbound/mongo/resource_repository.py</code> — resource persistence</li>
        <li><code>UI: pages/AgentRepository.tsx</code> — the inventory page component</li>
      </ul>
    `,
    flow: [
      { step: 1, label: 'User opens the Inventory page', actor: 'UI', detail: 'The inventory page loads and shows a sidebar of categories (Agents, Tools, LLMs, etc.)' },
      { step: 2, label: 'UI fetches the catalog', actor: 'UI → MAS', detail: 'Asks MAS "what types of building blocks exist?" — MAS auto-discovers them on startup' },
      { step: 3, label: 'UI fetches the user\'s saved resources', actor: 'UI → MAS', detail: 'Asks MAS "what has this user already configured?" — MAS reads from MongoDB' },
      { step: 4, label: 'User creates a new resource', actor: 'UI', detail: 'Picks a type (e.g. OpenAI LLM), fills in config (API key, model name)' },
      { step: 5, label: 'MAS validates and saves', actor: 'MAS → MongoDB', detail: 'Checks the config matches the expected schema, then stores it in the database' },
    ],
    codeFlow: [
      { step: 1, label: 'Route /inventory loads', actor: 'UI', detail: '<code>AgentRepository.tsx</code> renders → calls <code>use-workspace-data.ts</code> hook' },
      { step: 2, label: 'GET /catalog/elements.list.get', actor: 'UI → MAS', detail: '<code>CatalogService.get_elements()</code> → <code>ElementRegistry</code> (populated by <code>SpecDiscoverer</code> at startup from <code>lib/mas/elements/*/spec.py</code>)' },
      { step: 3, label: 'GET /resources/resources.list?userId=&category=', actor: 'UI → MAS', detail: '<code>ResourceService.list()</code> → <code>MongoResourceRepository.find_by_user()</code>' },
      { step: 4, label: 'User fills ElementForm', actor: 'UI', detail: 'Form rendered from JSON Schema via <code>ElementRegistry.get_schema(category, type)</code>' },
      { step: 5, label: 'POST /resources/resource.save', actor: 'UI → MAS', detail: '<code>ResourceService.save()</code> → validate against schema → <code>MongoResourceRepository.insert()</code>' },
    ],
      _endpoints: [
    { method: 'GET', path: '/catalog/categories.list.get' },
    { method: 'GET', path: '/catalog/elements.list.get', summary: 'element types by category' },
    { method: 'GET', path: '/catalog/element.spec.get?category=&type=', summary: 'JSON Schema' },
    { method: 'GET', path: '/resources/resources.list?userId=&category=', summary: 'user instances' },
    { method: 'POST', path: '/resources/resource.save', summary: 'create new resource' },
    { method: 'PUT', path: '/resources/resource.update' },
    { method: 'DEL', path: '/resources/resource.delete?resourceId=' },
  ],
  scheme: {
      nodes: [
        { id: 'ui', label: 'UI', x: 20, y: 55, w: 90, h: 36, color: '#BB86FC' },
        { id: 'mas', label: 'Multi Agent System (MAS)', x: 180, y: 55, w: 110, h: 36, color: '#BB86FC' },
        { id: 'registry', label: 'ElementRegistry', x: 370, y: 18, w: 155, h: 36, color: '#38BDF8' },
        { id: 'mongo', label: 'MongoDB', x: 370, y: 95, w: 120, h: 36, color: '#86EFAC' },
      ],
      edges: [
        { from: 'ui', to: 'mas', label: '/api2' },
        { from: 'mas', to: 'registry', label: 'catalog scan' },
        { from: 'mas', to: 'mongo', label: 'resources CRUD' },
      ],
    },
    dataModel: `
      <h3>MongoDB Collections</h3>
      <div class="data-model-section">
        <div class="data-model-entry">
          <code>multiagent.resources</code>
          <p>Configured instances (resources) of catalog elements created by users.</p>
          <div class="data-model-fields">Key fields: <code>userId</code>, <code>identityType</code>, <code>category</code>, <code>elementType</code>, <code>config</code> (validated JSON), <code>name</code></div>
        </div>
      </div>
      <h3>In-Memory Registry</h3>
      <p>The <code>ElementRegistry</code> singleton holds all discovered element types and their JSON Schemas. Built at startup by <code>SpecDiscoverer</code> — not persisted, rebuilt on every restart.</p>
    `,
    devScenarios: `
      <h3>Common Dev Tasks</h3>
      <div class="dev-scenario">
        <h4>Add a new element type (e.g. new LLM provider)</h4>
        <ol>
          <li>Create a Python package under <code>lib/mas/elements/&lt;category&gt;/</code></li>
          <li>Define a class extending <code>BaseElementSpec</code> with a JSON Schema for config</li>
          <li>Restart MAS — <code>SpecDiscoverer</code> auto-discovers it, no registration code needed</li>
          <li>The UI catalog shows the new type automatically</li>
        </ol>
      </div>
      <div class="dev-scenario">
        <h4>Change a resource's validation schema</h4>
        <ol>
          <li>Edit the <code>config_schema()</code> method on the relevant <code>BaseElementSpec</code> subclass</li>
          <li>Existing saved resources are not re-validated — only new saves go through schema check</li>
          <li>If existing data must change, write a migration script</li>
        </ol>
      </div>
    `,
    dependencies: {
      requires: [],
      requiredBy: [
        { featureId: 'feat_workflows', reason: 'Blueprints reference configured resources from the Inventory' },
        { featureId: 'feat_chats', reason: 'Session execution builds runtime elements from saved resources' },
      ],
    },
  },
};
