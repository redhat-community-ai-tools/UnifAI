/**
 * Team collaboration view.
 *
 * Composes the shared useSessionHub (session list, selection, CRUD, streaming,
 * blueprint resolution) with team-specific concerns: presence join/leave,
 * heartbeat, participant tracking, typing indicators, and remote-execution
 * detection.  All session management lives in useSessionHub — this file only
 * adds the ~150 lines of collaboration wiring.
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "@/http/axiosAgentConfig";
import { cancelSession } from "@/api/sessions";
import {
  joinSession as joinSessionApi,
  leaveSession as leaveSessionApi,
  sendHeartbeat as sendHeartbeatApi,
  fetchParticipants as fetchParticipantsApi,
  fetchTypingUsers as fetchTypingUsersApi,
} from "@/api/collaboration";
import { useStreamingData } from "./StreamingDataContext";
import { useAuth } from "@/contexts/AuthContext";
import { useSessionManagement } from "@/hooks/use-session-management";
import { useSessionStream } from "@/hooks/use-session-stream";
import { useSessionHub } from "@/hooks/use-session-hub";
import { sortSessionsByTimestamp } from "@/utils/sessionHelpers";
import {
  CollaborationHubSessionSidebar,
  CollaborationHubMainColumn,
  CollaborationHubRightPanel,
  CollaborationHubModals,
} from "./collaborationHubPanels";
import { MemberDisplay, buildMemberDisplay } from "@/utils/memberDisplay";
import type { ChatSessionData } from "@/types/session";
import { transformSessionData } from "@/utils/sessionHelpers";

const COLLAB_POLL_INTERVAL = 3000;
const COLLAB_HEARTBEAT_INTERVAL = 30000;

interface CollaborationHubViewProps {
  runId: string | null;
  teamMembers: MemberDisplay[];
  teamName: string;
}

export default function CollaborationHubView({ runId, teamMembers, teamName }: CollaborationHubViewProps) {
  const hub = useSessionHub({ runId, manualStreamControl: true });

  // ── Collab-specific state ──────────────────────────────────────────────
  const [sessionParticipants, setSessionParticipants] = useState<Record<string, string[]>>({});
  const [isSessionBusy, setIsSessionBusy] = useState(false);
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { user } = useAuth();
  const { clearStream } = useStreamingData();
  const { loadSessionMessages } = useSessionManagement();

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const sessionListPollCounterRef = useRef(0);
  const joinedSessionRef = useRef<string | null>(null);
  const selectedSessionRef = useRef(hub.selectedSession);
  const isLiveRequestRef = useRef(hub.isLiveRequest);
  const wasSessionBusyRef = useRef(false);
  const streamCompleteResolverRef = useRef<(() => void) | null>(null);
  const updateNodeListRef = useRef<((chunkData: any) => void) | null>(null);
  updateNodeListRef.current = hub.updateNodeList;

  // Keep refs in sync
  useEffect(() => { selectedSessionRef.current = hub.selectedSession; }, [hub.selectedSession]);
  useEffect(() => { isLiveRequestRef.current = hub.isLiveRequest; }, [hub.isLiveRequest]);

  // ── Remote stream (watching another user's execution) ──────────────────
  const {
    subscribeToStream: subscribeRemoteStream,
    cancelStream: cancelRemoteStream,
  } = useSessionStream({
    onChunk: useCallback((chunkData: any) => {
      updateNodeListRef.current?.(chunkData);
    }, []),
    onStreamEnd: useCallback(() => {
      setIsSessionBusy(false);
      streamCompleteResolverRef.current?.();
      const session = selectedSessionRef.current;
      if (session) {
        loadSessionMessages(session).then((updated) => {
          if (updated) {
            hub.setCurrentSessionMessages(updated.messages);
            hub.setChatSessions(prev =>
              prev.map(s => (s.id === session.id ? { ...s, ...updated } : s)),
            );
          }
        });
      }
    }, [loadSessionMessages]),
    onError: useCallback((error: string) => {
      console.error("Session stream error:", error);
      streamCompleteResolverRef.current?.();
    }, []),
  });

  // ── Local execution (current user triggers run) ────────────────────────
  const triggerExecution = useCallback(
    async (sessionPayload: { sessionId: string; inputs: { user_prompt: string }; scope?: "public" | "private"; loggedInUser?: string }) => {
      try {
        hub.setIsLiveRequest(true);
        setIsSubmitting(true);

        await axios.post("/sessions/user.session.submit", {
          sessionId: sessionPayload.sessionId,
          inputs: sessionPayload.inputs,
          scope: hub.globalScope,
          userId: user?.username || "default",
        });
        setIsSubmitting(false);
        subscribeRemoteStream(sessionPayload.sessionId);

        await new Promise<void>((resolve) => {
          let resolved = false;
          const done = () => {
            if (resolved) return;
            resolved = true;
            clearInterval(statusPoll);
            resolve();
          };
          streamCompleteResolverRef.current = done;
          const statusPoll = setInterval(async () => {
            try {
              const statusRes = await axios.get(
                `/sessions/session.status.get?sessionId=${sessionPayload.sessionId}`,
              );
              if (statusRes.data !== "RUNNING" && statusRes.data !== "QUEUED") done();
            } catch { /* ignore */ }
          }, 2000);
        });
      } catch (err) {
        console.error("Error communicating with chat API", err);
        setIsSubmitting(false);
      } finally {
        hub.setIsLiveRequest(false);
        streamCompleteResolverRef.current = null;
      }

      let output: unknown;
      try {
        const res = await axios.get(
          `/sessions/session.state.get?sessionId=${sessionPayload.sessionId}`,
        );
        output = res.data.output;
      } catch (err) {
        console.error("Error fetching session state:", err);
      }
      return output;
    },
    [hub.globalScope, user?.username, subscribeRemoteStream],
  );

  const handleCancelSession = useCallback(async () => {
    if (!hub.selectedSession?.id) return;
    try {
      await cancelSession(hub.selectedSession.id);
    } catch (err) {
      console.error("Error cancelling session:", err);
    } finally {
      cancelRemoteStream();
      hub.setIsLiveRequest(false);
      setIsSubmitting(false);
      streamCompleteResolverRef.current?.();
      streamCompleteResolverRef.current = null;
    }
  }, [hub.selectedSession?.id, cancelRemoteStream]);

  // ── Presence: join / leave / heartbeat ─────────────────────────────────
  const joinSession = useCallback(async (sessionId: string) => {
    const username = user?.username || "default";
    try {
      await joinSessionApi(sessionId, username, user?.name || username);
      joinedSessionRef.current = sessionId;
    } catch { /* degrade gracefully */ }
  }, [user]);

  const leaveSession = useCallback(async (sessionId: string) => {
    const username = user?.username || "default";
    try {
      await leaveSessionApi(sessionId, username);
    } catch { /* best-effort */ }
    if (joinedSessionRef.current === sessionId) joinedSessionRef.current = null;
  }, [user]);

  const sendHeartbeat = useCallback(async () => {
    const sid = joinedSessionRef.current;
    if (!sid) return;
    try {
      await sendHeartbeatApi(sid, user?.username || "default");
    } catch { /* best-effort */ }
  }, [user]);

  // ── Participant tracking ───────────────────────────────────────────────
  const fetchParticipants = useCallback(async (sessionId: string) => {
    try {
      const participants = await fetchParticipantsApi(sessionId);
      setSessionParticipants(prev => {
        const existing = prev[sessionId];
        if (
          existing &&
          existing.length === participants.length &&
          existing.every((u, i) => u === participants[i])
        ) return prev;
        return { ...prev, [sessionId]: participants };
      });
    } catch { /* unavailable */ }
  }, []);

  // ── Polling loop ───────────────────────────────────────────────────────
  const pollSessionUpdates = useCallback(async () => {
    const session = selectedSessionRef.current;
    if (!session) return;

    sessionListPollCounterRef.current += 1;
    if (sessionListPollCounterRef.current % 5 === 0) {
      try {
        const listRes = await axios.get(
          `/sessions/session.user.list?userId=${hub.contextUserId}&identityType=${hub.identityType}`,
        );
        const transformApiDataToSessions = (apiData: ChatSessionData[]) =>
          apiData.map((sd, i) => {
            const base = transformSessionData(sd, i);
            let sharing = false;
            if (base.fromSharedLink && base.blueprintExists && base.blueprintId)
              sharing = !(sd.metadata?.public_usage_scope ?? false);
            return { ...base, isSharingDisabled: sharing };
          });
        const sorted = sortSessionsByTimestamp(transformApiDataToSessions(listRes.data));
        hub.setChatSessions(sorted);
        await Promise.allSettled(sorted.map(s => fetchParticipants(s.id)));
      } catch { /* ignore */ }
    }

    if (!isLiveRequestRef.current) {
      try {
        const statusRes = await axios.get(
          `/sessions/session.status.get?sessionId=${session.id}`,
        );
        const busy = statusRes.data === "RUNNING" || statusRes.data === "QUEUED";
        setIsSessionBusy(busy);
      } catch {
        setIsSessionBusy(false);
      }
    }

    const updated = await loadSessionMessages(session);
    if (updated) {
      hub.setCurrentSessionMessages(updated.messages);
      hub.setChatSessions(prev =>
        prev.map(s => (s.id === session.id ? { ...s, ...updated } : s)),
      );
    }

    await fetchParticipants(session.id);

    try {
      const allTyping = await fetchTypingUsersApi(session.id);
      const currentUser = user?.username || "default";
      setTypingUsers(allTyping.filter((u: string) => u !== currentUser));
    } catch { /* ignore */ }
  }, [loadSessionMessages, fetchParticipants, user?.username, hub.contextUserId, hub.identityType]);

  const getSessionParticipantMembers = useCallback((sessionId: string): MemberDisplay[] => {
    const participants = sessionParticipants[sessionId];
    if (!participants || participants.length === 0) return [];
    return participants.map((username, idx) => {
      const existing = teamMembers.find(m => m.id === username);
      return existing || buildMemberDisplay(username, teamMembers.length + idx);
    });
  }, [sessionParticipants, teamMembers]);

  // Subscribe to remote stream when session becomes busy
  useEffect(() => {
    const justBecameBusy = isSessionBusy && !wasSessionBusyRef.current;
    wasSessionBusyRef.current = isSessionBusy;
    if (justBecameBusy && !hub.isLiveRequest && hub.selectedSession) {
      clearStream();
      subscribeRemoteStream(hub.selectedSession.id);
    }
    if (!isSessionBusy && !hub.isLiveRequest) cancelRemoteStream();
  }, [isSessionBusy, hub.isLiveRequest, hub.selectedSession?.id]);

  // Join/leave + poll when selected session changes
  useEffect(() => {
    const previous = joinedSessionRef.current;
    if (previous && previous !== hub.selectedSession?.id) {
      leaveSession(previous);
      const username = user?.username || "default";
      setSessionParticipants(prev => {
        if (!prev[previous]) return prev;
        return { ...prev, [previous]: prev[previous].filter(u => u !== username) };
      });
    }

    setIsSessionBusy(false);
    setTypingUsers([]);
    wasSessionBusyRef.current = false;
    cancelRemoteStream();
    clearStream();

    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);

    if (!hub.selectedSession) return;

    joinSession(hub.selectedSession.id);
    fetchParticipants(hub.selectedSession.id);
    pollSessionUpdates();

    pollTimerRef.current = setInterval(pollSessionUpdates, COLLAB_POLL_INTERVAL);
    heartbeatTimerRef.current = setInterval(sendHeartbeat, COLLAB_HEARTBEAT_INTERVAL);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    };
  }, [hub.selectedSession?.id]);

  // Leave on unmount
  useEffect(() => {
    return () => {
      cancelRemoteStream();
      if (joinedSessionRef.current) leaveSession(joinedSessionRef.current);
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    };
  }, []);

  // ── Loading / Error ────────────────────────────────────────────────────
  if (hub.isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        Loading sessions...
      </div>
    );
  }
  if (hub.error) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        {hub.error}
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <>
      <div className="flex flex-1 overflow-hidden" style={{ height: "calc(100vh - 64px)" }}>
        <CollaborationHubSessionSidebar
          chatSessions={hub.chatSessions}
          selectedSession={hub.selectedSession}
          isLiveRequest={hub.isLiveRequest}
          onSelectSession={hub.handleSessionSelect}
          onDeleteChat={hub.handleDeleteChat}
          onOpenAddFlow={() => hub.setShowAddFlowModal(true)}
          getSessionParticipantMembers={getSessionParticipantMembers}
        />
        <CollaborationHubMainColumn
          selectedSession={hub.selectedSession}
          isLiveRequest={hub.isLiveRequest}
          isSessionBusy={isSessionBusy}
          isSubmitting={isSubmitting}
          currentSessionMessages={hub.currentSessionMessages}
          isSharingDisabled={hub.isSharingDisabled}
          isBlueprintValid={hub.isBlueprintValid}
          isValidatingBlueprint={hub.isValidatingBlueprint}
          typingUsers={typingUsers}
          teamMembers={teamMembers}
          triggerExecution={triggerExecution}
          onCancelSession={handleCancelSession}
          getSessionParticipantMembers={getSessionParticipantMembers}
        />
        <CollaborationHubRightPanel
          selectedSession={hub.selectedSession}
          isLiveRequest={hub.isLiveRequest}
          isCancelled={hub.isCancelled}
          isSessionBusy={isSessionBusy}
          teamName={teamName}
          chatSessionsLength={hub.chatSessions.length}
          blueprintSpecCache={hub.blueprintSpecCache}
          blueprintValidationResults={hub.blueprintValidationResults}
          isValidatingBlueprint={hub.isValidatingBlueprint}
          getSessionParticipantMembers={getSessionParticipantMembers}
        />
      </div>

      <CollaborationHubModals
        showAddFlowModal={hub.showAddFlowModal}
        setShowAddFlowModal={hub.setShowAddFlowModal}
        selectedFlowForModal={hub.selectedFlowForModal}
        setSelectedFlowForModal={hub.setSelectedFlowForModal}
        isCreatingSession={hub.isCreatingSession}
        onAddFlowConfirm={hub.handleAddFlow}
        showDeleteModal={hub.showDeleteModal}
        setShowDeleteModal={hub.setShowDeleteModal}
        chatToDelete={hub.chatToDelete}
        isDeleting={hub.isDeleting}
        onConfirmDelete={hub.confirmDeleteChat}
        onDeleteCancel={hub.cancelDeleteChat}
      />
    </>
  );
}
