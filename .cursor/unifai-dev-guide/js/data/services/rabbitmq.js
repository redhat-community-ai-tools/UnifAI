SERVICES.rabbitmq = {
  id: 'rabbitmq',
  name: 'RabbitMQ',
  icon: '🐰',
  role: 'Celery message broker',
  type: 'INFRA',
  x: 140, y: 780,
  w: 190, h: 54,
  detail: {
    subtitle: 'AMQP broker for RAG Celery workers',
    job: `
      <p><strong>RabbitMQ</strong> serves as the Celery message broker, carrying task messages from the RAG to Celery workers.</p>
      <h3>Queues</h3>
      <ul>
        <li><code>document_queue</code> — document ingestion tasks</li>
        <li><code>slack_queue</code> — Slack channel ingestion tasks</li>
        <li><code>slack_events_queue</code> — real-time Slack event handling</li>
      </ul>
    `,
    interfaces: `<p>AMQP protocol via Celery. Connection URL from <code>get_rabbitmq_url(user, password)</code> in <code>global_utils</code>.</p>`,
    architecture: `<p>Configured via <code>rabbitmq_ip</code>, <code>rabbitmq_port</code>, <code>broker_user_name</code>, <code>broker_password</code> in <code>AppConfig</code>.</p>`,
    scheme: null,
  },
};
