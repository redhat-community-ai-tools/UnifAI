SERVICES.keycloak = {
  id: 'keycloak',
  name: 'Keycloak',
  icon: '🏰',
  role: 'Identity provider (OIDC)',
  type: 'EXTERNAL',
  x: 1020, y: 190,
  w: 210, h: 54,
  detail: {
    subtitle: 'External IdP • OAuth2 / OpenID Connect',
    job: `
      <p><strong>Keycloak</strong> is the external identity provider. It manages user accounts, authentication, and SSO across applications.</p>
      <ul>
        <li>Hosts the login page (user never types credentials into UnifAI directly)</li>
        <li>Issues OAuth2 access tokens and refresh tokens</li>
        <li>Provides OIDC discovery at <code>/realms/{realm}/.well-known/openid-configuration</code></li>
      </ul>
    `,
    interfaces: `
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/.well-known/openid-configuration</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/protocol/openid-connect/auth — authorize</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/protocol/openid-connect/token — exchange code / refresh</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/protocol/openid-connect/userinfo</span></div>
      </div>
    `,
    architecture: `<p>Deployed externally. Identity service connects via Authlib OAuth client with <code>keycloak_base_url</code> and <code>keycloak_realm</code> config.</p>`,
    _endpoints: [
    { method: 'GET', path: '/.well-known/openid-configuration' },
    { method: 'GET', path: '/protocol/openid-connect/auth', summary: 'authorize' },
    { method: 'POST', path: '/protocol/openid-connect/token', summary: 'exchange code / refresh' },
    { method: 'GET', path: '/protocol/openid-connect/userinfo' },
  ],
  scheme: null,
  },
};
