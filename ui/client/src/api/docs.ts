import { api } from '@/http/queryClient';
import type { Document } from '@/types';

/**
 * File validation error from the backend
 */
export interface FileValidationError {
    file_name: string;
    error_type: 'extension' | 'size' | 'duplicate';
    message: string;
}

/**
 * Valid file info returned from validation
 */
export interface ValidatedFile {
    name: string;
    normalized_name: string;
    size: number;
}

/**
 * Response from the file validation endpoint
 */
export interface FileValidationResponse {
    valid_files: ValidatedFile[];
    errors: FileValidationError[];
    has_errors: boolean;
}


export async function fetchDocuments(): Promise<Document[]> {
  // Call the new backend endpoint for available data sources with source_type='document'
  // Using GET request with query parameters as required by the backend @from_query decorator
  const response = await api.get<{sources: any}>(
    "data_sources/data.sources.get",
    {
      params: {
        source_type: "document",
        filter_query: JSON.stringify({ "type_data.full_text": 0 })
      }
    }
  );
  return response.data.sources;
};

export async function uploadDocs(files: {name: string, content: string}[]): Promise<any> {
    const response = await api.post<any>(
        'docs/upload',
        { files: files }
    );
    return response.data;
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

export async function embedDocs(
    docs: {source_name: string, tags?: string[]}[], 
    user: string,
    skipValidation: boolean = false
): Promise<PipelineEmbedResponse> {
    const embedded = await api.put<PipelineEmbedResponse>(
      'pipelines/embed',
      {
        data: docs,
        source_type: 'document',
        logged_in_user: user,
        skip_validation: skipValidation
      }
    );
    return embedded.data;
}

export async function deleteDocs(pipelineIds: string[]): Promise<any> {
    const deleted = await api.delete(`data_sources/data.source.delete`, {
        data: { pipeline_ids: pipelineIds }
    });
    return deleted.data;
};

export async function getSupportedFileExtensions(): Promise<string[]> {
    const response = await api.get<{supported_extensions: string[]}>('docs/supported-extensions');
    return response.data.supported_extensions;
};

/**
 * Validate files before upload.
 * 
 * This endpoint performs pre-upload validation including:
 * - File extension validation (must be in supported list)
 * - File size validation (max 50 MB per file)
 * - Duplicate name detection (allows re-upload of FAILED documents)
 * 
 * @param files - Array of file metadata objects with 'name' and 'size' keys
 * @param username - Username of the person uploading files
 * @param checkDuplicates - Whether to check for duplicate filenames (default: true)
 * @returns Validation results with valid files and errors
 * 
 */
export async function validateFiles(
    files: { name: string; size: number }[],
    username: string,
    checkDuplicates: boolean = true
): Promise<FileValidationResponse> {
    const response = await api.post<FileValidationResponse>('docs/validate', {
        files,
        username,
        check_duplicates: checkDuplicates
    });
    return response.data;
}

export async function updateDocument(sourceId: string, updates: Record<string, unknown>): Promise<void> {
    await api.put('data_sources/data.source.update', {
        source_id: sourceId,
        updates
    });
};

export async function fetchDocumentDetails(sourceId: string): Promise<Document> {
    const response = await api.get<{ success: boolean; source: Document }>(
        'data_sources/data.source.details.get',
        {
            params: { source_id: sourceId }
        }
    );
    return response.data.source;
};