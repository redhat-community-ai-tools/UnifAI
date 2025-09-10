import {
   ActivityLogType,
   DataSourceStatus,
   DataSourceType,
   PipelineStatus,
   UserRole
} from '@/constants/pipelineStatus';

export interface Pipeline {
  id: string;
  name: string;
  status: PipelineStatus;
  progress: number;
  source: DataSourceType;
  projectId: string;
}

export interface DataSource {
  id: string;
  name: string;
  type: DataSourceType;
  status: DataSourceStatus;
  lastSync?: string;
}

export interface ActivityLog {
  id: string;
  type: ActivityLogType;
  title: string;
  description: string;
  time: string;
  projectId: string;
  sourceType: DataSourceType;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatar?: string;
}

export interface ProjectStats {
  totalDocuments: number;
  processedDocuments: number;
  vectorCount: number;
  sourceDistribution: {
    [key in DataSourceType]?: {
      count: number;
      percentage: number;
    };
  };
}

export interface Channel {
  channel_name: string;
  channel_id: string;
  is_private: boolean;
}

export interface EmbedChannel {
  name: string;
  messages: string;
  lastSync: string;
  status: PipelineStatus;
  frequency: string;
  channel_id: string;
  created: string;
  is_private: boolean;
}
export interface Document {
  _id: string;
  pipeline_id: string;
  created_at: string;
  last_updated: string;
  source_id: string;
  source_name: string;
  source_type: string;
  duplication_notice?: {
    duplicate_uploaded_name: string;
    existing_name: string;
    duplicate_at: string;
  };
  type_data: {
    file_type: string;
    doc_path: string;
    page_count: number;
    full_text: string;
    file_size: string;
    content_md5: string;
  };
  upload_by: string;
  pipeline_stats: {
    status: PipelineStatus;
    documents_retrieved: number;
    chunks_generated: number;
    embeddings_created: number;
    api_calls: number;
    processing_time: number;
  };
  status: PipelineStatus;
}
