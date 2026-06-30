SERVICES.slack = {
  id: 'slack',
  name: 'Slack API',
  icon: '💬',
  role: 'Paused (AIA process)',
  type: 'DISABLED',
  x: 10, y: 200,
  w: 200, h: 54,
  detail: {
    subtitle: 'External • Slack Web API + Events API',
    job: `
      <p><strong>Slack</strong> integration works in two directions:</p>
      <ul>
        <li><strong>Outbound</strong> — RAG calls the Slack Web API to fetch channels, message history, and user info</li>
        <li><strong>Inbound</strong> — Slack's Events API sends webhooks to <code>POST /api/slack/events</code> for real-time updates</li>
      </ul>
    `,
    interfaces: `
      <h3>Slack Web API (called by RAG)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">auth.test — verify bot token</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">conversations.list — list channels</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">conversations.history — fetch messages</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">users.info — user details</span></div>
      </div>
    `,
    architecture: `<p>Authentication via bot token and user token stored in RAG config (<code>slack_bot_token</code>, <code>slack_user_token</code>).</p>`,
    _endpoints: [
    { method: 'GET', path: 'auth.test', summary: 'verify bot token' },
    { method: 'GET', path: 'conversations.list', summary: 'list channels' },
    { method: 'GET', path: 'conversations.history', summary: 'fetch messages' },
    { method: 'GET', path: 'users.info', summary: 'user details' },
  ],
  scheme: null,
  },
};
