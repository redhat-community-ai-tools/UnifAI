
import React, { useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { motion } from "framer-motion";

// Agentic AI components
import ExecutionTab from "@/components/agentic-ai/ExecutionTab";
import { StreamingDataProvider } from "@/components/agentic-ai/StreamingDataContext";

// Create a ReactFlow provider wrapper
import { ReactFlowProvider } from "reactflow";

export default function AgenticChats() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Agentic Chats"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <main className="flex-1 overflow-y-auto bg-background-dark">
          <div className="p-6">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <StreamingDataProvider>
                <ReactFlowProvider>
                  <ExecutionTab runId={null} />
                </ReactFlowProvider>
              </StreamingDataProvider>
            </motion.div>
          </div>
        </main>

        <StatusBar />
      </div>
    </div>
  );
}