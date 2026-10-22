// Chat message format (used for both API responses and UI state)
export interface ChatMessage {
  content: string;
  role: "user" | "assistant";
  sender_id?: string;
  metadata?: Record<string, any>;
}

/**
 * Non-fatal structured error the backend attaches to a message's `metadata.error`
 * (and sends on `agent_error` stream events), e.g. a model rate limit or quota.
 */
export interface MessageError {
  type: string; // "rate_limited"
  message: string;
  /** Seconds to wait before retrying; null when unknown. */
  retry_after: number | null;
}

// Shared ChatSession interface used across components
export interface ChatSession {
  id: string;
  blueprintId: string;
  title: string;
  lastActive: string;
  timestamp: Date;
  preview: string;
  messages: ChatMessage[];
  blueprintExists: boolean;
  fromSharedLink?: boolean;
  fromSchedule?: boolean;
  blueprintName?: string;
  isSharingDisabled?: boolean;
  hitlEnabled?: boolean;
  status?: string;
  statusMessage?: string;
  totalCost?: number | null;
}

// Types for the API response
export interface ChatSessionData {
  metadata: Record<string, any>; // Contains public_usage_scope for shared link sessions
  blueprint_id: string;
  session_id: string;
  started_at: string;
  last_active_at?: string;
  blueprint_exists: boolean;
  status?: string;
}

export interface SessionStateData {
  final_output: string;
  messages: ChatMessage[];
  status?: string;
  status_message?: string;
}