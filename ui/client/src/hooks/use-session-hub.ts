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

import { useState, useCallback, useRef, useEffect } from "react";
import axios from "@/http/axiosAgentConfig";
import { fetchResolvedBlueprint } from "@/api/blueprints";
import { useStreamingData } from "@/components/agentic-ai/StreamingDataContext";
import { useAuth } from "@/contexts/AuthContext";
import { useView } from "@/contexts/ViewContext";
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
}

export interface UseSessionHubReturn {
  // ── Session list ────────────────────────────────────────────────────────
  chatSessions: ChatSession[];
  setChatSessions: React.Dispatch<React.SetStateAction<ChatSession[]>>;
  selectedSession: ChatSession | null;
  setSelectedSession: React.Dispatch<React.SetStateAction<ChatSession | null>>;
  currentSessionMessages: ChatMessage[];
  setCurrentSessionMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  isLoading: boolean;
  error: string | null;
  isLoadingSessionMessages: boolean;
  fetchChatSessions: () => Promise<void>;

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
  identityType: "team" | "user";
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
    | "workplan_snapshot";
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
};

// ─── Hook ───────────────────────────────────────────────────────────────────

export function useSessionHub({
  runId,
  manualStreamControl = false,
}: UseSessionHubOptions): UseSessionHubReturn {
  // ── Session state ──────────────────────────────────────────────────────
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [currentSessionMessages, setCurrentSessionMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
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
  const { selectedTeam } = useView();
  const { isTeam, userId: contextUserId, displayName, identityType } =
    useWorkspaceIdentity();
  const { toast } = useToast();

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

  // ── Node-list streaming ────────────────────────────────────────────────
  const updateNodeList = useCallback(
    (chunkData: ChunkData) => {
      const {
        node, display_name, type, chunk, state, tool, output,
        call_id, args, action, plan_id, thread_id, owner_uid, workplan,
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
            };
            const idx = existing.workplans.findIndex(
              (wp: any) => wp.plan_id === plan_id || wp.owner_uid === snap.owner_uid,
            );
            if (idx !== -1) existing.workplans[idx] = snap;
            else existing.workplans.push(snap);
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

  // ── handleSessionSelect ────────────────────────────────────────────────
  // Stable ref so fetchChatSessions can call it without a circular dep
  const handleSessionSelectRef = useRef<(session: ChatSession) => Promise<void>>(null!);

  const handleSessionSelect = useCallback(
    async (session: ChatSession) => {
      const requestId = ++sessionSelectRequestId.current;

      let current = session;
      setSelectedSession(current);
      setIsLoadingSessionMessages(true);
      setCurrentSessionMessages([]);
      setIsSharingDisabled(false);

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
            contextUserId,
            identityType,
            isTeam ? (selectedTeam?.name ?? undefined) : undefined,
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
              setChatSessions((prev) =>
                prev.map((s) =>
                  s.id === current.id
                    ? { ...s, blueprintName, isSharingDisabled: disabled }
                    : s,
                ),
              );
            } else if (blueprintName) {
              setChatSessions((prev) =>
                prev.map((s) =>
                  s.id === current.id ? { ...s, blueprintName } : s,
                ),
              );
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
        setChatSessions((prev) =>
          prev.map((s) => (s.id === current.id ? merged : s)),
        );
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
      contextUserId,
      identityType,
      isTeam,
      selectedTeam?.name,
      loadSessionMessages,
      manualStreamControl,
    ],
  );
  handleSessionSelectRef.current = handleSessionSelect;

  // ── fetchChatSessions ──────────────────────────────────────────────────
  const fetchChatSessions = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await axios.get(
        `/sessions/session.user.list?userId=${contextUserId}&identityType=${identityType}`,
      );
      const sorted = sortSessionsByTimestamp(
        transformApiDataToSessions(response.data),
      );
      setChatSessions(sorted);

      if (sorted.length > 0) {
        const target = runId
          ? sorted.find((s) => s.id === runId) ?? sorted[0]
          : sorted[0];
        await handleSessionSelectRef.current(target);
      }
    } catch (err) {
      console.error("Error fetching chat sessions:", err);
      setError("Failed to load chat sessions");
    } finally {
      setIsLoading(false);
    }
  }, [contextUserId, identityType, runId, transformApiDataToSessions]);

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
      await axios.delete(`/sessions/session.delete?sessionId=${chatToDelete.id}`);
      setChatSessions((prev) => prev.filter((s) => s.id !== chatToDelete.id));
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
  }, [chatToDelete, selectedSession?.id, toast]);

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
      await axios.post("/sessions/user.session.create", {
        blueprintId: graphId,
        userId: contextUserId,
        displayName,
        identityType,
      });
      const response = await axios.get(
        `/sessions/session.user.list?userId=${contextUserId}&identityType=${identityType}`,
      );
      const sorted = sortSessionsByTimestamp(
        transformApiDataToSessions(response.data),
      );
      setChatSessions(sorted);
      const newest = sorted.find((s) => s.blueprintId === graphId);
      if (newest) await handleSessionSelectRef.current(newest);
      setShowAddFlowModal(false);
      setSelectedFlowForModal(null);
    } catch (err) {
      console.error("Error creating session:", err);
    } finally {
      setIsCreatingSession(false);
    }
  }, [selectedFlowForModal, contextUserId, displayName, identityType, transformApiDataToSessions]);

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

  type SessionPayload = {
    sessionId: string;
    inputs: { user_prompt: string };
    scope?: "public" | "private";
    loggedInUser?: string;
  };

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
          userId: (() => {
            const raw = (sessionPayload.loggedInUser || "").trim();
            if (isTeam && raw && raw === contextUserId) {
              return user?.username || "default";
            }
            if (raw && raw !== "default") return raw;
            return user?.username || "default";
          })(),
        });

        await streamCompletePromise;

        const session_response = await axios.get(
          `/sessions/session.chat.get?sessionId=${sessionPayload.sessionId}`,
        );
        const { output, status, status_message } = session_response.data;

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
    [sessionStream, globalScope, isTeam, contextUserId, user?.username],
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
  useEffect(() => {
    sessionSelectRequestId.current += 1;
    sessionStream.cancelStream();
    clearStream();
    setSelectedSession(null);
    setCurrentSessionMessages([]);
    fetchChatSessions();
  }, [contextUserId, identityType]);

  // ── Return ─────────────────────────────────────────────────────────────
  return {
    chatSessions,
    setChatSessions,
    selectedSession,
    setSelectedSession,
    currentSessionMessages,
    setCurrentSessionMessages,
    isLoading,
    error,
    isLoadingSessionMessages,
    fetchChatSessions,

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
    identityType,
    isTeam,
    displayName,
    globalScope,
  };
}
