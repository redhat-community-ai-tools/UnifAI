
import React, { useMemo, useCallback, useEffect, useRef } from "react";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { motion } from "framer-motion";
import { useView } from "@/contexts/ViewContext";
import { useRoute, useLocation } from "wouter";

import ExecutionTab from "@/components/agentic-ai/ExecutionTab";
import CollaborationHubView from "@/components/agentic-ai/CollaborationHubView";
import { useTeamMembers } from "@/hooks/use-team-members";
import { StreamingDataProvider } from "@/components/agentic-ai/StreamingDataContext";

export default function AgenticChats() {
  const { viewMode, selectedTeam } = useView();
  const isTeam = viewMode === "team";
  const [, navigate] = useLocation();

  const [, routeParams] = useRoute("/agentic-chats/:sessionId");

  const urlRunId = useMemo(() => {
    if (routeParams?.sessionId) return routeParams.sessionId;
    const params = new URLSearchParams(window.location.search);
    return params.get("runId");
  }, [routeParams]);

  const handleSessionChange = useCallback(
    (sessionId: string) => {
      navigate(`/agentic-chats/${sessionId}`, { replace: true });
    },
    [navigate],
  );

  // Clear stale session ID from the URL when the workspace changes so
  // the new workspace doesn't try to look up the previous workspace's session.
  const prevWorkspaceRef = useRef({ viewMode, teamId: selectedTeam?.id });
  useEffect(() => {
    const prev = prevWorkspaceRef.current;
    const teamId = selectedTeam?.id;
    if (prev.viewMode !== viewMode || prev.teamId !== teamId) {
      prevWorkspaceRef.current = { viewMode, teamId };
      if (routeParams?.sessionId) {
        navigate("/agentic-chats", { replace: true });
      }
    }
  }, [viewMode, selectedTeam?.id, navigate, routeParams?.sessionId]);

  const teamMembers = useTeamMembers();

  return (
    <>
      <Header
        title={isTeam ? "Collaboration Hub" : "Agentic Chats"}
        onToggleSidebar={() => {}}
      />

      {isTeam ? (
        <StreamingDataProvider>
          <CollaborationHubView
            runId={urlRunId}
            teamMembers={teamMembers}
            teamName={selectedTeam?.name || "Team"}
            onSessionChange={handleSessionChange}
          />
        </StreamingDataProvider>
      ) : (
        <>
          <main className="flex-1 overflow-y-auto bg-background-dark">
            <div className="p-6">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <StreamingDataProvider>
                  <ExecutionTab
                    runId={urlRunId}
                    onSessionChange={handleSessionChange}
                  />
                </StreamingDataProvider>
              </motion.div>
            </div>
          </main>
          <StatusBar />
        </>
      )}
    </>
  );
}
