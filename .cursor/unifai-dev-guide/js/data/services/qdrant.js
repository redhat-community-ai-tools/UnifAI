SERVICES.qdrant = {
  id: 'qdrant',
  name: 'Qdrant',
  icon: '🔍',
  role: 'Vector database',
  type: 'INFRA',
  x: -100, y: 780,
  w: 190, h: 54,
  detail: {
    subtitle: 'Used by RAG only • Cosine similarity',
    job: `
      <p><strong>Qdrant</strong> stores vector embeddings for semantic search. RAG creates collections per source type (e.g., <code>document_data</code>, <code>slack_data</code>).</p>
      <h3>Operations</h3>
      <ul>
        <li><strong>Upsert</strong> — batches of 100 points (vector + text + metadata)</li>
        <li><strong>Query</strong> — vector similarity search with optional metadata filters</li>
        <li><strong>Delete</strong> — by point IDs or source_id filter</li>
        <li><strong>Count</strong> — exact or approximate collection stats</li>
      </ul>
    `,
    interfaces: `<p>Qdrant REST/gRPC API via the <code>qdrant-client</code> Python SDK. Wrapped by <code>QdrantVectorRepository</code> implementing the <code>VectorRepository</code> port.</p>`,
    architecture: `<p>Collections are auto-created with cosine distance metric and payload indexes on <code>metadata.source_type</code>, <code>metadata.channel_name</code>, <code>metadata.source_id</code>.</p>`,
    scheme: null,
  },
};
