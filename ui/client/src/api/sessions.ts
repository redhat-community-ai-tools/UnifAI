import axios from '@/http/axiosAgentConfig';
import type { ChatSessionData } from '@/types/session';

// ─────────────────────────────────────────────────────────────────────────────
//  Types
// ─────────────────────────────────────────────────────────────────────────────

export interface SessionChatResponse {
  messages?: any[];
  output?: string;
  status?: string;
  status_message?: string;
  [key: string]: any;
}

export interface CreateSessionParams {
  blueprintId: string;
  teamId?: string;
  userId?: string;
  metadata?: Record<string, any>;
}

export async function createSession(params: CreateSessionParams): Promise<string> {
  const response = await axios.post('/sessions/user.session.create', params);
  return response.data;
}

export async function listUserSessions(teamId?: string | null): Promise<ChatSessionData[]> {
  const params = new URLSearchParams();
  if (teamId) params.set('teamId', teamId);
  const response = await axios.get(`/sessions/session.user.list?${params.toString()}`);
  return response.data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await axios.delete(`/sessions/session.delete?sessionId=${sessionId}`);
}

export async function getSessionChat(sessionId: string): Promise<SessionChatResponse> {
  const response = await axios.get(`/sessions/session.chat.get?sessionId=${sessionId}`);
  return response.data;
}

export async function getSessionStatus(sessionId: string): Promise<string> {
  const response = await axios.get(`/sessions/session.status.get?sessionId=${sessionId}`);
  return response.data;
}

export async function getSessionState(sessionId: string): Promise<any> {
  const response = await axios.get(`/sessions/session.state.get?sessionId=${sessionId}`);
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
  const response = await axios.post('/sessions/user.session.submit', params);
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