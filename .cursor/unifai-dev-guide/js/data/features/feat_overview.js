FEATURES.feat_overview = {
  id: 'feat_overview',
  name: 'Overview Dashboards',
  icon: '📊',
  role: 'Stats & monitoring for RAG and Agentic AI',
  type: 'FEATURE',
  x: 1240, y: -140,
  w: 280, h: 56,
  services: ['ui', 'rag', 'mas', 'mongodb', 'qdrant'],
  detail: {
    subtitle: 'RAG Overview + Agentic AI Overview dashboards',
    job: `
      <p>The <strong>Overview Dashboards</strong> give users a quick snapshot of their system health and usage across both RAG and Agentic AI features.</p>
      <h3>RAG Overview (<code>/rag-overview</code>)</h3>
      <ul>
        <li>Pipeline processing status cards (active, connected, last sync)</li>
        <li>Total chunks breakdown: Documents vs Slack (from Qdrant)</li>
        <li>Live activity feed showing recent pipeline events</li>
        <li>Pipeline visualizer showing ingestion progress</li>
      </ul>
      <h3>Agentic AI Overview (<code>/agentic-overview</code>)</h3>
      <ul>
        <li>Stat cards: total Workflows, Active Workflows, Inventory size, Categories</li>
        <li>Resource distribution chart by category</li>
        <li>Most-used and unused workflow lists</li>
        <li>Click a workflow to preview its graph</li>
      </ul>
    `,
    interfaces: `
      <h3>RAG Overview Data (UI → RAG /api1)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/data_sources/data.sources.get — pipeline statuses</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/vector/chunks.counts — Qdrant doc/slack chunk totals</span></div>
      </div>
      <h3>Agentic Overview Data (UI → MAS /api2)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/statistics/stats.get?userId= — workflow counts, sessions, resources</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/blueprints/available.blueprints.resolved.get?userId=</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/sessions/session.user.blueprints.get?userId=</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/resources/resources.list?userId=</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/catalog/categories.list.get</span></div>
      </div>
    `,
    architecture: `
      <h3>RAG Overview</h3>
      <ul>
        <li><code>pages/RagOverview.tsx</code> — React Query with 10–30s refetch intervals</li>
        <li><code>api/pipelines.ts</code> — <code>fetchPipelineMetrics</code>, <code>fetchActivePipelines</code>, <code>fetchQdrantChunksCounts</code></li>
        <li>Components: <code>PipelineInfoCards</code>, <code>PipelineVisualizerWrapper</code>, <code>LiveActivityFeed</code></li>
      </ul>
      <h3>Agentic Overview</h3>
      <ul>
        <li><code>pages/AgenticOverview.tsx</code> — uses <code>hooks/use-agentic-data.ts</code></li>
        <li>Components: <code>StatCard</code>, <code>ResourceDistributionChart</code>, <code>WorkflowList</code></li>
        <li>Stats come from <code>MAS /statistics/stats.get</code> which aggregates MongoDB data</li>
      </ul>
    `,
    flow: [
      { step: 1, label: 'User opens RAG Overview', actor: 'UI → RAG', detail: 'The dashboard fetches pipeline statuses and vector chunk counts from RAG' },
      { step: 2, label: 'RAG gathers data from MongoDB + Qdrant', actor: 'RAG', detail: 'Pipeline stats from MongoDB, chunk counts from Qdrant collections' },
      { step: 3, label: 'Live monitoring displays', actor: 'UI', detail: 'Status cards, chunk breakdowns, and activity feeds auto-refresh every 10–30s' },
      { step: 4, label: 'User opens Agentic AI Overview', actor: 'UI → MAS', detail: 'The dashboard fetches workflow counts, session stats, and resource distribution from MAS' },
      { step: 5, label: 'Charts and stat cards render', actor: 'UI', detail: 'Resource distribution by category, most/least used workflows, and summary stat cards' },
    ],
    codeFlow: [
      { step: 1, label: 'Route /rag-overview → RagOverview.tsx', actor: 'UI', detail: 'React Query hooks fire with 10–30s <code>refetchInterval</code>' },
      { step: 2, label: 'GET /data_sources/data.sources.get', actor: 'UI → RAG', detail: '<code>DataSourceService.list()</code> → enriches each source with pipeline status from <code>pipeline_monitoring.pipelines</code>' },
      { step: 3, label: 'GET /vector/chunks.counts', actor: 'UI → RAG → Qdrant', detail: '<code>QdrantVectorRepository.count()</code> per collection (<code>document_data</code>, <code>slack_data</code>)' },
      { step: 4, label: 'Route /agentic-overview → AgenticOverview.tsx', actor: 'UI', detail: '<code>use-agentic-data.ts</code> hook fetches from MAS' },
      { step: 5, label: 'GET /statistics/stats.get?userId=', actor: 'UI → MAS', detail: '<code>StatisticsService.get_stats()</code> → aggregates workflow counts, active sessions, resources by category from MongoDB' },
    ],
      _endpoints: [
    { method: 'GET', path: '/data_sources/data.sources.get', summary: 'pipeline statuses' },
    { method: 'GET', path: '/vector/chunks.counts', summary: 'Qdrant doc/slack chunk totals' },
    { method: 'GET', path: '/statistics/stats.get?userId=', summary: 'workflow counts, sessions, resources' },
    { method: 'GET', path: '/blueprints/available.blueprints.resolved.get?userId=' },
    { method: 'GET', path: '/sessions/session.user.blueprints.get?userId=' },
    { method: 'GET', path: '/resources/resources.list?userId=' },
    { method: 'GET', path: '/catalog/categories.list.get' },
  ],
  scheme: {
      nodes: [
        { id: 'ui', label: 'UI', x: 20, y: 65, w: 90, h: 36, color: '#BB86FC' },
        { id: 'rag', label: 'RAG', x: 180, y: 22, w: 110, h: 36, color: '#BB86FC' },
        { id: 'mas', label: 'Multi Agent System (MAS)', x: 180, y: 110, w: 110, h: 36, color: '#BB86FC' },
        { id: 'qdrant', label: 'Qdrant', x: 370, y: 5, w: 100, h: 36, color: '#86EFAC' },
        { id: 'mongo', label: 'MongoDB', x: 370, y: 70, w: 120, h: 36, color: '#86EFAC' },
      ],
      edges: [
        { from: 'ui', to: 'rag', label: 'pipeline stats' },
        { from: 'ui', to: 'mas', label: 'workflow stats' },
        { from: 'rag', to: 'qdrant', label: 'chunk counts' },
        { from: 'rag', to: 'mongo', label: 'pipeline data' },
        { from: 'mas', to: 'mongo', label: 'aggregations' },
      ],
    },
    dataModel: `
      <h3>Data Sources (read-only)</h3>
      <p>The Overview dashboards are read-only aggregation views. They query collections owned by other features:</p>
      <div class="data-model-section">
        <div class="data-model-entry">
          <code>pipeline_monitoring.data_sources</code> + <code>pipelines</code>
          <p>RAG Overview reads pipeline statuses and progress. Owned by the RAG Data Pipeline feature.</p>
        </div>
        <div class="data-model-entry">
          <code>Qdrant: document_data</code> + <code>slack_data</code>
          <p>RAG Overview queries collection point counts for the chunk breakdown cards.</p>
        </div>
        <div class="data-model-entry">
          <code>multiagent.blueprints</code> + <code>sessions</code> + <code>resources</code>
          <p>Agentic Overview aggregates blueprint counts, session activity, and resource distribution. Owned by Inventory / Workflows / Chats features.</p>
        </div>
      </div>
    `,
    devScenarios: `
      <h3>Common Dev Tasks</h3>
      <div class="dev-scenario">
        <h4>Add a new stat card to the Agentic Overview</h4>
        <ol>
          <li>Add the aggregation query to <code>StatisticsService.get_stats()</code> in MAS</li>
          <li>Add the stat card component in <code>AgenticOverview.tsx</code></li>
          <li>Wire the data from the <code>use-agentic-data.ts</code> hook</li>
        </ol>
      </div>
      <div class="dev-scenario">
        <h4>Change the auto-refresh interval</h4>
        <ol>
          <li>RAG Overview uses React Query with <code>refetchInterval: 10000–30000</code></li>
          <li>Adjust the interval in the relevant <code>useQuery</code> options in the page component</li>
        </ol>
      </div>
    `,
    dependencies: {
      requires: [
        { featureId: 'feat_rag', reason: 'RAG Overview displays pipeline statuses and vector chunk counts' },
        { featureId: 'feat_workflows', reason: 'Agentic Overview shows workflow counts and usage stats' },
        { featureId: 'feat_inventory', reason: 'Agentic Overview shows resource distribution by category' },
      ],
      requiredBy: [],
    },
  },
};
