/*
 * Service-to-service connections rendered on the map.
 * Loaded AFTER all service files so that referenced IDs exist.
 */

EDGES.push(
  { from: 'browser',  to: 'ui',              label: 'HTTP' },
  { from: 'ui',       to: 'rag',             label: '/api1' },
  { from: 'ui',       to: 'mas',             label: '/api2' },
  { from: 'ui',       to: 'identity',        label: '/api3' },
  { from: 'ui',       to: 'platform',        label: '/api4' },
  { from: 'identity', to: 'keycloak',        label: 'OIDC' },
  { from: 'identity', to: 'redis',           label: 'sessions' },
  { from: 'identity', to: 'mongodb',        label: 'teams' },
  { from: 'mas',      to: 'identity',       label: 'team auth' },
  { from: 'mas',      to: 'rag',            label: 'query.match' },
  { from: 'slack',    to: 'rag',             label: 'paused', style: 'dashed' },
  { from: 'rag',      to: 'rabbitmq',        label: 'enqueue' },
  { from: 'rag',      to: 'mongodb',         label: 'metadata' },
  { from: 'rag',      to: 'qdrant',          label: 'vectors' },
  { from: 'celery',   to: 'rabbitmq',        label: 'consume' },
  { from: 'celery',   to: 'mongodb',         label: 'status' },
  { from: 'celery',   to: 'qdrant',          label: 'upsert' },
  { from: 'mas',      to: 'mongodb',         label: 'sessions' },
  { from: 'mas',      to: 'redis',           label: 'streams' },
  { from: 'mas',      to: 'temporal',        label: 'submit WF' },
  { from: 'mas',      to: 'temporal_worker', label: 'shared codebase', style: 'codebase' },
  { from: 'temporal_worker', to: 'temporal',  label: 'poll queue' },
  { from: 'temporal_worker', to: 'redis',    label: 'stream events' },
  { from: 'temporal_worker', to: 'mongodb',  label: 'session state' },
  { from: 'platform', to: 'mongodb',         label: 'config' },
);
