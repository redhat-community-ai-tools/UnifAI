import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StreamingDataProvider } from "@/components/agentic-ai/StreamingDataContext";
import { FlowObject } from "./graphs/interfaces";
import WorkflowsPanel from "./WorkflowsPanel";
import { BlueprintValidationResult } from "@/types/validation";

// Create a ReactFlow provider wrapper
import { ReactFlowProvider } from "reactflow";

type AgentFlowGraphProps = {
  selectedFlow: FlowObject | null;
  setSelectedFlow: (flow: FlowObject | null) => void;
  onFlowEdit?: (blueprintId: string) => void;
  onValidationChange?: (isValid: boolean, validationResult: BlueprintValidationResult | null, isValidating: boolean) => void;
};

export default function AgentFlowGraph({
  selectedFlow,
  setSelectedFlow,
  onFlowEdit,
  onValidationChange,
}: AgentFlowGraphProps): React.ReactElement {
  
  const handleFlowSelect = (flow: FlowObject | null): void => {
    setSelectedFlow(flow);
  };

  const handleFlowDelete = (flow: FlowObject): void => {
    // If the deleted flow was selected, clear the selection
    if (selectedFlow?.id === flow.id) {
      setSelectedFlow(null);
    }
  };

  const handleFlowEdit = (flow: FlowObject): void => {
    if (onFlowEdit) {
      onFlowEdit(flow.id);
    }
  };

  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardHeader className="py-4 px-6 flex flex-row justify-between items-center">
        <CardTitle className="text-lg font-heading">
          Agent Workflow Visualization
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0" style={{ height: "73.5vh" }}>
        <StreamingDataProvider>
          <ReactFlowProvider>
            <WorkflowsPanel
              selectedFlow={selectedFlow}
              onFlowSelect={handleFlowSelect}
              onFlowDelete={handleFlowDelete}
              onFlowEdit={handleFlowEdit}
              onValidationChange={onValidationChange}
              showActiveStatus={true}
              showDeleteButton={true}
              showEditButton={true}
              useResolvedEndpoint={true}
              height="100%"
              graphProps={{
                showControls: true,
                showMiniMap: false,
                showBackground: true,
                interactive: true,
                isLiveRequest: false,
              }}
            />
          </ReactFlowProvider>
        </StreamingDataProvider>
      </CardContent>
    </Card>
  );
}