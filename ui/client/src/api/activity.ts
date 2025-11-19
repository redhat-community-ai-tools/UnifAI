import { api } from '@/http/queryClient';
import type { ActivityItem } from '@shared/schema';

export interface FetchActivitiesParams {
  sources?: Array<'slack' | 'document'>;
  sinceHours?: number; // default 24
  limit?: number; // optional cap
}

function withinLastHours(dateStr: string | undefined, hours: number): boolean {
  if (!dateStr) return false;
  const ts = new Date(dateStr).getTime();
  if (Number.isNaN(ts)) return false;
  const cutoff = Date.now() - hours * 3600 * 1000;
  return ts >= cutoff;
}

export async function fetchRecentActivities(params: FetchActivitiesParams = {}): Promise<ActivityItem[]> {
  const { sources = ['slack', 'document'], sinceHours = 24, limit } = params;

  // Use existing data sources endpoint for all requested source types
  const requests: Promise<{ data: { sources: any[] } }>[] = sources.map((sourceType) =>
    api.get<{ sources: any[] }>('data_sources/data.sources.get', { params: { source_type: sourceType } })
  );

  const responses = await Promise.all(requests);
  const all = responses.flatMap(r => r.data.sources || []);

  const completedInWindow = all
    .filter((s) => (s.status === 'DONE' || s.pipeline_stats?.status === 'DONE') && withinLastHours(s.last_sync_at, sinceHours))
    .sort((a, b) => new Date(b.last_sync_at || 0).getTime() - new Date(a.last_sync_at || 0).getTime());

  const activities: ActivityItem[] = completedInWindow.map((s, idx) => ({
    id: `${s.source_id || s.pipeline_id || idx}-${s.last_sync_at || ''}`,
    type: (s.source_type === 'slack' || (s.pipeline_id && String(s.pipeline_id).includes('slack'))) ? 'slack' : 'document',
    title: `${s.source_name || 'Source'} pipeline completed`,
    description: `Processed ${s.pipeline_stats?.documents_retrieved ?? 0} items; embeddings ${s.pipeline_stats?.embeddings_created ?? 0}.`,
    status: 'complete',
    source: s.source_name || s.source_type,
    destination: 'Vector DB',
    metadata: s.pipeline_stats || {},
    timestamp: s.last_sync_at || s.created_at || new Date().toISOString(),
  } as ActivityItem));

  return typeof limit === 'number' ? activities.slice(0, limit) : activities;
}


