import { useState, useEffect, useCallback, useRef } from 'react';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';
import axios from '@/http/axiosAgentConfig';
import { ChatSession, ChatMessage, ChatSessionData } from '@/types/session';
import { checkSessionSharingStatus } from '@/hooks/use-sharing-status';
import {transformSessionData, sortSessionsByTimestamp,} from '@/utils/sessionHelpers';
import { useSessionManagement } from '@/hooks/use-session-management';
import { useSessionStream } from '@/hooks/use-session-stream';
import { getBlueprintInfo } from '@/api/blueprints';
import { createSessionError } from '@/components/agentic-ai/chat/types';
import { createSession as createSessionApi, CreateSessionParams, listSessions } from '@/api/sessions';

interface UsePublicChatReturn {
  sessions: ChatSession[];
  selectedSession: ChatSession | null;
  isLoading: boolean;
  isCreatingSession: boolean;
  isDeleting: boolean;
  chatHistory: ChatMessage[];
  runId: string | null;
  isLiveRequest: boolean;
  handleNewChat: () => Promise<void>;
  handleSessionSelect: (session: ChatSession) => Promise<void>;
  handleDeleteChat: (session: ChatSession, event: React.MouseEvent) => void;
  confirmDeleteChat: () => Promise<void>;
  cancelDeleteChat: () => void;
  triggerExecution: (sessionPayload: any) => Promise<string>;
  handleCancelSession: () => Promise<void>;
  isSubmitting: boolean;
  showDeleteModal: boolean;
  setShowDeleteModal: (open: boolean) => void;
  chatToDelete: ChatSession | null;
  fetchNextPage: () => void;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  error: string | null;
}

const PAGE_SIZE = 50;

export const usePublicChat = (blueprintId: string | null): UsePublicChatReturn => {
  const { user, isAuthenticated } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<ChatSession | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [isLiveRequest, setIsLiveRequest] = useState(false);

  const streamCompleteResolverRef = useRef<(() => void) | null>(null);

  const { loadSessionMessages } = useSessionManagement();

  const sessionStream = useSessionStream({
    onChunk: useCallback(() => {
      // Chat-only mode: intermediate chunks are not displayed.
      // Final answer is fetched via session.chat.get after stream completes.
    }, []),
    onStreamEnd: useCallback(() => {
      setIsLiveRequest(false);
      if (streamCompleteResolverRef.current) {
        streamCompleteResolverRef.current();
        streamCompleteResolverRef.current = null;
      }
    }, []),
    onError: useCallback((error: string) => {
      console.error('Stream error:', error);
      setIsLiveRequest(false);
      if (streamCompleteResolverRef.current) {
        streamCompleteResolverRef.current();
        streamCompleteResolverRef.current = null;
      }
    }, []),
  });

  // Transform API data to ChatSession format
  const transformApiDataToSessions = useCallback(
    async (apiData: ChatSessionData[]): Promise<ChatSession[]> => {
      // Transform sessions and fetch fresh public_usage_scope status for shared link sessions
      const transformedSessions = await Promise.all(
        apiData.map(async (sessionData, index) => {
          const baseSession = transformSessionData(sessionData, index);

          // Fetch fresh public_usage_scope status for shared link sessions to ensure accuracy
          const isSharingDisabled = await checkSessionSharingStatus(
            baseSession.blueprintId,
            baseSession.fromSharedLink ?? false,
            baseSession.blueprintExists,
            sessionData.metadata?.public_usage_scope
          );

          return {
            ...baseSession,
            isSharingDisabled,
          };
        })
      );

      return transformedSessions;
    },
    []
  );

  // Paginated session fetching
  const {
    data: sessionsData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
    error: queryError,
  } = useInfiniteQuery({
    queryKey: ['publicChatSessions', user?.username, blueprintId],
    queryFn: async ({ pageParam = 0 }) => {
      const params = new URLSearchParams({
        userId: user!.username,
        limit: String(PAGE_SIZE),
        offset: String(pageParam),
      });
      params.set('filters', JSON.stringify({ blueprint_id: blueprintId }));

      const { sessions: allSessions, pagination } = await listSessions(params);

      const transformedSessions = await transformApiDataToSessions(allSessions);
      const validSessions = transformedSessions.filter(s => s.blueprintExists !== false);
      return {
        sessions: sortSessionsByTimestamp(validSessions),
        hasMore: pagination.has_more,
        nextOffset: pagination.offset + pagination.limit,
        total: pagination.total,
      };
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      if (!lastPage.hasMore) return undefined;
      return lastPage.nextOffset;
    },
    enabled: isAuthenticated && !!user && !!blueprintId,
  });

  const sessions = sessionsData?.pages.flatMap((page) => page.sessions) ?? [];

  // Handle session selection
  const handleSessionSelect = useCallback(
    async (session: ChatSession) => {
      sessionStream.cancelStream();
      setIsLiveRequest(false);
      setSelectedSession(session);

      const updatedSession = await loadSessionMessages(session);
      if (updatedSession) {
        setSelectedSession(updatedSession);
        setChatHistory(updatedSession.messages);
        setRunId(session.id);
      } else {
        setChatHistory([]);
        setRunId(session.id);
      }

      // Reconnect to an active Redis stream if the session is still running
      const sessionStatus = updatedSession?.status;
      const isTerminal = sessionStatus === 'CANCELLED' || sessionStatus === 'FAILED' || sessionStatus === 'COMPLETED';

      if (!isTerminal) {
        sessionStream.checkAndReconnect(session.id).then(hasActiveStream => {
          if (hasActiveStream) {
            setIsLiveRequest(true);
          }
        });
      }
    },
    [loadSessionMessages, sessionStream]
  );

  // Handle delete chat
  const handleDeleteChat = useCallback((session: ChatSession, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent session selection when clicking delete
    setChatToDelete(session);
    setShowDeleteModal(true);
  }, []);

  const confirmDeleteChat = useCallback(async () => {
    if (!chatToDelete) return;

    setIsDeleting(true);
    try {
      await axios.delete(`/sessions/session.delete?sessionId=${chatToDelete.id}`);

      if (selectedSession?.id === chatToDelete.id) {
        setSelectedSession(null);
        setChatHistory([]);
        setRunId(null);
      }

      setShowDeleteModal(false);
      setChatToDelete(null);

      queryClient.invalidateQueries({ queryKey: ['publicChatSessions', user?.username, blueprintId] });

      toast({
        title: 'Success',
        description: 'Chat session deleted successfully',
      });
    } catch (error: any) {
      console.error('Error deleting chat session:', error);
      toast({
        title: 'Error',
        description: error.response?.data?.error || 'Failed to delete chat session',
        variant: 'destructive',
      });
    } finally {
      setIsDeleting(false);
    }
  }, [chatToDelete, selectedSession, user, blueprintId, queryClient, toast]);

  const cancelDeleteChat = useCallback(() => {
    setShowDeleteModal(false);
    setChatToDelete(null);
  }, []);

  // Core session creation logic (shared by manual and auto-init)
  const createSession = useCallback(async () => {
    if (!blueprintId || !user) {
      throw new Error('Blueprint ID and user are required');
    }

    const creationData: CreateSessionParams = {
      blueprintId: blueprintId,
      metadata: { source: 'public_link' },
    };

    const newSessionId = await createSessionApi(creationData);

    if (!newSessionId || typeof newSessionId !== 'string') {
      throw new Error('Invalid session ID received from server');
    }

    const tempSession: ChatSession = {
      id: newSessionId,
      blueprintId: blueprintId,
      title: 'New Chat',
      lastActive: 'Just now',
      timestamp: new Date(),
      preview: 'New conversation',
      messages: [],
      blueprintExists: true,
      fromSharedLink: true,
    };

    setSelectedSession(tempSession);
    setChatHistory([]);
    setRunId(newSessionId);

    // Invalidate to refresh with real data from server
    queryClient.invalidateQueries({
      queryKey: ['publicChatSessions', user.username, blueprintId],
    });

    return tempSession;
  }, [blueprintId, user, queryClient]);

  // Handle new chat creation (manual trigger with UI feedback)
  const handleNewChat = useCallback(async () => {
    if (!blueprintId || !user) return;

    setIsCreatingSession(true);
    try {
      await createSession();
    } catch (error: any) {
      toast({
        title: 'Error',
        description: error.response?.data?.error || 'Failed to create new chat',
        variant: 'destructive',
      });
    } finally {
      setIsCreatingSession(false);
    }
  }, [blueprintId, user, createSession, toast]);

  const handleCancelSession = useCallback(async () => {
    if (!runId) return;

    try {
      await sessionStream.cancelSessionExecution(runId);
    } catch (error) {
      console.error('Error cancelling session execution:', error);
    } finally {
      sessionStream.cancelStream();
      setIsLiveRequest(false);

      if (streamCompleteResolverRef.current) {
        streamCompleteResolverRef.current();
        streamCompleteResolverRef.current = null;
      }
    }
  }, [runId, sessionStream]);

  // Trigger execution using Temporal submit + Redis stream (same path as Agentic-Chats)
  const triggerExecution = useCallback(
    async (sessionPayload: any): Promise<string> => {
      if (!runId) {
        throw new Error('No session available');
      }

      // Check sharing status before allowing execution (fresh check each time)
      if (blueprintId) {
        try {
          const blueprintInfo = await getBlueprintInfo(blueprintId);
          const isPublic = blueprintInfo.metadata?.usageScope === "public";
          if (!isPublic) {
            throw new Error("This workflow's chat sharing has been disabled and can no longer be continued.");
          }
        } catch (error: any) {
          if (error.message && error.message.includes('disabled')) {
            throw error;
          }
          throw new Error("This workflow's chat sharing has been disabled and can no longer be continued.");
        }
      }

      try {
        setIsLiveRequest(true);

        const streamCompletePromise = new Promise<void>((resolve) => {
          streamCompleteResolverRef.current = resolve;
        });

        await sessionStream.submitAndSubscribe({
          sessionId: runId,
          inputs: sessionPayload.inputs || {},
          scope: 'public',
          userId: user?.username || '',
        });

        await streamCompletePromise;

        const sessionResponse = await axios.get(`/sessions/session.chat.get?sessionId=${runId}`);
        const { output, status, status_message } = sessionResponse.data;

        if (status === 'CANCELLED') {
          throw createSessionError(status_message || 'Workflow was stopped.', 'CANCELLED');
        }
        if (status === 'FAILED') {
          throw createSessionError(status_message || 'Workflow failed.', 'FAILED');
        }

        return output && output.trim() !== '' ? output : 'Execution completed, but no output was generated.';
      } catch (error: any) {
        console.error('Error in triggerExecution:', error);
        setIsLiveRequest(false);
        throw error;
      }
    },
    [runId, blueprintId, user, sessionStream]
  );

  const didAutoInitRef = useRef(false);

  // Reset auto-init flag when blueprint or user changes
  useEffect(() => {
    didAutoInitRef.current = false;
  }, [blueprintId, user?.username]);

  // Auto-create or auto-select session when data first loads
  useEffect(() => {
    if (isLoading || !sessionsData || didAutoInitRef.current) {
      return;
    }

    if (sessions.length === 0 && !selectedSession && !runId && blueprintId && user) {
      didAutoInitRef.current = true;
      (async () => {
        try {
          await createSession();
        } catch (createError: any) {
          console.error('Error auto-creating new chat:', createError);
          // Don't show toast for auto-init failures (silent failure)
        }
      })();
    } else if (sessions.length > 0 && !selectedSession) {
      handleSessionSelect(sessions[0]);
    }
  }, [sessions.length, isLoading, sessionsData, blueprintId, user, selectedSession, runId, createSession, handleSessionSelect]);

  return {
    sessions,
    selectedSession,
    isLoading,
    isCreatingSession,
    isDeleting,
    chatHistory,
    runId,
    isLiveRequest,
    handleNewChat,
    handleSessionSelect,
    handleDeleteChat,
    confirmDeleteChat,
    cancelDeleteChat,
    triggerExecution,
    handleCancelSession,
    isSubmitting: sessionStream.isSubmitting,
    showDeleteModal,
    setShowDeleteModal,
    chatToDelete,
    fetchNextPage,
    hasNextPage: hasNextPage ?? false,
    isFetchingNextPage,
    error: isError
      ? (queryError instanceof Error ? queryError.message : 'Failed to load chat sessions')
      : null,
  };
};

