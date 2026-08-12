/**
 * Shared session-management hook consumed by both ExecutionTab (personal) and
 * CollaborationHubView (team).  Contains session list CRUD, session selection
 * with race guards, blueprint resolution + caching, streaming / execution,
 * cancel, delete, and create-from-flow — everything that was previously
 * duplicated across the two components.
 *
 * Team-specific behaviour (presence, typing indicators, remote execution
 * detection) lives outside this hook — CollaborationHubView composes
 * useSessionHub with its own collab hooks.
 */

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { fetchResolvedBlueprint } from "@/api/blueprints";
import {
  createSession,
  deleteSession,
  getSessionChat,
  listSessions,
  fetchSessionChatById,
} from "@/api/sessions";
import { useStreamingData } from "@/components/agentic-ai/StreamingDataContext";
import { useAuth } from "@/contexts/AuthContext";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";
import { useToast } from "@/hooks/use-toast";
import { useBlueprintValidation } from "@/hooks/use-blueprint-validation";
import { useSessionManagement } from "@/hooks/use-session-management";
import { useSessionStream } from "@/hooks/use-session-stream";
import { createSessionError } from "@/components/agentic-ai/chat/types";
import {
  ChatSession,
  ChatMessage,
  ChatSessionData,
} from "@/types/session";
import {
  transformSessionData,
  sortSessionsByTimestamp,
} from "@/utils/sessionHelpers";
import type { FlowObject } from "@/components/agentic-ai/graphs/interfaces";
import { SessionPayload } from "@/components/agentic-ai/ExecutionTab";

// Re-export so consumers don't need a separate import
export type { SessionPayload } from "@/components/agentic-ai/ExecutionTab";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface UseSessionHubOptions {
  runId: string | null;
  /**
   * When true the hook skips the submitAndSubscribe + stream-complete dance
   * used by ExecutionTab and instead exposes `subscribeToStream` /
   * `cancelStream` directly, letting the caller drive streaming (used by
   * CollaborationHubView which has its own submit path + remote-stream logic).
   */
  manualStreamControl?: boolean;
  /**
   * Called whenever the active session changes (sidebar click, initial load).
   * The parent component can use this to update the browser URL for deep-linking.
   */
  onSessionChange?: (sessionId: string) => void;
}

export interface UseSessionHubReturn {
  // ── Session list ────────────────────────────────────────────────────────
  chatSessions: ChatSession[];
  updateSessionInCache: (sessionId: string, updater: (s: ChatSession) => ChatSession) => void;
  refreshSessions: () => Promise<ChatSession[]>;
  selectedSession: ChatSession | null;
  setSelectedSession: React.Dispatch<React.SetStateAction<ChatSession | null>>;
  currentSessionMessages: ChatMessage[];
  setCurrentSessionMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  isLoading: boolean;
  error: string | null;
  isLoadingSessionMessages: boolean;

  // ── Pagination ─────────────────────────────────────────────────────────
  fetchNextPage: (options?: { skipRunId?: boolean }) => void;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;

  // ── Session selection ───────────────────────────────────────────────────
  handleSessionSelect: (session: ChatSession) => Promise<void>;
  sessionSelectRequestId: React.MutableRefObject<number>;

  // ── Execution / streaming ───────────────────────────────────────────────
  isLiveRequest: boolean;
  setIsLiveRequest: React.Dispatch<React.SetStateAction<boolean>>;
  isCancelled: boolean;
  triggerExecution: (payload: SessionPayload) => Promise<string>;
  handleCancelSession: () => Promise<void>;
  sessionStream: ReturnType<typeof useSessionStream>;
  streamCompleteResolverRef: React.MutableRefObject<(() => void) | null>;
  updateNodeList: (chunkData: any) => void;

  // ── Blueprint ───────────────────────────────────────────────────────────
  blueprintSpecCache: Map<string, any>;
  isSharingDisabled: boolean;
  isValidatingBlueprint: boolean;
  isBlueprintValid: boolean;
  blueprintValidationResults: ReturnType<typeof useBlueprintValidation>["validationResults"];

  // ── Delete modal ────────────────────────────────────────────────────────
  showDeleteModal: boolean;
  setShowDeleteModal: React.Dispatch<React.SetStateAction<boolean>>;
  chatToDelete: ChatSession | null;
  isDeleting: boolean;
  handleDeleteChat: (session: ChatSession, event: React.MouseEvent) => void;
  confirmDeleteChat: () => Promise<void>;
  cancelDeleteChat: () => void;

  // ── Add-flow modal ──────────────────────────────────────────────────────
  showAddFlowModal: boolean;
  setShowAddFlowModal: React.Dispatch<React.SetStateAction<boolean>>;
  selectedFlowForModal: FlowObject | null;
  setSelectedFlowForModal: React.Dispatch<React.SetStateAction<FlowObject | null>>;
  isCreatingSession: boolean;
  handleAddFlow: () => Promise<void>;
  handleCancelAddFlow: () => void;

  // ── Identity helpers (pass-through for convenience) ─────────────────────
  contextUserId: string;
  teamId: string | undefined;
  isTeam: boolean;
  displayName: string;
  globalScope: "public" | "private";
}

// ─── Chunk‐data shape used by updateNodeList ────────────────────────────────

type ChunkData = {
  node: string;
  display_name: string;
  type:
    | "llm_token"
    | "complete"
    | "tool_calling"
    | "tool_result"
    | "workplan_snapshot"
    | "approval_required";
  chunk?: string;
  tool?: string;
  output?: string;
  call_id?: string;
  args?: Record<string, any>;
  state?: { user_prompt?: string };
  action?: "loaded" | "saved" | "deleted";
  plan_id?: string;
  thread_id?: string;
  owner_uid?: string;
  workplan?: any;
  // HITL approval fields
  request_id?: string;
  approval_type?: string;
  origin?: { node_uid: string; node_display_name: string; session_id: string };
  tool_name?: string;
  tool_args?: Record<string, any>;
  tool_description?: string;
  tool_access_mode?: string;
};

// ─── Hook ───────────────────────────────────────────────────────────────────

const PAGE_SIZE = 50;

export function useSessionHub({
  runId,
  manualStreamControl = false,
  onSessionChange,
}: UseSessionHubOptions): UseSessionHubReturn {
  // ── Session state ──────────────────────────────────────────────────────
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [currentSessionMessages, setCurrentSessionMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLiveRequest, setIsLiveRequest] = useState(false);
  const [isCancelled, setIsCancelled] = useState(false);
  const [globalScope] = useState<"public" | "private">("public");
  const [isSharingDisabled, setIsSharingDisabled] = useState(false);
  const [blueprintSpecCache, setBlueprintSpecCache] = useState<Map<string, any>>(new Map());
  const [isLoadingSessionMessages, setIsLoadingSessionMessages] = useState(false);

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<ChatSession | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Add-flow modal
  const [showAddFlowModal, setShowAddFlowModal] = useState(false);
  const [selectedFlowForModal, setSelectedFlowForModal] = useState<FlowObject | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);

  // Contexts
  const { nodeListRef, clearStream } = useStreamingData();
  const { user } = useAuth();
  const { isTeam, userId: contextUserId, displayName, teamId } =
    useWorkspaceIdentity();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Refs
  const sessionSelectRequestId = useRef(0);
  const selectedSessionIdRef = useRef<string | null>(null);
  const updateNodeListRef = useRef<((chunkData: any) => void) | null>(null);
  const streamCompleteResolverRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    selectedSessionIdRef.current = selectedSession?.id ?? null;
  }, [selectedSession?.id]);

  // ── Blueprint validation ───────────────────────────────────────────────
  const {
    isValidating: isValidatingBlueprint,
    validationResults: blueprintValidationResults,
    isValid: isBlueprintValid,
    validateBlueprint: validateSelectedBlueprint,
  } = useBlueprintValidation({ showToastOnFailure: true });

  // ── Session management (message loading) ───────────────────────────────
  const { loadSessionMessages } = useSessionManagement();

  // ── transformApiDataToSessions ─────────────────────────────────────────
  const transformApiDataToSessions = useCallback(
    (apiData: ChatSessionData[]): ChatSession[] =>
      apiData.map((sessionData, index) => {
        const base = transformSessionData(sessionData, index);
        let sharing = false;
        if (base.fromSharedLink && base.blueprintExists && base.blueprintId) {
          sharing = !(sessionData.metadata?.public_usage_scope ?? false);
        }
        return { ...base, isSharingDisabled: sharing };
      }),
    [],
  );

  // ── Paginated session fetching ────────────────────────────────────────
  const sessionsQueryKey = useMemo(
    () => ['chatSessions', contextUserId, teamId] as const,
    [contextUserId, teamId],
  );

  const {
    data: sessionsData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError: isSessionsError,
    error: sessionsQueryError,
  } = useInfiniteQuery({
    queryKey: sessionsQueryKey,
    queryFn: async ({ pageParam = 0 }) => {
      const params = new URLSearchParams({
        userId: contextUserId,
        limit: String(PAGE_SIZE),
        offset: String(pageParam),
      });
      if (teamId) params.set('teamId', teamId);
      const { sessions, pagination } = await listSessions(params);
      return {
        sessions: sortSessionsByTimestamp(transformApiDataToSessions(sessions)),
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
  });

  const chatSessions = sessionsData?.pages.flatMap((p) => p.sessions) ?? [];
  const sessionsError = isSessionsError
    ? (sessionsQueryError instanceof Error
        ? sessionsQueryError.message
        : "Failed to load chat sessions")
    : null;

  // ── Node-list streaming ────────────────────────────────────────────────
  const updateNodeList = useCallback(
    (chunkData: ChunkData) => {
      const {
        node, display_name, type, chunk, state, tool, output,
        call_id, args, action, plan_id, thread_id, owner_uid, workplan,
        request_id, origin, tool_name, tool_args, tool_description, tool_access_mode,
      } = chunkData;
      const map = nodeListRef.current;
      let existing = map.get(node);

      if (!existing) {
        existing = {
          node_name: display_name,
          node_uid: node,
          stream: type === "complete" ? "DONE" : "PROGRESS",
          text: "",
          tools: [],
          workplans: [],
          approvals: [],
        };
        map.set(node, existing);
      }

      switch (type) {
        case "llm_token":
          if (chunk) existing.text += chunk;
          break;
        case "tool_calling":
          if (call_id && tool) {
            if (!existing.tools?.find((t: any) => t.id === call_id)) {
              existing.tools?.push({ id: call_id, name: tool, args });
            }
          }
          break;
        case "tool_result":
          if (call_id && tool && output) {
            const entry = existing.tools?.find((t: any) => t.id === call_id);
            if (entry) entry.output = output;
            else existing.tools?.push({ id: call_id, name: tool, output });
          }
          break;
        case "workplan_snapshot":
          if (plan_id && workplan && action) {
            if (!existing.workplans) existing.workplans = [];
            const snap = {
              type: "workplan_snapshot" as const,
              action: action as "loaded" | "saved" | "deleted",
              plan_id,
              thread_id: thread_id || "",
              owner_uid: owner_uid || node,
              node,
              display_name,
              workplan,
              isExpanded: false,
            };
            const idx = existing.workplans.findIndex(
              (wp: any) => wp.plan_id === plan_id || wp.owner_uid === snap.owner_uid,
            );
            if (idx !== -1) existing.workplans[idx] = snap;
            else existing.workplans.push(snap);
          }
          break;
        case "approval_required":
          if (request_id && tool_name) {
            if (!existing.approvals) existing.approvals = [];
            const alreadyExists = existing.approvals.some(
              (a: any) => a.requestId === request_id,
            );
            if (!alreadyExists) {
              existing.approvals.push({
                requestId: request_id,
                toolName: tool_name,
                toolArgs: tool_args || {},
                toolDescription: tool_description || "",
                accessMode: tool_access_mode || "write",
                originNodeUid: origin?.node_uid || node,
                originNodeName: origin?.node_display_name || display_name,
                status: "pending",
              });
            }
          }
          break;
        default:
          break;
      }
    },
    [nodeListRef],
  );
  updateNodeListRef.current = updateNodeList;

  // ── Session stream ─────────────────────────────────────────────────────
  const sessionStream = useSessionStream({
    onChunk: useCallback((chunkData: any) => {
      updateNodeListRef.current?.(chunkData);
    }, []),
    onStreamEnd: useCallback(() => {
      setIsLiveRequest(false);
      streamCompleteResolverRef.current?.();
      streamCompleteResolverRef.current = null;
    }, []),
    onError: useCallback((err: string) => {
      console.error("Stream error:", err);
      setIsLiveRequest(false);
      streamCompleteResolverRef.current?.();
      streamCompleteResolverRef.current = null;
    }, []),
  });

  // Update a single session inside the paged query cache without refetching.
  const updateSessionInCache = useCallback(
    (sessionId: string, updater: (s: ChatSession) => ChatSession) => {
      queryClient.setQueryData(sessionsQueryKey, (old: any) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page: any) => ({
            ...page,
            sessions: page.sessions.map((s: ChatSession) =>
              s.id === sessionId ? updater(s) : s,
            ),
          })),
        };
      });
    },
    [queryClient, sessionsQueryKey],
  );

  // ── handleSessionSelect ────────────────────────────────────────────────
  // Stable ref so auto-select and handleAddFlow can call it without a circular dep
  const handleSessionSelectRef = useRef<(session: ChatSession) => Promise<void>>(null!);

  const onSessionChangeRef = useRef(onSessionChange);
  onSessionChangeRef.current = onSessionChange;

  const handleSessionSelect = useCallback(
    async (session: ChatSession) => {
      const requestId = ++sessionSelectRequestId.current;
      console.log('[handleSessionSelect] called with', session.id, 'requestId=', requestId);

      let current = session;
      setSelectedSession(current);
      setIsLoadingSessionMessages(true);
      setCurrentSessionMessages([]);
      setIsSharingDisabled(false);

      onSessionChangeRef.current?.(session.id);

      // Cancel any existing stream subscription before switching
      sessionStream.cancelStream();
      clearStream();
      setIsLiveRequest(false);
      setIsCancelled(false);

      if (current.blueprintId) validateSelectedBlueprint(current.blueprintId);

      // Resolve blueprint for name + sharing status + spec cache
      if (session.blueprintExists && session.blueprintId) {
        try {
          const resolved = await fetchResolvedBlueprint(
            session.blueprintId,
            teamId,
          );
          if (sessionSelectRequestId.current !== requestId) return;
          if (resolved) {
            setBlueprintSpecCache((prev) => {
              const next = new Map(prev);
              next.set(session.blueprintId, resolved.spec_dict);
              return next;
            });
            const blueprintName = resolved.spec_dict?.name || "";
            current = { ...current, blueprintName };

            if (session.fromSharedLink) {
              const disabled = !(resolved.metadata?.usageScope === "public");
              setIsSharingDisabled(disabled);
              current = { ...current, isSharingDisabled: disabled };
              updateSessionInCache(current.id, (s) => ({
                ...s, blueprintName, isSharingDisabled: disabled,
              }));
            } else if (blueprintName) {
              updateSessionInCache(current.id, (s) => ({
                ...s, blueprintName,
              }));
            }
            setSelectedSession(current);
          }
        } catch {
          // keep defaults
        }
      }

      if (sessionSelectRequestId.current !== requestId) return;

      // Load messages
      const updated = await loadSessionMessages(current);
      if (sessionSelectRequestId.current !== requestId) return;

      if (updated) {
        const merged = { ...current, ...updated };
        setSelectedSession(merged);
        setCurrentSessionMessages(merged.messages);
        updateSessionInCache(current.id, () => merged);
      } else {
        setCurrentSessionMessages([]);
      }
      setIsLoadingSessionMessages(false);

      // Reconnect to active stream (ExecutionTab path only)
      if (!manualStreamControl) {
        const sessionStatus = updated?.status;
        const isTerminal =
          sessionStatus === "CANCELLED" ||
          sessionStatus === "FAILED" ||
          sessionStatus === "COMPLETED";

        if (!isTerminal) {
          const reconnectSessionId = session.id;
          sessionStream.checkAndReconnect(session.id).then((hasActiveStream) => {
            if (sessionSelectRequestId.current !== requestId) return;
            if (selectedSessionIdRef.current !== reconnectSessionId) return;
            if (hasActiveStream) setIsLiveRequest(true);
          });
        }
      }
    },
    [
      sessionStream,
      clearStream,
      validateSelectedBlueprint,
      teamId,
      loadSessionMessages,
      manualStreamControl,
      updateSessionInCache,
    ],
  );
  handleSessionSelectRef.current = handleSessionSelect;

  // ── refreshSessions ────────────────────────────────────────────────────
  const refreshSessions = useCallback(async (): Promise<ChatSession[]> => {
    await queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
    const data = queryClient.getQueryData(sessionsQueryKey) as any;
    return data?.pages.flatMap((p: any) => p.sessions) ?? [];
  }, [queryClient, sessionsQueryKey]);

  // ── Auto-select session on load ────────────────────────────────────────
  const activeRunIdRef = useRef(runId);
  const autoSelectKeyRef = useRef<string | null>(null);
  useEffect(() => {
    const key = `${contextUserId}:${teamId}:${activeRunIdRef.current ?? "first"}`;
    console.log('[auto-select] effect fired. key=', key, 'autoSelectKey=', autoSelectKeyRef.current, 'selectedSession=', selectedSession?.id ?? 'null', 'chatSessions.length=', chatSessions.length);
    if (isLoading || !sessionsData || autoSelectKeyRef.current === key) return;
    if (chatSessions.length > 0 && !selectedSession) {
      const target = activeRunIdRef.current
        ? chatSessions.find((s) => s.id === activeRunIdRef.current)
        : chatSessions[0];
      console.log('[auto-select] will select target=', target?.id ?? 'none');

      if (activeRunIdRef.current && !target && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
        return;
      }

      // Deep-link fallback: session not in any loaded page
      if (activeRunIdRef.current && !target) {
        autoSelectKeyRef.current = key;
        (async () => {
          try {
            const chatData = await fetchSessionChatById(activeRunIdRef.current!);
            const deepLinked: ChatSession = {
              id: activeRunIdRef.current!,
              blueprintId: "",
              title: "Deep-linked session",
              lastActive: "",
              timestamp: new Date(),
              preview: "",
              messages: chatData?.messages ?? [],
              blueprintExists: false,
              status: chatData?.status,
              statusMessage: chatData?.status_message,
            };
            await handleSessionSelectRef.current(deepLinked);
          } catch (err: any) {
            const status = err?.response?.status;
            if (status === 403) {
              setError("You don't have access to this session.");
            } else if (status === 404) {
              setError("Session not found.");
            } else {
              setError("Failed to load the requested session.");
            }
            if (chatSessions.length > 0) {
              await handleSessionSelectRef.current(chatSessions[0]);
            }
          }
        })();
        return;
      }

      if (!target) return;
      autoSelectKeyRef.current = key;
      handleSessionSelectRef.current(target);
    }
  }, [isLoading, sessionsData, chatSessions, selectedSession, runId,
      contextUserId, teamId, hasNextPage, isFetchingNextPage, fetchNextPage]);

  // ── Delete ─────────────────────────────────────────────────────────────
  const handleDeleteChat = useCallback(
    (session: ChatSession, event: React.MouseEvent) => {
      event.stopPropagation();
      setChatToDelete(session);
      setShowDeleteModal(true);
    },
    [],
  );

  const confirmDeleteChat = useCallback(async () => {
    if (!chatToDelete) return;
    setIsDeleting(true);
    try {
      await deleteSession(chatToDelete.id);
      refreshSessions();
      if (selectedSession?.id === chatToDelete.id) {
        setSelectedSession(null);
        setCurrentSessionMessages([]);
      }
      setShowDeleteModal(false);
      setChatToDelete(null);
    } catch (err) {
      console.error("Error deleting chat session:", err);
      toast({
        title: "Delete failed",
        description: "Could not delete the chat session. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsDeleting(false);
    }
  }, [chatToDelete, selectedSession?.id, toast, refreshSessions]);

  const cancelDeleteChat = useCallback(() => {
    setShowDeleteModal(false);
    setChatToDelete(null);
  }, []);

  // ── Add flow ───────────────────────────────────────────────────────────
  const handleAddFlow = useCallback(async () => {
    if (!selectedFlowForModal) return;
    setIsCreatingSession(true);
    try {
      const graphId = selectedFlowForModal.id || `graph-${Date.now()}`;
      const runId = await createSession({ blueprintId: graphId, teamId });
      console.log('[handleAddFlow] createSession returned runId=', runId, 'type=', typeof runId);

      const newSession: ChatSession = {
        id: runId,
        blueprintId: graphId,
        title: selectedFlowForModal.name || "New Session",
        lastActive: "Just now",
        timestamp: new Date(),
        preview: "Click to load messages...",
        messages: [],
        blueprintExists: true,
      };

      queryClient.setQueryData(sessionsQueryKey, (old: any) => {
        if (!old?.pages?.length) return old;
        const firstPage = old.pages[0];
        return {
          ...old,
          pages: [
            { ...firstPage, sessions: [newSession, ...firstPage.sessions] },
            ...old.pages.slice(1),
          ],
        };
      });

      console.log('[handleAddFlow] calling handleSessionSelect with newSession.id=', newSession.id);
      handleSessionSelectRef.current(newSession);

      console.log('[handleAddFlow] firing invalidateQueries (background)');
      queryClient.invalidateQueries({ queryKey: sessionsQueryKey });

      setShowAddFlowModal(false);
      setSelectedFlowForModal(null);
    } catch (err) {
      console.error("Error creating session:", err);
      toast({
        title: "Create session failed",
        description: "Could not start a new session. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsCreatingSession(false);
    }
  }, [selectedFlowForModal, teamId, queryClient, sessionsQueryKey, toast]);

  const handleCancelAddFlow = useCallback(() => {
    setShowAddFlowModal(false);
    setSelectedFlowForModal(null);
  }, []);

  // Cleanup stale flow selection when modal closes
  useEffect(() => {
    if (!showAddFlowModal && selectedFlowForModal) {
      setSelectedFlowForModal(null);
    }
  }, [showAddFlowModal]);

  // ── Execution ──────────────────────────────────────────────────────────

  const triggerExecution = useCallback(
    async (sessionPayload: SessionPayload): Promise<string> => {
      try {
        setIsCancelled(false);
        setIsLiveRequest(true);

        const streamCompletePromise = new Promise<void>((resolve) => {
          streamCompleteResolverRef.current = resolve;
        });

        await sessionStream.submitAndSubscribe({
          sessionId: sessionPayload.sessionId,
          inputs: sessionPayload.inputs,
          scope: sessionPayload.scope || globalScope,
        });

        await streamCompletePromise;

        const sessionChat = await getSessionChat(sessionPayload.sessionId);
        const { output, status, status_message } = sessionChat;

        if (status === "CANCELLED") {
          throw createSessionError(status_message || "Workflow was stopped.", "CANCELLED");
        }
        if (status === "FAILED") {
          throw createSessionError(status_message || "Workflow failed.", "FAILED");
        }

        return output;
      } catch (err) {
        console.error("Error in session execution:", err);
        setIsLiveRequest(false);
        throw err;
      }
    },
    [sessionStream, globalScope],
  );

  // ── Cancel ─────────────────────────────────────────────────────────────
  const handleCancelSession = useCallback(async () => {
    if (!selectedSession?.id) return;
    setIsCancelled(true);
    try {
      await sessionStream.cancelSessionExecution(selectedSession.id);
    } catch (err) {
      console.error("Error cancelling session execution:", err);
    } finally {
      sessionStream.cancelStream();
      setIsLiveRequest(false);
      streamCompleteResolverRef.current?.();
      streamCompleteResolverRef.current = null;
    }
  }, [selectedSession, sessionStream]);

  // ── Workspace-switch effect ────────────────────────────────────────────
  // On the very first mount we still want to honor a deep-linked `runId`
  // (e.g. a link from RunHistoryPanel). Only skip it on later re-runs, which
  // happen when the user switches workspace (personal <-> team) and the old
  // runId no longer applies to the new workspace's session list.
  const hasMountedRef = useRef(false);
  useEffect(() => {
    console.log('[workspace-switch] effect fired. contextUserId=', contextUserId, 'teamId=', teamId);
    sessionSelectRequestId.current += 1;
    autoSelectKeyRef.current = null;
    activeRunIdRef.current = hasMountedRef.current ? null : runId;
    sessionStream.cancelStream();
    clearStream();
    setSelectedSession(null);
    setCurrentSessionMessages([]);
    queryClient.removeQueries({ queryKey: sessionsQueryKey });
    refreshSessions();
    hasMountedRef.current = true;
  }, [contextUserId, teamId]);

  // ── Return ─────────────────────────────────────────────────────────────
  return {
    chatSessions,
    updateSessionInCache,
    refreshSessions,
    selectedSession,
    setSelectedSession,
    currentSessionMessages,
    setCurrentSessionMessages,
    isLoading,
    error: sessionsError ?? error,
    isLoadingSessionMessages,

    fetchNextPage,
    hasNextPage: hasNextPage ?? false,
    isFetchingNextPage,

    handleSessionSelect,
    sessionSelectRequestId,

    isLiveRequest,
    setIsLiveRequest,
    isCancelled,
    triggerExecution,
    handleCancelSession,
    sessionStream,
    streamCompleteResolverRef,
    updateNodeList,

    blueprintSpecCache,
    isSharingDisabled,
    isValidatingBlueprint,
    isBlueprintValid,
    blueprintValidationResults,

    showDeleteModal,
    setShowDeleteModal,
    chatToDelete,
    isDeleting,
    handleDeleteChat,
    confirmDeleteChat,
    cancelDeleteChat,

    showAddFlowModal,
    setShowAddFlowModal,
    selectedFlowForModal,
    setSelectedFlowForModal,
    isCreatingSession,
    handleAddFlow,
    handleCancelAddFlow,

    contextUserId,
    teamId,
    isTeam,
    displayName,
    globalScope,
  };
}
