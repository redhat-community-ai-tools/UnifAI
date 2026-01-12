/**
 * Shared utilities for session data transformation and manipulation
 */

import { ChatSession, ChatSessionData, ChatMessage } from '@/types/session';
import { formatRelativeTimestamp } from '@/utils';

/**
 * Generate a random title for a chat session
 */
export const generateRandomTitle = (index: number): string => {
  const titles = ['Chat Session', 'Conversation', 'Discussion', 'Chat'];
  return `${titles[index % titles.length]} ${index + 1}`;
};

/**
 * Get preview text from messages (first 50 characters)
 */
export const getPreviewText = (messages: ChatMessage[]): string => {
  if (!messages || messages.length === 0) {
    return 'No messages yet';
  }
  const lastMessage = messages[messages.length - 1];
  const content = lastMessage.content || '';
  return content.length > 50 ? `${content.substring(0, 50)}...` : content;
};

/**
 * Generate a random session ID
 */
export const generateRandomId = (): string => {
  return `chat-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * Transform API session data to ChatSession format
 * This is a base transformer that doesn't include sharing status checks
 */
export const transformSessionData = (
  sessionData: ChatSessionData,
  index: number
): Omit<ChatSession, 'isSharingDisabled'> => {
  const title = sessionData.metadata?.title || generateRandomTitle(index);
  const id = sessionData.session_id || generateRandomId();
  const blueprintId = sessionData.blueprint_id;
  const blueprintExists = sessionData.blueprint_exists;
  const fromSharedLink = sessionData.metadata?.source === 'public_link';
  const timestamp = new Date(sessionData.started_at);
  const lastActive = formatRelativeTimestamp(sessionData.started_at);
  const preview = fromSharedLink ? 'From chat experience' : 'Click to load messages...';

  return {
    id,
    blueprintId,
    title: fromSharedLink ? `${title} (Shared Link)` : title,
    lastActive,
    timestamp,
    preview,
    messages: [], // Messages will be loaded separately when session is selected
    blueprintExists,
    fromSharedLink,
  };
};

/**
 * Sort sessions by timestamp (most recent first)
 */
export const sortSessionsByTimestamp = (sessions: ChatSession[]): ChatSession[] => {
  return [...sessions].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
};

