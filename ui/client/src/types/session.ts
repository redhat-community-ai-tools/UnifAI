// Chat message format (used for both API responses and UI state)
export interface ChatMessage {
  content: string;
  role: "user" | "assistant";
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
  isSharingDisabled?: boolean; // Track if sharing is disabled for this session
}

// Types for the API response
export interface ChatSessionData {
  metadata: Record<string, any>; // Contains public_usage_scope for shared link sessions
  blueprint_id: string;
  session_id: string;
  started_at: string;
  blueprint_exists: boolean;
}

export interface SessionStateData {
  final_output: string;
  messages: ChatMessage[];
}