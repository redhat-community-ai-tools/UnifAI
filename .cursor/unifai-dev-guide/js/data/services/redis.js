SERVICES.redis = {
  id: 'redis',
  name: 'Redis',
  icon: '🟥',
  role: 'Streaming, sessions & collaboration',
  type: 'INFRA',
  x: 780, y: 780,
  w: 200, h: 54,
  detail: {
    subtitle: 'Used by MAS (Streams + Collaboration) and Identity (sessions)',
    job: `
      <p><strong>Redis</strong> serves three roles: cross-process event streaming for MAS sessions via Redis Streams, server-side session storage for the Identity service, and <strong>team collaboration</strong> infrastructure for MAS.</p>
      <p>For MAS, Redis is essential in the default Background (Temporal) execution mode — it carries streaming events from distributed workers to the UI via Redis Streams. Without Redis, MAS falls back to in-process queues (foreground single-worker only). For Identity, Redis is required for session persistence. For team collaboration features, Redis is required.</p>
      <h3>MAS Streaming Operations</h3>
      <ul>
        <li><code>XADD</code> — write session events to a per-session stream</li>
        <li><code>XREAD</code> — blocking read for event consumers</li>
        <li><code>SADD</code> / <code>SMEMBERS</code> — track active sessions</li>
        <li><code>EXPIRE</code> — TTL on session streams</li>
      </ul>
      <h3>Team Collaboration Operations</h3>
      <ul>
        <li><strong>Session presence</strong> — join/leave/heartbeat tracking with configurable TTL (default 300s)</li>
        <li><strong>Edit locks</strong> — per-resource and per-blueprint locks with TTL (~180s) and heartbeat renewal</li>
        <li><strong>Typing indicators</strong> — real-time typing state for team session participants</li>
        <li><strong>Team active-session index</strong> — tracks which sessions have active participants</li>
      </ul>
      <h3>Identity Session Operations</h3>
      <ul>
        <li><code>SET</code> / <code>GET</code> — store and retrieve user sessions (<code>identity:session:*</code> keys)</li>
        <li><code>DEL</code> — clear sessions on logout</li>
      </ul>
    `,
    interfaces: `<p>Redis protocol via <code>redis-py</code>. Streams API (<code>XADD</code>, <code>XREAD</code>, <code>XINFO</code>). Connection from <code>get_redis_url()</code>.</p>`,
    architecture: `<p>Tuning: <code>redis_stream_ttl</code>, <code>redis_stream_block_ms</code>, <code>redis_stream_batch_size</code> in MAS <code>AppConfig</code>.</p>`,
    scheme: null,
  },
};
