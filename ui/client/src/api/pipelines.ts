import { api } from '@/http/queryClient';
import { isEmbeddingActivelyProcessing } from '@/features/helpers';

export interface ActivePipeline {
  id: string;
  source_id: string;
  source_name: string;
  source_type: 'slack' | 'document';
  status: string;
  pipeline_stats?: {
    documents_retrieved?: number;
    chunks_generated?: number;
    embeddings_created?: number;
    api_calls?: number;
    processing_time?: number;
  };
  created_at: string;
  last_sync_at?: string;
  type_data?: any;
}

export interface PipelineMetrics {
  totalThroughput: number;
  successRate: number;
  activePipelines: number;
  totalPipelines: number;
}

export interface ConnectedSourcesSummary {
  total: number;
  connected: number;
  byType: Record<string, number>;
}

export interface QdrantChunksCounts {
  total: number;
  slack: number;
  document: number;
}

// Get active pipelines from all sources
export async function fetchActivePipelines(): Promise<ActivePipeline[]> {
  try {
    // Fetch both Slack and Document sources
    const [slackResponse, docsResponse] = await Promise.all([
      api.get<{sources: any[]}>("data_sources/data.sources.get", {
        params: { source_type: "slack" }
      }),
      api.get<{sources: any[]}>("data_sources/data.sources.get", {
        params: { source_type: "document" }
      })
    ]);

    const allSources = [
      ...slackResponse.data.sources.map(source => ({
        ...source,
        source_type: 'slack' as const
      })),
      ...docsResponse.data.sources.map(source => ({
        ...source,
        source_type: 'document' as const
      }))
    ];

    // Filter only active pipelines using the existing helper function
    const activePipelines = allSources.filter(source => 
      isEmbeddingActivelyProcessing(source as any)
    );

    return activePipelines.map(source => ({
      id: source.pipeline_id || source.source_id,
      source_id: source.source_id,
      source_name: source.source_name,
      source_type: source.source_type,
      status: source.status,
      pipeline_stats: source.pipeline_stats,
      created_at: source.created_at,
      last_sync_at: source.last_sync_at,
      type_data: source.type_data,
    }));
  } catch (error) {
    console.error('Failed to fetch active pipelines:', error);
    return [];
  }
}

// Get counts of connected sources by type (slack, document, jira, github)
export async function fetchConnectedSources(): Promise<ConnectedSourcesSummary> {
  const types = ['slack', 'document'] as const;

  const results = await Promise.all(types.map(async (t) => {
    try {
      const res = await api.get<{ sources: any[] }>("data_sources/data.sources.get", { params: { source_type: t } });
      return { type: t, count: Array.isArray(res.data?.sources) ? res.data.sources.length : 0 };
    } catch (_) {
      return { type: t, count: 0 };
    }
  }));

  const byType: Record<string, number> = {};
  let total = 0;
  let connected = 0;
  for (const r of results) {
    byType[r.type] = r.count;
    total += r.count; // treat total as all discovered sources across types
    connected += r.count > 0 ? 1 : 0; // Connected types present
  }

  return { total, connected, byType };
}

// Get pipeline metrics for the dashboard
export async function fetchPipelineMetrics(): Promise<PipelineMetrics> {
  try {
    const activePipelines = await fetchActivePipelines();
    const connected = await fetchConnectedSources();
    
    // Calculate metrics
    const totalThroughput = activePipelines.reduce((sum, pipeline) => {
      return sum + (pipeline.pipeline_stats?.documents_retrieved || 0);
    }, 0);

    const successRate = activePipelines.length > 0 
      ? (activePipelines.filter(p => p.status !== 'FAILED').length / activePipelines.length) * 100
      : 0;

    return {
      totalThroughput,
      successRate,
      activePipelines: activePipelines.length,
      totalPipelines: connected.total,
    };
  } catch (error) {
    console.error('Failed to fetch pipeline metrics:', error);
    return {
      totalThroughput: 0,
      successRate: 0,
      activePipelines: 0,
      totalPipelines: 0,
    };
  }
}

export async function fetchQdrantChunksCounts(): Promise<QdrantChunksCounts> {
  try {
    const res = await api.get<QdrantChunksCounts>("vector/chunks.counts");
    return res.data;
  } catch (error) {
    console.error('Failed to fetch Qdrant chunks counts:', error);
    return { total: 0, slack: 0, document: 0 };
  }
}
