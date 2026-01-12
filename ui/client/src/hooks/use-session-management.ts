/**
 * Custom hook for session management operations
 */

import { useState, useCallback } from 'react';
import axios from '@/http/axiosAgentConfig';
import { ChatSession, SessionStateData, ChatMessage } from '@/types/session';
import { getPreviewText } from '@/utils/sessionHelpers';

/**
 * Fetch session state (messages) for a specific session
 */
export const fetchSessionState = async (sessionId: string): Promise<SessionStateData | null> => {
  try {
    const response = await axios.get(`/sessions/session.state.get?sessionId=${sessionId}`);
    return response.data;
  } catch (err) {
    console.error('Error fetching session state:', err);
    return null;
  }
};

/**
 * Hook for managing session selection and message loading
 */
export const useSessionManagement = () => {
  const [currentMessages, setCurrentMessages] = useState<ChatMessage[]>([]);

  const loadSessionMessages = useCallback(
    async (session: ChatSession): Promise<ChatSession | null> => {
      // If messages are already loaded for this session, use them
      if (session.messages && session.messages.length > 0) {
        setCurrentMessages(session.messages);
        return session;
      }

      // Otherwise, fetch the session state
      const stateData = await fetchSessionState(session.id);
      if (stateData && stateData.messages) {
        setCurrentMessages(stateData.messages);

        // Update the session with loaded messages and preview
        const updatedSession: ChatSession = {
          ...session,
          messages: stateData.messages,
          preview: getPreviewText(stateData.messages),
        };

        return updatedSession;
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

