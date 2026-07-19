import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StreamingDataProvider } from "@/components/agentic-ai/StreamingDataContext";
import { FlowObject } from "./graphs/interfaces";
import WorkflowsPanel from "./WorkflowsPanel";
import { BlueprintValidationResult } from "@/types/validation";

type AgentFlowGraphProps = {
  selectedFlow: FlowObject | null;
  setSelectedFlow: (flow: FlowObject | null) => void;
  onValidationChange?: (isValid: boolean, validationResult: BlueprintValidationResult | null, isValidating: boolean) => void;
  onFlowEdit?: (flow: FlowObject) => void;
  hitlEnabled?: boolean;
  onHitlToggle?: (enabled: boolean) => void;
};

export default function AgentFlowGraph({
  selectedFlow,
  setSelectedFlow,
  onValidationChange,
  onFlowEdit,
  hitlEnabled,
  onHitlToggle,
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

  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardHeader className="py-4 px-6 flex flex-row justify-between items-center">
        <CardTitle className="text-lg font-heading">
          Agent Workflow Visualization
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0" style={{ height: "73.5vh" }}>
        <StreamingDataProvider>
          <WorkflowsPanel
            selectedFlow={selectedFlow}
            onFlowSelect={handleFlowSelect}
            onFlowDelete={handleFlowDelete}
            onFlowEdit={onFlowEdit}
            onValidationChange={onValidationChange}
            hitlEnabled={hitlEnabled}
            onHitlToggle={onHitlToggle}
            showDeleteButton={true}
            showEditButton={true}
            height="100%"
            graphProps={{
              showBackground: true,
              interactive: true,
            }}
          />
        </StreamingDataProvider>
      </CardContent>
    </Card>
  );
}