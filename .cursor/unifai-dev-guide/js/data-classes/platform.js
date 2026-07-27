SERVICE_CLASSES.platform = {
  description: `<p>Platform Backend is a small admin config service. It uses <code>AppContainer</code> (singleton) to wire MongoDB + <code>ActionDispatcher</code> + <code>AdminConfigService</code>.</p>`,
  layers: [
    {
      name: 'Bootstrap',
      classes: [
        { name: 'AppContainer', file: 'core/app_container.py', role: 'Singleton DI: MongoClient, repos, ActionDispatcher, AdminConfigService', calls: ['MongoAdminConfigRepository', 'ActionDispatcher', 'AdminConfigService', 'AppConfig'], calledBy: ['entrypoint'] },
      ]
    },
    {
      name: 'Config',
      classes: [
        { name: 'AppConfig', file: 'config/app_config.py', role: 'Platform settings (Mongo names, rag_url, admin_users, port)', calls: ['global_utils:SharedConfig'], calledBy: ['AppContainer'] },
      ]
    },
    {
      name: 'Admin Config Domain',
      classes: [
        { name: 'AdminConfigService', file: 'admin_config/service.py', role: 'Merge template + DB; validate/update sections; optional dispatch', calls: ['AdminConfigRepository', 'ActionDispatcher', 'AdminConfigTemplate'], calledBy: ['AppContainer', 'HTTP: /admin_config/'] },
        { name: 'ActionDispatcher', file: 'admin_config/action_dispatcher.py', role: 'POST to target services after config save', calls: ['requests'], calledBy: ['AdminConfigService'] },
        { name: 'AdminConfigRepository (ABC)', file: 'admin_config/repository/repository.py', role: 'Port: get(key)/set(entry) for config entries', calls: [], calledBy: ['MongoAdminConfigRepository', 'AdminConfigService'] },
        { name: 'MongoAdminConfigRepository', file: 'admin_config/repository/mongo_repository.py', role: 'Mongo implementation with unique index on key', calls: ['pymongo'], calledBy: ['AppContainer'] },
      ]
    },
    {
      name: 'Models',
      classes: [
        { name: 'AdminConfigTemplate', file: 'admin_config/models.py', role: 'Static template tree: categories → sections → fields', calls: [], calledBy: ['AdminConfigService', 'template.py'] },
        { name: 'AdminConfigEntry', file: 'admin_config/models.py', role: 'Mongo document: section key + value dict + timestamp', calls: [], calledBy: ['AdminConfigRepository', 'AdminConfigService'] },
        { name: 'AdminConfigResponse', file: 'admin_config/models.py', role: 'Root DTO: merged template + stored values for API', calls: ['CategoryValue', 'SectionValue', 'FieldValue'], calledBy: ['AdminConfigService'] },
        { name: 'FieldDefinition', file: 'admin_config/models.py', role: 'Schema for one configurable field', calls: [], calledBy: ['SectionDefinition'] },
        { name: 'SectionDefinition', file: 'admin_config/models.py', role: 'Group of fields + optional on_update hooks', calls: ['FieldDefinition'], calledBy: ['CategoryDefinition'] },
      ]
    },
  ],
  scheme: {
    nodes: [
      { id: 'http', label: 'Flask HTTP', x: 20, y: 55, w: 110, h: 34, color: '#BB86FC' },
      { id: 'container', label: 'AppContainer', x: 200, y: 20, w: 130, h: 34, color: '#A78BFA' },
      { id: 'svc', label: 'ConfigService', x: 200, y: 78, w: 130, h: 34, color: '#BB86FC' },
      { id: 'mongo', label: 'MongoRepo', x: 410, y: 20, w: 110, h: 34, color: '#86EFAC' },
      { id: 'dispatcher', label: 'Dispatcher', x: 410, y: 78, w: 110, h: 34, color: '#38BDF8' },
      { id: 'rag', label: 'RAG', x: 410, y: 136, w: 100, h: 34, color: '#BB86FC' },
    ],
    edges: [
      { from: 'http', to: 'container', label: 'resolve' },
      { from: 'container', to: 'svc', label: 'provides' },
      { from: 'svc', to: 'mongo', label: 'get/set' },
      { from: 'svc', to: 'dispatcher', label: 'on_update' },
      { from: 'dispatcher', to: 'rag', label: 'HTTP POST' },
    ],
  },
};
