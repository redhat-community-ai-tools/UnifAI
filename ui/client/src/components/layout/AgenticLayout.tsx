import React from "react";
import Sidebar from "./Sidebar";
import { useView } from "@/contexts/ViewContext";
import { Users, UserPlus, MousePointerClick, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

interface AgenticLayoutProps {
  children: React.ReactNode;
}

export default function AgenticLayout({ children }: AgenticLayoutProps) {
  const { viewMode, teams, selectedTeam, teamsLoading, teamsReady } = useView();

  let mainContent: React.ReactNode = children;
  if (viewMode === "team") {
    if (teamsLoading || !teamsReady) {
      mainContent = <TeamsLoadingView />;
    } else if (teams.length === 0) {
      mainContent = <NoTeamsView />;
    } else if (!selectedTeam) {
      mainContent = <PickTeamView />;
    }
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {mainContent}
      </div>
    </div>
  );
}

function TeamsLoadingView() {
  return (
    <div className="flex-1 flex items-center justify-center bg-background-dark">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-center"
      >
        <Loader2 className="w-8 h-8 text-primary/60 animate-spin mx-auto mb-4" />
        <p className="text-sm text-gray-400">Loading teams…</p>
      </motion.div>
    </div>
  );
}

function NoTeamsView() {
  return (
    <div className="flex-1 flex items-center justify-center bg-background-dark">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="text-center max-w-md px-6"
      >
        <div className="mx-auto w-20 h-20 rounded-2xl bg-primary/10 flex items-center justify-center mb-6">
          <Users className="w-10 h-10 text-primary/60" />
        </div>
        <h2 className="text-xl font-heading font-semibold text-white mb-3">
          No Team Workspace Yet
        </h2>
        <p className="text-sm text-gray-400 leading-relaxed mb-2">
          To see a team workspace, join an existing team or create a new one.
          Use the team selector in the sidebar to get started.
        </p>
        <div className="flex items-center justify-center gap-2 mt-6 text-xs text-gray-600">
          <UserPlus className="w-3.5 h-3.5" />
          <span>Tip: Click <strong className="text-gray-400">Team</strong> in the sidebar, then <strong className="text-gray-400">Create a new team</strong></span>
        </div>
      </motion.div>
    </div>
  );
}

function PickTeamView() {
  return (
    <div className="flex-1 flex items-center justify-center bg-background-dark">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="text-center max-w-md px-6"
      >
        <div className="mx-auto w-20 h-20 rounded-2xl bg-primary/10 flex items-center justify-center mb-6">
          <MousePointerClick className="w-10 h-10 text-primary/60" />
        </div>
        <h2 className="text-xl font-heading font-semibold text-white mb-3">
          Pick a Team Workspace
        </h2>
        <p className="text-sm text-gray-400 leading-relaxed mb-2">
          Select a team from the dropdown in the sidebar to view its workspace.
        </p>
      </motion.div>
    </div>
  );
}
