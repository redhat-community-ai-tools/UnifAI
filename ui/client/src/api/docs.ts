import { api } from '@/http/queryClient';
import type { Document } from '@/types';

export async function fetchDocuments(): Promise<Document[]> {
  // Call the new backend endpoint for available data sources with source_type='document'
  // Using GET request with query parameters as required by the backend @from_query decorator
  const response = await api.get<{sources: any}>(
    "data_sources/data.sources.get",
    {
      params: {
        source_type: "document"
      }
    }
  );
  return response.data.sources;
};

export async function uploadDocs(files: {name: string, content: string}[]): Promise<any> {
    const uploaded = await api.post<any>(
        'docs/upload',
        { files: files }
      );
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

export async function embedDocs(docs: {source_name: string, tags?: string[]}[], user: string): Promise<PipelineEmbedResponse> {
    const embedded = await api.put<PipelineEmbedResponse>(
      'pipelines/embed',
      {
        data: docs,
        source_type: 'document',
        logged_in_user: user
      }
    );
    return embedded.data;
}

export async function deleteDoc(pipelineId: string): Promise<any> {
    // Call the new backend endpoint for deleting data sources
    const deleted = await api.delete(`data_sources/data.source.delete`, {
        data: { pipeline_id: pipelineId }
    });
    return deleted.data;
};

export async function getSupportedFileExtensions(): Promise<string[]> {
    const response = await api.get<{supported_extensions: string[]}>('docs/supported-extensions');
    return response.data.supported_extensions;
};

export async function updateDocument(sourceId: string, updates: Record<string, unknown>): Promise<void> {
    await api.put('data_sources/data.source.update', {
        source_id: sourceId,
        updates
    });
};