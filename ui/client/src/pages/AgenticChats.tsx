
import React, { useMemo } from "react";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { motion } from "framer-motion";
import { useView } from "@/contexts/ViewContext";

import ExecutionTab from "@/components/agentic-ai/ExecutionTab";
import CollaborationHubView from "@/components/agentic-ai/CollaborationHubView";
import { useTeamMembers } from "@/hooks/use-team-members";
import { StreamingDataProvider } from "@/components/agentic-ai/StreamingDataContext";

export default function AgenticChats() {
  const { viewMode, selectedTeam } = useView();
  const isTeam = viewMode === "team";

  const urlRunId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("runId");
  }, []);

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
                  <ExecutionTab runId={urlRunId} />
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
