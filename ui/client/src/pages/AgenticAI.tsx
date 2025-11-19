import { useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import { Users, Network, Play, Plus, LoaderCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

// Agentic AI components
import AgentFlowGraph from "@/components/agentic-ai/AgentFlowGraph";
import NewGraph from "../workspace/NewGraph";
import axios from "../http/axiosAgentConfig";

// Create a ReactFlow provider wrapper
import { ReactFlowProvider } from "reactflow";
import { FlowObject } from "@/components/agentic-ai/graphs/interfaces";

export interface GraphNode {
  id: string;
  name: string;
  description: string | null;
}

export default function AgenticAI() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedFlow, setSelectedFlow] = useState<FlowObject | null>(null);
  const [builtGraphId, setBuiltGraphId] = useState<string | null>(null);
  const [builtGraphName, setBuiltGraphName] = useState<string | null>(null);
  const [selectedGraphId, setSelectedGraphId] = useState<string | null>(null);
  const [showGraphBuilder, setShowGraphBuilder] = useState(false);
  const [isLoadingFlow, setIsLoadingFlow] = useState(false);
  const { user } = useAuth();
  const { toast } = useToast();

  const handleLoadFlow = async () => {
    if (isLoadingFlow) return; // Prevent multiple calls
    
    setIsLoadingFlow(true);
    try {
      const graphId = selectedFlow?.id || `graph-${Date.now()}`;
      const graphName =
        selectedFlow?.name || "Custom Flow " + Math.floor(Math.random() * 1000);

      // Set the graph ID and name
      setBuiltGraphId(graphId);
      setBuiltGraphName(graphName);

      const selectedBlueprint = {
        blueprintId: graphId,
        userId: user?.username || "default",
      };

      const response = await axios.post(
        "/sessions/user.session.create",
        selectedBlueprint,
      );
      setSelectedGraphId(response.data);

      // Navigate to Agentic Chats page
      window.location.href = "/agentic-chats";
    } catch (error) {
      console.error("Error create new graph session:", error);
      toast({
        title: "Failed to load current workflow",
        description: `Error: ${error.response.data.error}`,
        variant: "destructive",
      });
    } finally {
      setIsLoadingFlow(false);
    }
  };

  const handleBuildGraph = () => {
    setShowGraphBuilder(true);
  };

  const handleBackToFlowConfig = () => {
    setShowGraphBuilder(false);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Agentic AI System"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <main className="flex-1 overflow-y-auto bg-background-dark">
          {showGraphBuilder ? (
            <NewGraph onBack={handleBackToFlowConfig} />
          ) : (
            <div className="p-6">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Card className="bg-background-card shadow-card border-gray-800 mb-6">
                  <CardHeader className="py-2 px-6 flex flex-row justify-between items-center">
                    <CardTitle className="text-lg font-heading">
                      Agent Workflow Configuration
                    </CardTitle>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleLoadFlow}
                        disabled={isLoadingFlow}
                        className="bg-primary hover:bg-[#7525c9] text-white flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <LoaderCircle className={`h-4 w-4 ${isLoadingFlow ? 'animate-spin' : ''}`} />
                        {isLoadingFlow ? 'Loading...' : 'Load Workflow'}
                      </Button>
                      <Button
                        className="bg-primary hover:bg-opacity-80 flex items-center gap-2"
                        size="sm"
                        onClick={handleBuildGraph}
                      >
                        <Plus className="h-4 w-4" />
                        Build Workflow
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-2 px-4 pb-4">
                    <p className="text-sm text-gray-400">
                      Configure your agent workflow. Select a pre-existing
                      flow and click "Load Workflow" to execute it, or click
                      "Build Workflow" to create a custom workflow with
                      drag-and-drop components.
                    </p>
                  </CardContent>
                </Card>

                <AgentFlowGraph
                  selectedFlow={selectedFlow}
                  setSelectedFlow={setSelectedFlow}
                />
              </motion.div>
            </div>
          )}
        </main>

        <StatusBar />
      </div>
    </div>
  );
}