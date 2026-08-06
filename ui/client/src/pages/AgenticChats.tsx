
import React, { useMemo, useState, useCallback, useEffect } from "react";
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

  // Detect a workspace switch (personal <-> team, or team A -> team B)
  // synchronously during render, *before* urlRunId is computed, to ensure the new workspace is loaded with the correct session ID.
  const workspaceKey = `${viewMode}:${selectedTeam?.id ?? ""}`;
  const [prevWorkspaceKey, setPrevWorkspaceKey] = useState(workspaceKey);
  const [suppressRunIdOverride, setSuppressRunIdOverride] = useState(false);
  if (workspaceKey !== prevWorkspaceKey) {
    setPrevWorkspaceKey(workspaceKey);
    setSuppressRunIdOverride(true);
  }

  const urlRunId = useMemo(() => {
    if (suppressRunIdOverride) return null;
    if (routeParams?.sessionId) return routeParams.sessionId;
    const params = new URLSearchParams(window.location.search);
    return params.get("runId");
  }, [routeParams, suppressRunIdOverride]);

  const handleSessionChange = useCallback(
    (sessionId: string) => {
      navigate(`/agentic-chats/${sessionId}`, { replace: true });
    },
    [navigate],
  );

  // Once the workspace-switch render has committed (with urlRunId already
  // suppressed above), clean up the address bar and lift the suppression.
  useEffect(() => {
    if (suppressRunIdOverride) {
      if (routeParams?.sessionId) {
        navigate("/agentic-chats", { replace: true });
      }
      setSuppressRunIdOverride(false);
    }
  }, [suppressRunIdOverride, routeParams?.sessionId, navigate]);

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
