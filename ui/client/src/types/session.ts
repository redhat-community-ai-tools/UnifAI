// Chat message format (used for both API responses and UI state)
export interface ChatMessage {
  content: string;
  role: "user" | "assistant";
  file_attachments?: Array<{ file_name: string; mime_type?: string; file_uri?: string }>;
  sender_id?: string;
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
  blueprintName?: string; // The workflow display name from spec_dict.name
  isSharingDisabled?: boolean; // Track if sharing is disabled for this session
  status?: string;
  statusMessage?: string;
}

// Types for the API response
export interface ChatSessionData {
  metadata: Record<string, any>; // Contains public_usage_scope for shared link sessions
  blueprint_id: string;
  session_id: string;
  started_at: string;
  last_active_at?: string;
  blueprint_exists: boolean;
}

export interface SessionStateData {
  final_output: string;
  messages: ChatMessage[];
  status?: string;
  status_message?: string;
}