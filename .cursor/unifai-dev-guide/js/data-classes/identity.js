SERVICE_CLASSES.identity = {
  description: `<p>Identity is a Flask service following the same hexagonal pattern. Core auth logic lives in <code>AuthManager</code>; Redis provides session persistence via <code>RedisKVStore</code> from global_utils. The <strong>teams</strong> domain handles team CRUD, membership, and directory (LDAP/Rover) integration.</p>`,
  layers: [
    {
      name: 'Bootstrap',
      classes: [
        { name: 'create_app()', file: 'bootstrap/flask_app.py', role: 'Flask factory: loads config, builds auth stack, registers endpoints', calls: ['AppConfig', 'build_auth_stack', 'register_all_endpoints', 'global_utils:RequestRules'], calledBy: ['entrypoint'] },
        { name: 'build_auth_stack()', file: 'bootstrap/factories.py', role: 'Builds RedisKVStore + AuthManager + TeamService', calls: ['global_utils:build_redis_client', 'global_utils:RedisKVStore', 'AuthManager', 'TeamService'], calledBy: ['create_app()'] },
      ]
    },
    {
      name: 'Config',
      classes: [
        { name: 'AppConfig', file: 'config/app_config.py', role: 'Identity-specific settings (Keycloak, session, relay, directory, team fields)', calls: ['global_utils:SharedConfig'], calledBy: ['create_app()', 'AuthManager', 'credentials_bp', 'TeamService'] },
        { name: 'LoggingConfig', file: 'config/logging_config.py', role: 'Static log level/format/handler config', calls: [], calledBy: ['create_app()'] },
      ]
    },
    {
      name: 'Core Auth',
      classes: [
        { name: 'AuthManager', file: 'utils/auth_manager.py', role: 'OAuth integration, session store, /api/auth/* routes, refresh logic, admin check', calls: ['AppConfig', 'authlib', 'DevOAuthClient', 'global_utils:RedisKVStore', 'global_utils:identity_session_key'], calledBy: ['build_auth_stack()', 'require_auth'] },
        { name: 'DevOAuthClient', file: 'utils/dev_oauth_client.py', role: 'Dev-only stub for Keycloak: fake redirect, tokens, userinfo', calls: ['flask'], calledBy: ['AuthManager'] },
      ]
    },
    {
      name: 'Teams Domain',
      classes: [
        { name: 'Team', file: 'teams/models.py', role: 'Team aggregate: team_id, name, created_by, members list, timestamps', calls: [], calledBy: ['TeamService', 'MongoTeamRepository'] },
        { name: 'TeamMember', file: 'teams/models.py', role: 'Member model: user or group, with optional cached group_members', calls: [], calledBy: ['Team'] },
        { name: 'TeamService', file: 'teams/service.py', role: 'Team CRUD, membership checks, group member caching', calls: ['MongoTeamRepository', 'DirectoryClient'], calledBy: ['team_routes', 'identity_routes'] },
        { name: 'MongoTeamRepository', file: 'teams/repository/mongo_repository.py', role: 'MongoDB persistence for teams (users.teams collection)', calls: ['pymongo'], calledBy: ['TeamService'] },
      ]
    },
    {
      name: 'Inbound Adapters (Flask Endpoints)',
      classes: [
        { name: 'health_bp', file: 'adapters/inbound/flask/endpoints/health.py', role: 'GET /api/health/ and /api/health/version', calls: ['AppConfig'], calledBy: ['Flask: router'] },
        { name: 'team_routes', file: 'adapters/inbound/flask/endpoints/team_routes.py', role: 'Team CRUD: create, list, get, update, delete', calls: ['TeamService'], calledBy: ['Flask: router'] },
        { name: 'identity_routes', file: 'adapters/inbound/flask/endpoints/identity_routes.py', role: 'Identity resolution and membership checks (called by MAS)', calls: ['TeamService'], calledBy: ['Flask: router'] },
        { name: 'protected_bp', file: 'adapters/inbound/flask/endpoints/protected_routes.py', role: 'GET /api/protected/user.profile (guarded by require_auth)', calls: ['require_auth'], calledBy: ['Flask: router'] },
        { name: 'credentials_bp', file: 'adapters/inbound/flask/endpoints/credentials_callback.py', role: 'GET /api/credentials/callback — OAuth popup relay to MAS', calls: ['AppConfig', 'requests'], calledBy: ['Flask: router'] },
      ]
    },
  ],
  scheme: {
    nodes: [
      { id: 'flask', label: 'Flask App', x: 20, y: 62, w: 110, h: 34, color: '#BB86FC' },
      { id: 'auth_mgr', label: 'AuthManager', x: 205, y: 15, w: 125, h: 34, color: '#BB86FC' },
      { id: 'team_svc', label: 'TeamService', x: 205, y: 68, w: 120, h: 34, color: '#BB86FC' },
      { id: 'config', label: 'AppConfig', x: 205, y: 121, w: 110, h: 34, color: '#A78BFA' },
      { id: 'redis', label: 'RedisKVStore', x: 415, y: 15, w: 125, h: 34, color: '#86EFAC' },
      { id: 'keycloak', label: 'Keycloak', x: 415, y: 68, w: 110, h: 34, color: '#FBBF24' },
      { id: 'mongo', label: 'MongoDB', x: 415, y: 121, w: 110, h: 34, color: '#86EFAC' },
    ],
    edges: [
      { from: 'flask', to: 'auth_mgr', label: 'auth routes' },
      { from: 'flask', to: 'team_svc', label: 'team routes' },
      { from: 'flask', to: 'config', label: 'settings' },
      { from: 'auth_mgr', to: 'redis', label: 'sessions' },
      { from: 'auth_mgr', to: 'keycloak', label: 'OIDC' },
      { from: 'team_svc', to: 'mongo', label: 'teams CRUD' },
    ],
  },
};
