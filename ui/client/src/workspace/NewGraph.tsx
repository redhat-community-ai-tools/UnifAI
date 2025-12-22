import React, { useState, useMemo } from "react";
import { useGraphLogic } from "@/hooks/use-graph-logic/use-graph-logic";
import GraphCanvas from "@/components/agentic-ai/graphs/GraphCanvas";
import BuildingBlocksSidebar from "./BuildingBlocksSidebar";
import ConditionalEdgeModal from "@/components/agentic-ai/graphs/ConditionalEdgeModal";
import GraphValidationPanel from "@/components/agentic-ai/graphs/GraphValidationPanel";
import SaveBlueprintModal from "@/components/agentic-ai/graphs/SaveBlueprintModal";

interface NewGraphProps {
  onBack?: () => void;
  editBlueprintId?: string | null;
}

export default function NewGraph({ onBack, editBlueprintId }: NewGraphProps) {
  const {
    nodes,
    edges,
    buildingBlocksData,
    conditionsData,
    allBlocksData,
    isLoadingBlocks,
    yamlFlow,
    handleNodesChange,
    handleEdgesChange,
    onConnect,
    onDrop,
    onDragOver,
    onDragStart,
    clearGraph,
    saveGraph,
    deleteEdge,
    attachConditionToNode,
    removeConditionFromNode,
    conditionalEdgeModal,
    handleConditionalEdgeConfirm,
    handleConditionalEdgeCancel,
    isGraphValid,
    validationResult,
    fixSuggestions,
    isValidating,
    isSaving,
    // Edit mode state
    isEditMode,
    isLoadingBlueprint,
    blueprintName,
    blueprintDescription,
  } = useGraphLogic({ editBlueprintId });

  const [saveModalOpen, setSaveModalOpen] = useState(false);

  // Track which building blocks are currently used on the canvas
  const usedElementIds = useMemo(() => {
    const usedIds = new Set<string>();
    
    nodes.forEach(node => {
      // 1. Track the node itself by workspaceData.rid
      if (node.data?.workspaceData?.rid) {
        const matchingBlock = [...buildingBlocksData, ...conditionsData].find(
          block => block.workspaceData?.rid === node.data.workspaceData?.rid
        );
        if (matchingBlock) {
          usedIds.add(matchingBlock.id);
        }
      }
      
      // 2. Track any conditions attached to this node
      if (node.data?.referencedConditions && Array.isArray(node.data.referencedConditions)) {
        node.data.referencedConditions.forEach((condition: any) => {
          if (condition.workspaceData?.rid) {
            const matchingCondition = conditionsData.find(
              block => block.workspaceData?.rid === condition.workspaceData.rid
            );
            if (matchingCondition) {
              usedIds.add(matchingCondition.id);
            }
          }
        });
      }
    });
    
    return usedIds;
  }, [nodes, buildingBlocksData, conditionsData]);

  const handleSaveGraph = async () => {
    setSaveModalOpen(true);
  };

  const handleClearGraph = () => {
    clearGraph();
  };

  // Show loading state while loading blueprint for edit
  if (isLoadingBlueprint) {
    return (
      <div className="h-full max-h-[calc(100vh-100px)] flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <p className="text-gray-400">Loading blueprint for editing...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full max-h-[calc(100vh-100px)] flex bg-background overflow-hidden">
      {/* Sidebar */}
      <div className="w-80 h-full">
        <BuildingBlocksSidebar
          buildingBlocks={buildingBlocksData}
          conditions={conditionsData}
          isLoading={isLoadingBlocks}
          onDragStart={onDragStart}
          usedElementIds={usedElementIds}
        />
      </div>

      {/* Main Canvas */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <GraphCanvas
          nodes={nodes}
          edges={edges}
          yamlFlow={yamlFlow}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={onConnect}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onClearGraph={handleClearGraph}
          onSaveGraph={handleSaveGraph}
          onDeleteEdge={deleteEdge}
          onBack={onBack}
          onAttachCondition={attachConditionToNode}
          onRemoveCondition={removeConditionFromNode}
          isGraphValid={isGraphValid}
        />
      </div>

      {/* Validation Panel */}
      <div className="w-80 h-full">
        <GraphValidationPanel
          validationResult={validationResult}
          fixSuggestions={fixSuggestions}
          isValidating={isValidating}
        />
      </div>

      {/* Conditional Edge Modal */}
      <ConditionalEdgeModal
        isOpen={conditionalEdgeModal.isOpen}
        onClose={handleConditionalEdgeCancel}
        onConfirm={handleConditionalEdgeConfirm}
        sourceNodeId={conditionalEdgeModal.sourceNodeId}
        targetNodeId={conditionalEdgeModal.targetNodeId}
        conditionType={conditionalEdgeModal.conditionType}
        existingBranches={conditionalEdgeModal.existingBranches}
      />

      {/* Save Blueprint Modal */}
      <SaveBlueprintModal
        isOpen={saveModalOpen}
        onClose={() => setSaveModalOpen(false)}
        onSave={saveGraph}
        isLoading={isSaving}
        isEditMode={isEditMode}
        initialName={blueprintName}
        initialDescription={blueprintDescription}
      />
    </div>
  );
}
