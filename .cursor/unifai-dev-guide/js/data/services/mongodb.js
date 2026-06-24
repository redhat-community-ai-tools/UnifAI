SERVICES.mongodb = {
  id: 'mongodb',
  name: 'MongoDB',
  icon: '🍃',
  role: 'Document database',
  type: 'INFRA',
  x: 530, y: 780,
  w: 190, h: 54,
  detail: {
    subtitle: 'Used by RAG, MAS, Identity, Platform, Celery',
    job: `
      <p><strong>MongoDB</strong> is the primary metadata store for the entire system. Every application service uses it for persistence.</p>
      <h3>Databases & Collections</h3>
      <ul>
        <li><strong>RAG</strong>: <code>pipeline_monitoring</code> (pipelines, metrics, errors, logs), <code>data_sources</code> (sources, slack_channels), <code>users</code> (terms_user_approval)</li>
        <li><strong>MAS</strong>: blueprints, sessions, resources, shares, templates (all scoped by <code>identity</code> subdocument)</li>
        <li><strong>Identity</strong>: <code>users.teams</code> (team records with members and group membership)</li>
        <li><strong>Platform</strong>: <code>config.admin_config</code></li>
        <li><strong>Celery</strong>: <code>celery.celery_taskmeta</code> (result backend)</li>
      </ul>
    `,
    interfaces: `<p>Standard MongoDB wire protocol. All services connect via <code>pymongo.MongoClient</code> using <code>get_mongo_url()</code> from <code>global_utils</code>.</p>`,
    architecture: `<p>Deployed as a StatefulSet in Kubernetes. Connection string configured per-service via environment variables (<code>MONGODB_IP</code>, <code>MONGODB_PORT</code>).</p>`,
    scheme: null,
  },
};
