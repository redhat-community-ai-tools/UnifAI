import axios from '@/http/axiosAgentConfig';

export const FILE_MAX_COUNT = 3;
export const FILE_MAX_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

export interface FileReference {
  file_uri: string;
  mime_type: string;
  display_name: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface UploadResult {
  files: FileReference[];
  errors: { filename: string; error: string }[];
}

export interface CreateSessionParams {
  blueprintId: string;
  userId: string;
}

export async function createSession(params: CreateSessionParams) {
  const response = await axios.post('/sessions/user.session.create', params);
  return response.data;
}

/**
 * Submit Session Request Parameters
 * Used for fire-and-forget background execution
 */
export interface SubmitSessionParams {
  sessionId: string;
  inputs: Record<string, any>;
  scope?: 'public' | 'private';
  files?: File[];
  userId: string;
}

/**
 * Submit Session Response
 * Returned immediately with HTTP 202 - session runs in background
 */
export interface SubmitSessionResponse {
  sessionId: string;
  workflowId?: string;
}

/**
 * Submit a session for background execution.
 * Returns immediately with HTTP 202 — the session runs asynchronously.
 * 
 * After calling this, use subscribeToSessionStream() to receive real-time events.
 * 
 * @param params - Session submission parameters
 * @returns Session ID and workflow ID (if using Temporal)
 * @throws Error if submission fails (400, 500)
 */
export async function submitSession(params: SubmitSessionParams): Promise<SubmitSessionResponse> {
  const { files, ...jsonPayload } = params;

  if (files && files.length > 0) {
    const formData = new FormData();
    formData.append('payload', JSON.stringify(jsonPayload));
    files.forEach((file) => formData.append('files', file));
    const response = await axios.post('/sessions/user.session.submit', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  const response = await axios.post('/sessions/user.session.submit', jsonPayload);
  return response.data;
}

/**
 * Cancel Session Response
 */
export interface CancelSessionResponse {
  sessionId: string;
  status: 'CANCELLED';
}

/**
 * Cancel a running session.
 * Signals the backend to cancel the workflow for this session.
 * Silently ignores 409 (session already completed/failed/cancelled).
 *
 * @param sessionId - The session to cancel
 * @returns Cancel confirmation, or null if session was not cancellable
 */
export async function cancelSession(sessionId: string): Promise<CancelSessionResponse | null> {
  try {
    const response = await axios.post('/sessions/session.cancel', { sessionId });
    return response.data;
  } catch (err: any) {
    if (err.response?.status === 409) {
      return null;
    }
    throw err;
  }
}

/**
 * Redis Stream Status Response
 */
export interface StreamStatusResponse {
  session_id: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'unknown';
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  error: string | null;
  event_count: number;
  last_event_id: string | null;
  is_active: boolean;
}

/**
 * Check the streaming status of a session via Redis.
 * Returns null if Redis is unavailable, session not found, or timeout.
 */
export async function getSessionStreamStatus(sessionId: string): Promise<StreamStatusResponse | null> {
  try {
    const response = await axios.get(`/sessions/session.stream.status?sessionId=${sessionId}`, {
      timeout: 5000, // 5 second timeout to prevent hanging
    });
    return response.data;
  } catch (err: any) {
    // Gracefully handle unavailable Redis, not found, or timeout
    if (err.response?.status === 503 || err.response?.status === 404 || err.code === 'ECONNABORTED') {
      return null;
    }
    console.error('Error fetching stream status:', err);
    return null;
  }
}

/**
 * Subscribe to a session's Redis stream.
 * Returns a Response object for streaming, or null if unavailable.
 * 
 * The stream replays all events from the beginning, then blocks and streams
 * live events as they arrive. Connection stays open until session completes.
 * 
 * @param sessionId - The session to subscribe to
 */
export async function subscribeToSessionStream(sessionId: string): Promise<Response | null> {
  try {
    const response = await fetch(
      `/api2/sessions/session.subscribe?sessionId=${sessionId}`,
      {
        method: 'GET',
        headers: {
          'Accept': 'application/x-ndjson',
        },
      }
    );
    
    if (!response.ok) {
      console.warn(`Stream subscription failed: ${response.status}`);
      return null;
    }
    
    return response;
  } catch (err) {
    console.error('Error subscribing to stream:', err);
    return null;
  }
}

/**
 * Upload files to Google's servers via the Gemini File API.
 * Returns successful file references and any per-file errors.
 */
export async function uploadSessionFiles(
  sessionId: string,
  files: File[],
): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("sessionId", sessionId);
  files.forEach((f) => formData.append("files", f));
  const resp = await axios.post(
    "/sessions/session.files.upload",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      validateStatus: (s: number) => s === 200 || s === 207,
    },
  );
  return resp.data;
}

/**
 * Upload files (if any), then trigger execution with file references in inputs.
 * Handles partial and total upload failures.
 */
export async function sendMessageWithFiles(
  sessionId: string,
  message: string,
  files: File[],
  triggerExecution: (payload: any) => Promise<string>,
  onPartialFailure?: (failedNames: string) => void,
): Promise<void> {
  let fileRefs: FileReference[] = [];
  if (files.length > 0) {
    const result = await uploadSessionFiles(sessionId, files);
    fileRefs = result.files;

    if (result.files.length === 0 && result.errors.length > 0) {
      const failedNames = result.errors.map((e) => e.filename).join(", ");
      throw new Error(`All files failed to upload: ${failedNames}`);
    }

    if (result.errors.length > 0) {
      const failedNames = result.errors.map((e) => e.filename).join(", ");
      onPartialFailure?.(failedNames);
    }
  }
  await triggerExecution({
    sessionId,
    inputs: {
      user_prompt: message,
      ...(fileRefs.length > 0 && {
        file_references: fileRefs.map((r) => ({
          file_uri: r.file_uri,
          mime_type: r.mime_type,
          display_name: r.display_name,
          size_bytes: r.size_bytes,
          uploaded_at: r.uploaded_at,
        })),
      }),
    },
  });
}
