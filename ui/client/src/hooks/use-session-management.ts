/**
 * Custom hook for session management operations
 */

import { useState, useCallback } from 'react';
import axios from '@/http/axiosAgentConfig';
import { ChatSession, SessionStateData, ChatMessage } from '@/types/session';
import { getPreviewText } from '@/utils/sessionHelpers';

/**
 * Fetch session chat data (messages and output) for a specific session
 */
export const fetchSessionState = async (sessionId: string): Promise<SessionStateData | null> => {
  try {
    const response = await axios.get(`/sessions/session.chat.get?sessionId=${sessionId}`);
    return response.data;
  } catch (err) {
    console.error('Error fetching session state:', err);
    return null;
  }
};

/**
 * Fetch session chat data including messages and status
 */
export const fetchSessionChat = async (sessionId: string): Promise<{ messages: ChatMessage[]; status?: string; statusMessage?: string } | null> => {
  try {
    const response = await axios.get(`/sessions/session.chat.get?sessionId=${sessionId}`);
    return {
      messages: response.data?.messages ?? [],
      status: response.data?.status,
      statusMessage: response.data?.status_message ?? undefined,
    };
  } catch (err) {
    console.error('Error fetching session chat:', err);
    return null;
  }
};

/**
 * Fetch only session messages for a specific session (lightweight)
 */
export const fetchSessionMessages = async (sessionId: string): Promise<ChatMessage[] | null> => {
  const chat = await fetchSessionChat(sessionId);
  return chat?.messages ?? null;
};

/**
 * Hook for managing session selection and message loading
 */
export const useSessionManagement = () => {
  const [currentMessages, setCurrentMessages] = useState<ChatMessage[]>([]);

  const loadSessionMessages = useCallback(
    async (session: ChatSession): Promise<ChatSession | null> => {
      // Always fetch fresh data from the backend to ensure we have the latest state
      const chat = await fetchSessionChat(session.id);
      if (chat && chat.messages.length > 0) {
        setCurrentMessages(chat.messages);

        const updatedSession: ChatSession = {
          ...session,
          messages: chat.messages,
          preview: getPreviewText(chat.messages),
          status: chat.status,
          statusMessage: chat.statusMessage,
        };

        return updatedSession;
      }

      // If no messages from backend, fall back to session's existing messages
      if (session.messages && session.messages.length > 0) {
        setCurrentMessages(session.messages);
        return session;
      }

      return null;
    },
    []
  );

  const clearMessages = useCallback(() => {
    setCurrentMessages([]);
  }, []);

  return {
    currentMessages,
    loadSessionMessages,
    clearMessages,
    setCurrentMessages,
  };
};

