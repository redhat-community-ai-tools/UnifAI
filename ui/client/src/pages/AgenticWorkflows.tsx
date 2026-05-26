import React, { useState, useCallback } from "react";
import { useLocation } from "wouter";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { useAuth } from "@/contexts/AuthContext";
import { useAgenticAI } from "@/contexts/AgenticAIContext";
import { useView } from "@/contexts/ViewContext";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import { Plus, LoaderCircle, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

import AgentFlowGraph from "@/components/agentic-ai/AgentFlowGraph";
import NewGraph from "../workspace/NewGraph";
import type { SavedBlueprintInfo } from "@/hooks/use-graph-creation-logic";
import axios from "../http/axiosAgentConfig";

import { FlowObject } from "@/components/agentic-ai/graphs/interfaces";
import { BlueprintValidationResult } from "@/types/validation";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';

export interface GraphNode {
  id: string;
  name: string;
  description: string | null;
}

export default function AgenticWorkflows() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedFlow, setSelectedFlow] = useState<FlowObject | null>(null);
  const [builtGraphId, setBuiltGraphId] = useState<string | null>(null);
  const [builtGraphName, setBuiltGraphName] = useState<string | null>(null);
  const [selectedGraphId, setSelectedGraphId] = useState<string | null>(null);
  const [showGraphBuilder, setShowGraphBuilder] = useState(false);
  const [editingBlueprintId, setEditingBlueprintId] = useState<string | null>(null);
  const [isLoadingFlow, setIsLoadingFlow] = useState(false);
  const [isFlowValid, setIsFlowValid] = useState<boolean>(true);
  const [isValidatingFlow, setIsValidatingFlow] = useState<boolean>(false);
  const [currentValidationResult, setCurrentValidationResult] = useState<BlueprintValidationResult | null>(null);
  const { user } = useAuth();
  const { toast } = useToast();
  const { cacheBlueprintValidationResults } = useAgenticAI();
  const { selectedTeam } = useView();
  const { isTeam: isTeamWorkspace, userId: contextUserId, displayName: userDisplayName, identityType } = useWorkspaceIdentity();
  const [, navigate] = useLocation();
  
  // Handle validation changes from the flow graph
  const handleValidationChange = useCallback((isValid: boolean, validationResult: BlueprintValidationResult | null, isValidating: boolean) => {
    setIsFlowValid(isValid);
    setCurrentValidationResult(validationResult);
    setIsValidatingFlow(isValidating);
    
    // Cache all element validation results from the the blueprint.validate API response
    if (validationResult) {
      cacheBlueprintValidationResults(validationResult);
    }
  }, [cacheBlueprintValidationResults]);

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

      if (!isTeamWorkspace && !user?.username) {
        toast({
          title: "Authentication required",
          description: "Sign in before starting a workflow session.",
          variant: "destructive",
        });
        setIsLoadingFlow(false);
        return;
      }

      const selectedBlueprint = {
        blueprintId: graphId,
        userId: contextUserId,
        displayName: userDisplayName,
        identityType,
      };

      const response = await axios.post(
        "/sessions/user.session.create",
        selectedBlueprint,
      );
      const sessionId = response.data;
      setSelectedGraphId(sessionId);

      // Navigate to Agentic Chats page, passing the new session ID so it auto-selects
      navigate(`/agentic-chats?runId=${encodeURIComponent(sessionId)}`);
    } catch (error: any) {
      console.error("Error create new graph session:", error);
      toast({
        title: "Failed to load current workflow",
        description: `Error: ${error?.response?.data?.error || error?.message || 'Unknown error'}`,
        variant: "destructive",
      });
    } finally {
      setIsLoadingFlow(false);
    }
  };

  const handleOpenGraphBuilder = (flow?: FlowObject) => {
    setEditingBlueprintId(flow?.id ?? null);
    setShowGraphBuilder(true);
  };

  const handleBackToFlowConfig = useCallback((_savedBlueprint?: SavedBlueprintInfo) => {
    setShowGraphBuilder(false);
    setEditingBlueprintId(null);
    
    if (_savedBlueprint?.blueprintId) {
      setSelectedFlow({
        id: _savedBlueprint.blueprintId,
        name: _savedBlueprint.name,
        description: _savedBlueprint.description,
        icon: null,
      });
    } else {
      // Going back without saving (new build or edit) — clear selection so
      // WorkflowsPanel remounts cleanly and auto-selects a flow.
      setSelectedFlow(null);
    }
  }, []);

  return (
    <>
      <Header
        title={isTeamWorkspace ? `Team Workflows — ${selectedTeam?.name ?? 'Team'}` : "Agentic AI System"}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

        <main className="flex-1 overflow-y-auto bg-background-dark">
          {showGraphBuilder ? (
            <NewGraph
              onBack={handleBackToFlowConfig}
              editBlueprintId={editingBlueprintId}
            />
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
                      <SimpleTooltip 
                        content={
                          !selectedFlow ? (
                            <p>Select a workflow first</p>
                          ) : !isFlowValid && !isValidatingFlow ? (
                            <p>Cannot load workflow: Validation failed. Fix the issues before loading.</p>
                          ) : isValidatingFlow ? (
                            <p>Validating workflow...</p>
                          ) : null
                        }
                      >
                        <UmamiTrack 
                          event={UmamiEvents.AGENT_GRAPHS_LOAD_FLOW_BUTTON}
                          eventData={{ flowName: selectedFlow?.name }}
                        >
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleLoadFlow}
                            disabled={isLoadingFlow || !isFlowValid || isValidatingFlow || !selectedFlow}
                            className={`${
                              !selectedFlow || isValidatingFlow
                              ? 'bg-gray-600 text-gray-300 border-gray-600'
                              : !isFlowValid
                              ? 'bg-gray-600 text-gray-400 border-gray-600' 
                              : 'bg-primary hover:bg-primary/80 text-white'
                            } flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed`}
                          >
                            {isValidatingFlow ? (
                              <LoaderCircle className="h-4 w-4 animate-spin" />
                            ) : !isFlowValid ? (
                              <AlertTriangle className="h-4 w-4 text-yellow-500" />
                            ) : (
                              <LoaderCircle className={`h-4 w-4 ${isLoadingFlow ? 'animate-spin' : ''}`} />
                            )}
                            {isValidatingFlow ? 'Validating...' : isLoadingFlow ? 'Loading...' : !isFlowValid ? 'Validation Failed' : 'Load Workflow'}
                          </Button>
                        </UmamiTrack>
                      </SimpleTooltip>
                        <UmamiTrack 
                          event={UmamiEvents.AGENT_GRAPHS_BUILD_FLOW_BUTTON}
                        >
                          <Button
                            className="bg-primary hover:bg-opacity-80 flex items-center gap-2"
                            size="sm"
                            onClick={() => handleOpenGraphBuilder()}
                          >
                            <Plus className="h-4 w-4" />
                            Build Workflow
                          </Button>
                        </UmamiTrack>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-2 px-4 pb-4">
                    <p className="text-sm text-gray-400">
                      {isTeamWorkspace
                        ? `Browse and manage shared workflows for ${selectedTeam?.name ?? 'your team'}. Select a workflow and click "Load Workflow" to execute it, or build a new one to share with your team.`
                        : 'Configure your agent workflow. Select a pre-existing flow and click "Load Workflow" to execute it, or click "Build Workflow" to create a custom workflow with drag-and-drop components.'}
                    </p>
                  </CardContent>
                </Card>

                <AgentFlowGraph
                  selectedFlow={selectedFlow}
                  setSelectedFlow={setSelectedFlow}
                  onValidationChange={handleValidationChange}
                  onFlowEdit={handleOpenGraphBuilder}
                />
              </motion.div>
            </div>
          )}
        </main>

        <StatusBar />
    </>
  );
}