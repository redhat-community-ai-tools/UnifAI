import { useState, useMemo } from "react";
import { useGraphCreationLogic, SavedBlueprintInfo } from "@/hooks/use-graph-creation-logic";
import GraphCreation from "@/components/agentic-ai/graphs/GraphCreation";
import BuildingBlocksSidebar from "./BuildingBlocksSidebar";
import GraphValidationPanel from "@/components/agentic-ai/graphs/GraphValidationPanel";
import SaveBlueprintModal from "@/components/agentic-ai/graphs/SaveBlueprintModal";

interface NewGraphProps {
  onBack?: (savedBlueprint?: SavedBlueprintInfo) => void;
  editBlueprintId?: string | null;
}

export default function NewGraph({ onBack, editBlueprintId }: NewGraphProps) {
  const {
    nodes,
    edges,
    buildingBlocksData,
    orchestratorsData,
    conditionsData,
    isLoadingBlocks,
    yamlFlow,
    onDrop,
    onDragOver,
    onDragStart,
    clearGraph,
    saveGraph,
    deleteNode,
    deleteEdge,
    updateNodePosition,
    pendingConnectionSource,
    handleNodeClickForConnection,
    handlePaneClick,
    cancelConnectionMode,
    attachConditionToNode,
    onDragEnd,
    isGraphValid,
    validationResult,
    fixSuggestions,
    isValidating,
    isSaving,
    isEditMode,
    isLoadingBlueprint,
    editBlueprintName,
    editBlueprintDescription,
  } = useGraphCreationLogic({
    onSaveComplete: onBack,
    editBlueprintId,
    onEditLockDenied: () => onBack?.(),
  });

  const [saveModalOpen, setSaveModalOpen] = useState(false);

  // Track which building blocks are currently used on the canvas
  const usedElementIds = useMemo(() => {
    const usedIds = new Set<string>();
    const allSidebarBlocks = [...buildingBlocksData, ...orchestratorsData, ...conditionsData];
    
    nodes.forEach(node => {
      // 1. Track the node itself by workspaceData.rid
      if (node.data?.workspaceData?.rid) {
        const matchingBlock = allSidebarBlocks.find(
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
  }, [nodes, buildingBlocksData, orchestratorsData, conditionsData]);

  const handleSaveGraph = async () => {
    setSaveModalOpen(true);
  };

  const handleClearGraph = () => {
    clearGraph();
  };

  return (
    <div className="h-full max-h-[calc(100vh-100px)] flex bg-background overflow-hidden">
      {/* Sidebar */}
      <div className="h-full flex-shrink-0">
        <BuildingBlocksSidebar
          buildingBlocks={buildingBlocksData}
          orchestrators={orchestratorsData}
          conditions={conditionsData}
          isLoading={isLoadingBlocks}
          onDragStart={onDragStart}
          usedElementIds={usedElementIds}
        />
      </div>

      {/* Main Canvas */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <GraphCreation
          nodes={nodes}
          edges={edges}
          yamlFlow={yamlFlow}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onClearGraph={handleClearGraph}
          onSaveGraph={handleSaveGraph}
          onDeleteNode={deleteNode}
          onDeleteEdge={deleteEdge}
          onBack={onBack}
          isGraphValid={isGraphValid}
          onNodeClick={handleNodeClickForConnection}
          onPaneClick={handlePaneClick}
          onNodePositionChange={updateNodePosition}
          pendingConnectionSource={pendingConnectionSource}
          onCancelConnection={cancelConnectionMode}
          onAttachCondition={attachConditionToNode}
          onDragEnd={onDragEnd}
          isEditMode={isEditMode}
          isLoadingBlueprint={isLoadingBlueprint}
        />
      </div>

      {/* Validation Panel */}
      <div className="w-80 h-full">
        <GraphValidationPanel
          validationResult={validationResult}
          fixSuggestions={fixSuggestions}
          isValidating={isValidating}
          isLoadingBlueprint={isLoadingBlueprint}
        />
      </div>

      {/* Save Blueprint Modal */}
      <SaveBlueprintModal
        isOpen={saveModalOpen}
        onClose={() => setSaveModalOpen(false)}
        onSave={saveGraph}
        isLoading={isSaving}
        isEditMode={isEditMode}
        currentName={editBlueprintName}
        currentDescription={editBlueprintDescription}
      />
    </div>
  );
}
