import { formatDate } from '@/features/helpers';
import { api } from '@/http/queryClient';
import type { Channel, EmbedChannel } from '@/types';
import { timeAgo } from '@/utils';
import { useAuth } from '@/contexts/AuthContext';

export interface SystemStats {
  id: number;
  totalChannels: number;
  activeChannels: number;
  totalMessages: number;
  apiCallsCount: number;
  lastSyncAt: string | null;
  totalEmbeddings: number;
  updatedAt: string;
}

export interface PaginationParams {
  cursor?: string;
  limit?: number;
  search_regex?: string;
}

export interface PaginatedChannelsResponse {
  channels: Channel[];
  nextCursor?: string;
  hasMore: boolean;
  total?: number;
}

export async function fetchAvailableSlackChannels(
  types: string,
  pagination?: PaginationParams
): Promise<PaginatedChannelsResponse> {
  const params: any = { types };
  
  if (pagination?.cursor) {
    params.cursor = pagination.cursor;
  }
  
  if (pagination?.limit) {
    params.limit = pagination.limit;
  }

  if (pagination?.search_regex) {
    params.search_regex = pagination.search_regex;
  }

  const { data } = await api.get<PaginatedChannelsResponse>(
    'slack/available.slack.channels.get',
    { params }
  );

  return {
    channels: data.channels.map((c: Channel) => ({
      channel_name: c.channel_name,
      channel_id: c.channel_id,
      is_private: c.is_private,
    })),
    nextCursor: data.nextCursor,
    hasMore: data.hasMore,
    total: data.total,
  };
}

export interface ChannelWithSettings extends Channel {
  settings: {
    dateRange: string;
    communityPrivacy: 'public' | 'private';
    includeThreads: boolean;
    processFileContent: boolean;
  };
}

export interface PipelineEmbedResponse {
  registration_completed: boolean;
  registration: any;
  pipeline_execution: {
    data: {
      status: string;
      message: string;
      pipeline_worker_tasks_submitted: number;
      source_count: number;
    };
    status_code: number;
  };
}

export async function submitSlackChannels(
  channels: ChannelWithSettings[],
  user: string
): Promise<PipelineEmbedResponse> {
  // Transform channels to include settings as metadata
  const enrichedChannels = channels.map(channel => ({
    channel_name: channel.channel_name,
    channel_id: channel.channel_id,
    is_private: channel.is_private,
    // Include settings as additional metadata for backend processing
    metadata: {
      dateRange: channel.settings.dateRange,
      communityPrivacy: channel.settings.communityPrivacy,
      includeThreads: channel.settings.includeThreads,
      processFileContent: channel.settings.processFileContent,
    }
  }));

  const { data } = await api.put<PipelineEmbedResponse>(
    'pipelines/embed',
    { data: enrichedChannels, source_type: 'slack', logged_in_user: user }
  );
  
  return data;
};

export function useSubmitSlackChannels() {
  const { user } = useAuth();
  
  return (channels: ChannelWithSettings[]) => 
    submitSlackChannels(channels, user?.username || 'default');
}

export async function fetchEmbeddedSlackChannels(): Promise<EmbedChannel[]> {
  // Call the new backend endpoint for available data sources with source_type='slack'
  // Using GET request with query parameters as required by the backend @from_query decorator
  const { data } = await api.get<{sources: any[]}>(
    "data_sources/data.sources.get",
    { 
      params: {
        source_type: "slack"
      }
    }
  );
  
  return data.sources.map((item) => ({
    name: item.source_name || '', 
    messages: String(item.pipeline_stats?.documents_retrieved || 0),
    lastSync: timeAgo(item.last_sync_at),
    status: item.status || 'PENDING',
    frequency: "", // No field provided, fallback to empty
    channel_id: item.source_id || '',
    created: formatDate(item.created_at || ''),
    is_private: item.type_data?.is_private || false,
    communityPrivacy: item.type_data?.communityPrivacy || 'public',
    initialTimestamp: item.type_data?.start_timestamp ? formatDate(item.type_data.start_timestamp) : undefined,
  }));
};

export async function deleteSlackChannel(channelId: string): Promise<any> {
  // Call the new backend endpoint for deleting data sources
  const { data } = await api.delete(`data_sources/data.source.delete`, {
    data: { pipeline_id: channelId }
  });
  return data;
};

export async function fetchSystemStats(): Promise<SystemStats> {
  const response = await api.get("/slack/stats");
  return response.data;
};