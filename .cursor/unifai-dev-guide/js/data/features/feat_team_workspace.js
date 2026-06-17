FEATURES.feat_team_workspace = {
  id: 'feat_team_workspace',
  name: 'Team Workspace',
  icon: '👥',
  role: 'Shared team identity & real-time collaboration',
  type: 'FEATURE',
  x: 1560, y: -140,
  w: 260, h: 56,
  services: ['ui', 'identity', 'mas', 'mongodb', 'redis'],
  detail: {
    subtitle: 'Shared ownership namespace with collaboration, edit locks, and presence',
    job: `
      <p>The <strong>Team Workspace</strong> lets groups of users collaborate on agentic AI assets under a shared team identity. All resources, blueprints, and sessions are scoped to the team instead of individual users.</p>
      <h3>Private vs Team Mode</h3>
      <ul>
        <li><strong>Private workspace</strong> — data keyed by <code>identityType: "user"</code>, <code>userId: &lt;username&gt;</code></li>
        <li><strong>Team workspace</strong> — data keyed by <code>identityType: "team"</code>, <code>userId: &lt;team_id&gt;</code></li>
      </ul>
      <h3>What the User Sees</h3>
      <ul>
        <li>A <strong>Private / Team toggle</strong> in the sidebar with a team dropdown</li>
        <li>A <strong>"Create a new team"</strong> button that opens the Team Settings modal</li>
        <li>Team dashboard with member count, stats, and leaderboard</li>
        <li><strong>Edit locks</strong> — only one team member can edit a resource or blueprint at a time</li>
        <li><strong>Collaboration Hub</strong> — real-time session presence, typing indicators, multi-user sessions</li>
        <li><strong>Share to Team</strong> — instantly clone resources/blueprints into the team namespace</li>
      </ul>
      <h3>How It Works</h3>
      <p>Teams are stored in the <strong>Identity</strong> service. When the user switches to team mode, the UI sets <code>userId = team.id</code> and <code>identityType = "team"</code> on all Multi Agent System (MAS) calls. MAS verifies team membership via the Identity service before allowing access.</p>
    `,
    interfaces: `
      <h3>Identity — Team CRUD (/api3)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method post">POST</span><span class="path">/api/teams/team.create — create team</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/teams/teams.list — list teams for user</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/teams/team.get — get team by id</span></div>
        <div class="endpoint"><span class="method put">PUT</span><span class="path">/api/teams/team.update — update name/members</span></div>
        <div class="endpoint"><span class="method delete">DEL</span><span class="path">/api/teams/team.delete — delete team (creator only)</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/api/teams/identity.resolve — resolve user or team metadata</span></div>
      </div>
      <h3>MAS — Identity-Scoped Data (/api2)</h3>
      <p>All MAS endpoints accept <code>userId</code>, <code>identityType</code> ("user" | "team"), and <code>displayName</code>. Protected by <code>@with_require_identity_authorization</code>.</p>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/resources/resources.list?userId=&identityType=team</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/available.blueprints.resolved.get?userId=&identityType=team</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.user.list?userId=&identityType=team</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/shares/share.to_team — clone resource/blueprint into team</span></div>
        <div class="endpoint"><span class="method delete">DEL</span><span class="path">/workspace/workspace.cleanup — delete all data for an identity</span></div>
      </div>
      <h3>MAS — Collaboration (requires Redis)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/session.join — join session presence</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/session.leave — leave session</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/session.heartbeat — refresh presence</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/collaboration/session.participants — who is in a session</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/edit_lock.acquire — acquire edit lock</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/collaboration/edit_lock.release — release edit lock</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/collaboration/edit_lock.statuses — batch lock status query</span></div>
      </div>
    `,
    architecture: `
      <h3>Identity Model</h3>
      <p>The <code>Identity</code> model is a shared concept across all MAS data. Every resource, blueprint, and session stores an <code>identity</code> subdocument:</p>
      <ul>
        <li><code>Identity { type: "user"|"team", id: string, display_name: string }</code></li>
      </ul>
      <p>When in team mode, <code>type = "team"</code> and <code>id = team_id</code>. All queries filter by this identity.</p>
      <h3>Team Authorization</h3>
      <p>The <code>@with_require_identity_authorization</code> decorator on MAS endpoints verifies:</p>
      <ul>
        <li><strong>User identity</strong> — <code>userId</code> must match <code>X-Authenticated-User</code> header</li>
        <li><strong>Team identity</strong> — authenticated user must be a team member (verified via <code>IdentityProvider</code> port → Identity service HTTP call)</li>
      </ul>
      <h3>Collaboration Infrastructure (Redis)</h3>
      <ul>
        <li><strong>Session presence</strong> — join/leave/heartbeat with configurable TTL (default 300s)</li>
        <li><strong>Edit locks</strong> — Redis-backed locks with TTL (~180s) and heartbeat renewal. Only one team member can edit a resource/blueprint at a time</li>
        <li><strong>Typing indicators</strong> — real-time typing state visible to other session participants</li>
      </ul>
      <h3>Credential Separation</h3>
      <p>Team sessions use per-member OAuth credentials. The UI sends <code>credentialUserId</code> (the real user) separately from the workspace <code>userId</code> (the team). This ensures each member's credentials are used for external service calls.</p>
      <h3>Team Delete Cascade</h3>
      <p>Deleting a team triggers: (1) Delete team record in Identity → (2) <code>DELETE /workspace/workspace.cleanup</code> in MAS to purge all team-owned resources, blueprints, and sessions.</p>
      <h3>Key Files</h3>
      <ul>
        <li><code>shared-resources/identity/teams/</code> — Team model, service, repository</li>
        <li><code>multi-agent/lib/mas/core/identity/</code> — Identity model and ports</li>
        <li><code>multi-agent/adapters/inbound/flask/decorators.py</code> — Authorization decorator</li>
        <li><code>multi-agent/adapters/outbound/identity/</code> — IdentityProvider adapters</li>
        <li><code>multi-agent/lib/mas/collaboration/</code> — Collaboration service</li>
        <li><code>ui/client/src/contexts/ViewContext.tsx</code> — Private/Team view toggle</li>
        <li><code>ui/client/src/hooks/use-workspace-identity.ts</code> — Identity param source of truth</li>
        <li><code>ui/client/src/components/teams/TeamSettingsModal.tsx</code> — Team CRUD UI</li>
      </ul>
    `,
    flow: [
      { step: 1, label: 'User creates a team', actor: 'UI → Identity', detail: 'Opens Team Settings modal, sets a name, adds members (users or LDAP groups). Identity stores the team in MongoDB.' },
      { step: 2, label: 'User switches to team mode', actor: 'UI', detail: 'Clicks the "Team" toggle in the sidebar and selects a team from the dropdown. ViewContext sets viewMode to "team".' },
      { step: 3, label: 'UI switches identity context', actor: 'UI', detail: 'useWorkspaceIdentity() now returns userId=team.id, identityType="team". All API calls use these params.' },
      { step: 4, label: 'MAS verifies team membership', actor: 'MAS → Identity', detail: 'The @with_require_identity_authorization decorator calls IdentityProvider.is_member() which queries the Identity service.' },
      { step: 5, label: 'Team-scoped data loads', actor: 'MAS → MongoDB', detail: 'Resources, blueprints, and sessions are filtered by identity { type: "team", id: team_id }.' },
      { step: 6, label: 'Team member edits a resource', actor: 'UI → MAS → Redis', detail: 'An edit lock is acquired in Redis. Other team members see the lock indicator and cannot edit simultaneously.' },
      { step: 7, label: 'Team members collaborate on a session', actor: 'UI → MAS → Redis', detail: 'Members join session presence, see typing indicators, and observe real-time execution in the Collaboration Hub.' },
      { step: 8, label: 'User shares to team', actor: 'UI → MAS', detail: 'Share-to-team clones the resource/blueprint into the team namespace (no invite flow). contributed_by tracks the original author.' },
    ],
    codeFlow: [
      { step: 1, label: 'POST /api/teams/team.create', actor: 'UI → Identity', detail: '<code>TeamService.create_team()</code> → <code>MongoTeamRepository.insert()</code> with creator as first member' },
      { step: 2, label: 'ViewContext.setViewMode("team")', actor: 'UI', detail: '<code>ViewContext.tsx</code> → sets <code>viewMode</code>, <code>selectedTeam</code>; fetched via <code>GET /api/teams/teams.list</code>' },
      { step: 3, label: 'useWorkspaceIdentity() recalculates', actor: 'UI', detail: '<code>use-workspace-identity.ts</code> → <code>useMemo</code> returns <code>{ userId: team.id, identityType: "team", credentialUserId: user.username }</code>' },
      { step: 4, label: '@with_require_identity_authorization', actor: 'MAS', detail: '<code>decorators.py</code> → for team identity, calls <code>IdentityProvider.is_member(team_id, X-Authenticated-User)</code> → <code>IdentityPodProvider</code> HTTP to Identity' },
      { step: 5, label: 'GET /resources/resources.list?identityType=team', actor: 'UI → MAS', detail: '<code>ResourceService.list(identity)</code> → <code>MongoResourceRepository.find_by_identity()</code> filters by <code>identity.type + identity.id</code>' },
      { step: 6, label: 'POST /collaboration/edit_lock.acquire', actor: 'UI → MAS', detail: '<code>CollaborationService.acquire_lock()</code> → Redis SET with TTL ~180s; UI polls <code>edit_lock.statuses</code> via <code>use-team-edit-lock-poll.ts</code>' },
      { step: 7, label: 'POST /collaboration/session.join', actor: 'UI → MAS', detail: '<code>CollaborationService.join_session()</code> → Redis presence tracking; <code>CollaborationHubView.tsx</code> renders participants + typing indicators' },
      { step: 8, label: 'POST /shares/share.to_team', actor: 'UI → MAS', detail: '<code>ShareService.share_to_team()</code> → <code>ShareCloner.clone()</code> copies resource/blueprint with target identity = team; sets <code>contributed_by</code> field' },
    ],
      _endpoints: [
    { method: 'POST', path: '/api/teams/team.create', summary: 'create team' },
    { method: 'GET', path: '/api/teams/teams.list', summary: 'list teams for user' },
    { method: 'GET', path: '/api/teams/team.get', summary: 'get team by id' },
    { method: 'PUT', path: '/api/teams/team.update', summary: 'update name/members' },
    { method: 'DEL', path: '/api/teams/team.delete', summary: 'delete team (creator only)' },
    { method: 'GET', path: '/api/teams/identity.resolve', summary: 'resolve user or team metadata' },
    { method: 'GET', path: '/resources/resources.list?userId=&identityType=team' },
    { method: 'GET', path: '/blueprints/available.blueprints.resolved.get?userId=&identityType=team' },
    { method: 'GET', path: '/sessions/session.user.list?userId=&identityType=team' },
    { method: 'POST', path: '/shares/share.to_team', summary: 'clone resource/blueprint into team' },
    { method: 'DEL', path: '/workspace/workspace.cleanup', summary: 'delete all data for an identity' },
    { method: 'POST', path: '/collaboration/session.join', summary: 'join session presence' },
    { method: 'POST', path: '/collaboration/session.leave', summary: 'leave session' },
    { method: 'POST', path: '/collaboration/session.heartbeat', summary: 'refresh presence' },
    { method: 'GET', path: '/collaboration/session.participants', summary: 'who is in a session' },
    { method: 'POST', path: '/collaboration/edit_lock.acquire', summary: 'acquire edit lock' },
    { method: 'POST', path: '/collaboration/edit_lock.release', summary: 'release edit lock' },
    { method: 'GET', path: '/collaboration/edit_lock.statuses', summary: 'batch lock status query' },
  ],
  scheme: {
      nodes: [
        { id: 'ui', label: 'UI', x: 20, y: 72, w: 90, h: 36, color: '#BB86FC' },
        { id: 'identity', label: 'Identity', x: 180, y: 20, w: 110, h: 36, color: '#BB86FC' },
        { id: 'mas', label: 'Multi Agent System (MAS)', x: 180, y: 125, w: 110, h: 36, color: '#BB86FC' },
        { id: 'mongo', label: 'MongoDB', x: 370, y: 55, w: 120, h: 36, color: '#86EFAC' },
        { id: 'redis', label: 'Redis', x: 370, y: 130, w: 100, h: 36, color: '#86EFAC' },
      ],
      edges: [
        { from: 'ui', to: 'identity', label: 'team CRUD' },
        { from: 'ui', to: 'mas', label: 'scoped data' },
        { from: 'identity', to: 'mongo', label: 'teams store' },
        { from: 'mas', to: 'mongo', label: 'identity filter' },
        { from: 'mas', to: 'redis', label: 'locks & presence' },
      ],
    },
    dataModel: `
      <h3>MongoDB Collections</h3>
      <div class="data-model-section">
        <div class="data-model-entry">
          <code>identity.teams</code>
          <p>Team records stored in the Identity service database.</p>
          <div class="data-model-fields">Key fields: <code>name</code>, <code>creator</code>, <code>members[]</code> (username + role), <code>created_at</code></div>
        </div>
        <div class="data-model-entry">
          <code>multiagent.*</code> <span style="color:var(--text-muted)">(identity-scoped)</span>
          <p>All MAS collections (resources, blueprints, sessions) are filtered by <code>identity.type</code> + <code>identity.id</code>. Team data uses <code>type: "team"</code>.</p>
        </div>
      </div>
      <h3>Redis Keys</h3>
      <div class="data-model-section">
        <div class="data-model-entry">
          <code>edit_lock:{entityType}:{entityId}</code>
          <p>Distributed edit locks with ~180s TTL, renewed by heartbeat. Prevents concurrent edits.</p>
        </div>
        <div class="data-model-entry">
          <code>presence:{sessionId}:{userId}</code>
          <p>Session presence tracking with ~300s TTL. Tracks who is currently viewing a session.</p>
        </div>
      </div>
    `,
    devScenarios: `
      <h3>Common Dev Tasks</h3>
      <div class="dev-scenario">
        <h4>Add a new team-scoped feature</h4>
        <ol>
          <li>Ensure your endpoint accepts <code>userId</code> + <code>identityType</code> parameters</li>
          <li>Add <code>@with_require_identity_authorization</code> decorator for team access checks</li>
          <li>Filter queries by the <code>identity</code> subdocument — same pattern as existing endpoints</li>
        </ol>
      </div>
      <div class="dev-scenario">
        <h4>Debug edit lock issues</h4>
        <ol>
          <li>Check Redis for the lock key: <code>edit_lock:{type}:{id}</code></li>
          <li>Lock TTL is ~180s — if a user's browser closes, the lock auto-expires</li>
          <li>The UI polls <code>edit_lock.statuses</code> via <code>use-team-edit-lock-poll.ts</code></li>
        </ol>
      </div>
      <div class="dev-scenario">
        <h4>Test team authorization locally</h4>
        <ol>
          <li>Create a team via Identity API: <code>POST /api/teams/team.create</code></li>
          <li>Set the UI's ViewContext to team mode with the team ID</li>
          <li>Verify MAS calls <code>IdentityProvider.is_member()</code> on each request</li>
        </ol>
      </div>
    `,
    dependencies: {
      requires: [
        { featureId: 'feat_inventory', reason: 'Team workspace scopes Inventory resources to team identity' },
        { featureId: 'feat_workflows', reason: 'Team workspace scopes Workflows and blueprints to team identity' },
        { featureId: 'feat_chats', reason: 'Team collaboration features (presence, typing) work in Chat sessions' },
      ],
      requiredBy: [],
    },
  },
};
