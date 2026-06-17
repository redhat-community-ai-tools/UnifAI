SERVICES.platform = {
  id: 'platform',
  name: 'Platform Backend',
  icon: '⚙️',
  role: 'Admin configuration service',
  type: 'APP',
  x: 1400, y: 380,
  w: 230, h: 60,
  detail: {
    subtitle: 'Flask • Port 8005 • /api4',
    job: `
      <p>The <strong>Platform Backend</strong> is a small, focused service for centralized admin configuration. Think of it as the "settings API" for the whole system.</p>
      <h3>What It Does</h3>
      <ul>
        <li>Stores admin configuration sections in MongoDB (template-driven)</li>
        <li>Serves merged config (template defaults + saved overrides)</li>
        <li>On config update, can <strong>dispatch side-effects</strong> to other services via HTTP POST</li>
        <li>Enforces admin access via <code>X-Username</code> / <code>X-User-Id</code> headers</li>
      </ul>
      <h3>ActionDispatcher</h3>
      <p>When a config section has <code>on_update_target</code> and <code>on_update_endpoint</code>, saving triggers an HTTP POST to the target service. Currently only RAG is wired.</p>
    `,
    interfaces: `
      <h3>Admin Config</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/admin_config/config.get — merged template + DB</span></div>
        <div class="endpoint"><span class="method put">PUT</span><span class="path">/api/admin_config/config.section.update — admin only</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/admin_config/access.check?username=</span></div>
      </div>
      <h3>Health</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/health/</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/health/version</span></div>
      </div>
    `,
    architecture: `
      <h3>Structure</h3>
      <ul>
        <li><code>core/app_container.py</code> — DI container, wires Mongo + ActionDispatcher</li>
        <li><code>admin_config/service.py</code> — AdminConfigService: merge, update, dispatch</li>
        <li><code>admin_config/repository/</code> — MongoAdminConfigRepository</li>
        <li><code>admin_config/template.py</code> — config section definitions</li>
        <li><code>admin_config/action_dispatcher.py</code> — HTTP POST to target services</li>
        <li><code>api/flask/</code> — Flask app + endpoint blueprints</li>
      </ul>
      <h3>MongoDB</h3>
      <ul>
        <li>Database: <code>config</code>, Collection: <code>admin_config</code></li>
        <li>Unique index on <code>key</code></li>
      </ul>
    `,
    _endpoints: [
    { method: 'GET', path: '/api/admin_config/config.get', summary: 'merged template + DB' },
    { method: 'PUT', path: '/api/admin_config/config.section.update', summary: 'admin only' },
    { method: 'GET', path: '/api/admin_config/access.check?username=' },
    { method: 'GET', path: '/api/health/' },
    { method: 'GET', path: '/api/health/version' },
  ],
  scheme: {
      nodes: [
        { id: 'ui', label: 'UI /api4', x: 20, y: 62, w: 100, h: 34, color: '#BB86FC' },
        { id: 'platform', label: 'Platform BE', x: 195, y: 62, w: 125, h: 38, color: '#BB86FC' },
        { id: 'mongo', label: 'MongoDB', x: 405, y: 20, w: 100, h: 32, color: '#86EFAC' },
        { id: 'rag', label: 'RAG', x: 405, y: 72, w: 100, h: 32, color: '#BB86FC' },
        { id: 'mas', label: 'MAS (future)', x: 405, y: 124, w: 110, h: 32, color: '#BB86FC' },
      ],
      edges: [
        { from: 'ui', to: 'platform', label: 'HTTP' },
        { from: 'platform', to: 'mongo', label: 'read/write' },
        { from: 'platform', to: 'rag', label: 'ActionDispatcher' },
        { from: 'platform', to: 'mas', label: '(planned)' },
      ],
    },
  },
};
