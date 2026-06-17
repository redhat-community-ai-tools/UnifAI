SERVICES.identity = {
  id: 'identity',
  name: 'Identity',
  icon: '🔐',
  role: 'Auth & session service',
  type: 'APP',
  x: 1020, y: 380,
  w: 190, h: 60,
  detail: {
    subtitle: 'Flask • Authlib • Keycloak OIDC • Redis sessions • Team management',
    job: `
      <p>The <strong>Identity</strong> service is the authentication and session bridge between the UI and Keycloak. It implements the OAuth2 Authorization Code flow, manages server-side sessions, and provides <strong>team management</strong> for shared workspaces.</p>
      <h3>Login Flow</h3>
      <ul>
        <li>UI redirects to <code>/api3/auth/login?state=...</code></li>
        <li>Nginx does a <strong>307 redirect</strong> to the Identity host</li>
        <li>Identity redirects to Keycloak's authorize endpoint</li>
        <li>User logs in at Keycloak</li>
        <li>Keycloak calls back to <code>/api/auth/callback</code></li>
        <li>Identity stores tokens in Redis, redirects to UI with <code>?auth=success</code></li>
      </ul>
      <h3>Session Storage</h3>
      <p>Tokens and user profile live in <strong>Redis</strong> under <code>identity:session:&lt;uuid&gt;</code> keys. Only the session ID is stored in the cookie. This supports multi-pod scale-out natively.</p>
      <h3>Team Management</h3>
      <p>Identity owns the <strong>Team</strong> domain: create, update, delete teams and manage membership. Teams can include individual users and LDAP/Rover groups (with cached group members). MAS calls back to Identity to verify team membership for authorization.</p>
      <h3>Credentials Relay</h3>
      <p>Handles OAuth popup callbacks for external tool credentials (e.g. Google) and relays them to the Multi Agent System (MAS) via <code>/api/credentials/callback</code>.</p>
    `,
    interfaces: `
      <h3>Auth Endpoints</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/auth/login — start OIDC flow</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/auth/callback — OAuth callback</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/api/auth/logout — clear session + Keycloak logout</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/auth/user — current user + is_admin</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/api/auth/refresh — refresh access token</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/auth/config — local_auth flag for login page</span></div>
      </div>
      <h3>Team Management</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method post">POST</span><span class="path">/api/teams/team.create — create team</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/teams/teams.list — list teams for user (userId, groupIds)</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/teams/team.get — get team by id</span></div>
        <div class="endpoint"><span class="method put">PUT</span><span class="path">/api/teams/team.update — update name/members</span></div>
        <div class="endpoint"><span class="method delete">DEL</span><span class="path">/api/teams/team.delete — delete team (creator only)</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/teams/identity.resolve — resolve user or team identity metadata</span></div>
      </div>
      <h3>Credentials & Other</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/credentials/callback — OAuth popup relay to MAS</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/health/</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/health/version</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/protected/user.profile — example protected route</span></div>
      </div>
      <h3>Cookie</h3>
      <p><code>session_id</code> only — HTTPOnly, Secure, SameSite=None, configurable lifetime</p>
    `,
    architecture: `
      <h3>Design Pattern: Hexagonal Architecture</h3>
      <p>Identity follows the same <strong>ports and adapters</strong> pattern as the other backend services.</p>
      <h3>How It's Organized</h3>
      <ul>
        <li><strong><code>bootstrap/</code></strong> — App factory (<code>flask_app.py</code>), dependency wiring (<code>factories.py</code>): builds Redis client, AuthManager, registers endpoints</li>
        <li><strong><code>adapters/inbound/flask/endpoints/</code></strong> — HTTP blueprints: health, protected routes, credentials callback, team routes, identity routes</li>
        <li><strong><code>utils/auth_manager.py</code></strong> — Core OAuth logic: Authlib client, session store, auth routes, decorators (<code>require_auth</code>)</li>
        <li><strong><code>teams/</code></strong> — Team domain: <code>models.py</code> (Team, TeamMember), <code>service.py</code> (TeamService), <code>repository/</code> (MongoTeamRepository)</li>
        <li><strong><code>config/app_config.py</code></strong> — Keycloak URL, realm, client credentials, session flags, team/directory settings</li>
      </ul>
      <h3>Key Design Decisions</h3>
      <ul>
        <li>Server-side session store in Redis (no tokens in cookies, keys: <code>identity:session:*</code>)</li>
        <li>Nginx 307 redirect pattern (browser talks to Identity directly)</li>
        <li>State parameter preserves original URL across the OIDC round-trip</li>
        <li>Optional <code>local_auth</code> dev bypass via <code>DevOAuthClient</code></li>
      </ul>
    `,
    _endpoints: [
    { method: 'GET', path: '/api/auth/login', summary: 'start OIDC flow' },
    { method: 'GET', path: '/api/auth/callback', summary: 'OAuth callback' },
    { method: 'POST', path: '/api/auth/logout', summary: 'clear session + Keycloak logout' },
    { method: 'GET', path: '/api/auth/user', summary: 'current user + is_admin' },
    { method: 'POST', path: '/api/auth/refresh', summary: 'refresh access token' },
    { method: 'GET', path: '/api/auth/config', summary: 'local_auth flag for login page' },
    { method: 'POST', path: '/api/teams/team.create', summary: 'create team' },
    { method: 'GET', path: '/api/teams/teams.list', summary: 'list teams for user (userId, groupIds)' },
    { method: 'GET', path: '/api/teams/team.get', summary: 'get team by id' },
    { method: 'PUT', path: '/api/teams/team.update', summary: 'update name/members' },
    { method: 'DEL', path: '/api/teams/team.delete', summary: 'delete team (creator only)' },
    { method: 'GET', path: '/api/teams/identity.resolve', summary: 'resolve user or team identity metadata' },
    { method: 'GET', path: '/api/credentials/callback', summary: 'OAuth popup relay to MAS' },
    { method: 'GET', path: '/api/health/' },
    { method: 'GET', path: '/api/health/version' },
    { method: 'GET', path: '/api/protected/user.profile', summary: 'example protected route' },
  ],
  scheme: {
      nodes: [
        { id: 'browser', label: 'Browser', x: 20, y: 72, w: 100, h: 34, color: '#FBBF24' },
        { id: 'identity', label: 'Identity', x: 195, y: 72, w: 120, h: 38, color: '#BB86FC' },
        { id: 'keycloak', label: 'Keycloak', x: 410, y: 8, w: 105, h: 32, color: '#FBBF24' },
        { id: 'redis', label: 'Redis', x: 410, y: 56, w: 100, h: 32, color: '#86EFAC' },
        { id: 'mongo', label: 'MongoDB', x: 410, y: 104, w: 100, h: 32, color: '#86EFAC' },
        { id: 'mas', label: 'Multi Agent System (MAS)', x: 410, y: 152, w: 100, h: 32, color: '#BB86FC' },
        { id: 'ui', label: 'UI (redirect)', x: 195, y: 165, w: 120, h: 32, color: '#BB86FC' },
      ],
      edges: [
        { from: 'browser', to: 'identity', label: '/auth/login' },
        { from: 'identity', to: 'keycloak', label: 'authorize' },
        { from: 'keycloak', to: 'identity', label: 'callback + code' },
        { from: 'identity', to: 'redis', label: 'session store' },
        { from: 'identity', to: 'mongo', label: 'teams store' },
        { from: 'identity', to: 'mas', label: 'credentials relay' },
        { from: 'identity', to: 'ui', label: '?auth=success' },
      ],
    },
  },
};
