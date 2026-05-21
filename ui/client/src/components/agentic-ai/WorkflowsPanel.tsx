import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { motion } from "framer-motion";
import { Trash2, Users, Pencil, Search, X, Copy } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { useShared } from "@/contexts/SharedContext";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { FlowObject } from "./graphs/interfaces";
import GraphDisplay from "./graphs/GraphDisplay";
import { fetchActiveSessions } from "@/api/agentic";
import { fetchBlueprintSummaries, deleteBlueprint, fetchResolvedBlueprint, duplicateBlueprint } from "@/api/blueprints";
import { convertGraphFlowToFlowObject } from "@/utils/blueprintHelpers";
import ShareWorkflow from "./ShareWorkflow";
import { BlueprintValidationResult } from "@/types/validation";
import { useBlueprintValidation } from "@/hooks/use-blueprint-validation";

export interface WorkflowsPanelProps {
  selectedFlow: FlowObject | null;
  onFlowSelect: (flow: FlowObject | null) => void;
  onFlowDelete?: (flow: FlowObject) => void;
  onFlowEdit?: (flow: FlowObject) => void;
  onValidationChange?: (isValid: boolean, validationResult: BlueprintValidationResult | null, isValidating: boolean) => void;
  showActiveStatus?: boolean;
  showDeleteButton?: boolean;
  showEditButton?: boolean;
  className?: string;
  height?: string;
  graphProps?: {
    showBackground?: boolean;
    interactive?: boolean;
  };
}

export default function WorkflowsPanel({
  selectedFlow,
  onFlowSelect,
  onFlowDelete,
  onFlowEdit,
  onValidationChange,
  showActiveStatus = false,
  showDeleteButton = false,
  showEditButton = false,
  className = "",
  height = "100%",
  graphProps = {
    showBackground: true,
    interactive: true,
  },
}: WorkflowsPanelProps): React.ReactElement {
  // State for available graph flows
  const [graphFlows, setGraphFlows] = useState<FlowObject[]>([]);
  const [activeFlowIds, setActiveFlowIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [flowToDelete, setFlowToDelete] = useState<FlowObject | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [isDuplicating, setIsDuplicating] = useState<string | null>(null);
  const duplicatingInFlight = useRef<Set<string>>(new Set());
  const [selectedBlueprintData, setSelectedBlueprintData] = useState<{
    specDict: any;
    sharingEnabled: boolean;
  } | null>(null);
  
  const [searchQuery, setSearchQuery] = useState<string>("");

  const { user } = useAuth();
  const { openShareForItem } = useShared();
  
  // Blueprint validation hook
  const {
    isValidating,
    validationResults,
    isValid,
    validateBlueprint: validateSelectedBlueprint,
    clearValidation,
  } = useBlueprintValidation({
    activeBlueprintId: selectedFlow?.id ?? null,
    onValidationChange,
    showToastOnFailure: true,
  });

  const filteredFlows = useMemo(() => {
    const normalizedSearch = (searchQuery ?? "").trim().toLowerCase();
    if (!normalizedSearch) return graphFlows;
    return graphFlows.filter(
      (flow) =>
        flow.name.toLowerCase().includes(normalizedSearch) ||
        flow.description.toLowerCase().includes(normalizedSearch),
    );
  }, [graphFlows, searchQuery]);

  // Fetch available blueprints from API (resolved – references replaced with actual data)
  const fetchAvailableFlows = async (): Promise<void> => {
    try {
      const userId = user?.username || "default";
      // Use summary endpoint - returns name, description, metadata without heavy spec_dict.
      // Full resolved data is fetched on selection for the graph + sharing status.
      const summaries = await fetchBlueprintSummaries(userId);

      // Convert summaries to FlowObject format
      const processedFlows = summaries
        .map((summary, index) =>
          convertGraphFlowToFlowObject(
            { name: summary.name, description: summary.description },
            index,
            summary.blueprint_id
          ),
        )
        .filter((flow): flow is FlowObject => flow !== null);
      
      setGraphFlows(processedFlows);

      // Auto-select the first flow if none is selected and flows are available
      if (processedFlows.length > 0 && !selectedFlow) {
        onFlowSelect(processedFlows[0]);
      }
    } catch (error) {
      console.error("Error fetching available blueprints:", error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch active flows (only if showActiveStatus is true)
  const fetchActiveFlows = async (): Promise<void> => {
    if (!showActiveStatus) return;

    try {
      const userId = user?.username || "default";
      const activeSessions = await fetchActiveSessions(userId);
      setActiveFlowIds(activeSessions || []);
    } catch (error) {
      console.error("Error fetching active flows:", error);
      setActiveFlowIds([]);
    }
  };

  // Effect to load graph flows from API
  useEffect(() => {
    setIsLoading(true);
    Promise.all([
      fetchAvailableFlows(),
      fetchActiveFlows(),
    ]).finally(() => {
      setIsLoading(false);
    });
  }, [user]);

  // Trigger validation when selected flow changes
  useEffect(() => {
    if (selectedFlow?.id) {
      validateSelectedBlueprint(selectedFlow.id);
    } else {
      // Clear validation state when no flow is selected
      clearValidation();
    }
  }, [selectedFlow?.id, validateSelectedBlueprint, clearValidation]);

  // Fetch blueprint data (spec_dict + metadata) when selected flow changes.
  // This consolidates API calls - data is fetched once and passed to child components.
  // A `cancelled` flag prevents stale responses from overwriting state when the
  // user switches flows quickly.
  useEffect(() => {
    if (!selectedFlow?.id) {
      setSelectedBlueprintData(null);
      return;
    }

    let cancelled = false;
    // Clear previous data immediately so the UI shows a loading state
    // instead of the previous flow's graph while the new fetch is in-flight.
    setSelectedBlueprintData(null);

    const fetchBlueprintData = async () => {
      try {
        const userId = user?.username || 'default';
        const blueprint = await fetchResolvedBlueprint(selectedFlow.id, userId);
        if (cancelled) return;
        if (blueprint) {
          setSelectedBlueprintData({
            specDict: blueprint.spec_dict,
            sharingEnabled: blueprint.metadata?.usageScope === "public",
          });
        }
      } catch (error) {
        if (cancelled) return;
        console.error("Error fetching blueprint data:", error);
        setSelectedBlueprintData(null);
      }
    };

    fetchBlueprintData();
    return () => { cancelled = true; };
  }, [selectedFlow?.id, user?.username]);

  const handleFlowSelect = (flow: FlowObject): void => {
    onFlowSelect(flow);
  };

  const isFlowActive = (flowId: string): boolean => {
    return activeFlowIds.includes(flowId);
  };

  const handleDeleteClick = (flow: FlowObject, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent flow selection when clicking delete
    setFlowToDelete(flow);
    setShowDeleteModal(true);
  };

  const handleEditClick = (flow: FlowObject, event: React.MouseEvent) => {
    event.stopPropagation();
    if (onFlowEdit) {
      onFlowEdit(flow);
    }
  };

  const handleShareClick = (flow: FlowObject, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent flow selection when clicking share
    openShareForItem({
      itemKind: 'blueprint',
      itemId: flow.id,
      itemName: flow.name,
    });
  };

  const handleDuplicateClick = async (flow: FlowObject, event: React.MouseEvent) => {
    event.stopPropagation();
    if (duplicatingInFlight.current.has(flow.id)) return;
    duplicatingInFlight.current.add(flow.id);
    setIsDuplicating(flow.id);
    try {
      const userId = user?.username || "default";
      await duplicateBlueprint(flow.id, userId);
      await fetchAvailableFlows();
    } catch (error) {
      console.error("Error duplicating blueprint:", error);
    } finally {
      duplicatingInFlight.current.delete(flow.id);
      setIsDuplicating(null);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!flowToDelete) return;

    setIsDeleting(true);
    try {
      await deleteBlueprint(flowToDelete.id);
      
      // Remove the deleted flow from the list
      setGraphFlows(prevFlows => prevFlows.filter(flow => flow.id !== flowToDelete.id));
      
      // If the deleted flow was selected, clear the selection
      if (selectedFlow?.id === flowToDelete.id) {
        onFlowSelect(null);
      }
      
      // Call the optional onFlowDelete callback
      if (onFlowDelete) {
        onFlowDelete(flowToDelete);
      }
      
      setShowDeleteModal(false);
      setFlowToDelete(null);
    } catch (error) {
      console.error('Error deleting blueprint:', error);
      // Handle error (we can consider show a toast notification here)
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setShowDeleteModal(false);
    setFlowToDelete(null);
  };

  // Expose flows data for parent components
  useEffect(() => {
    // This allows parent components to access the flows data if needed
    if (typeof onFlowSelect === 'function' && graphFlows.length > 0 && !selectedFlow) {
      onFlowSelect(graphFlows[0]);
    }
  }, [graphFlows, selectedFlow, onFlowSelect]);

  if (isLoading) {
    return (
      <div className={`flex h-full overflow-hidden ${className}`} style={{ height }}>
        <div className="w-1/3 border-r border-gray-800 bg-background-dark flex flex-col min-h-0">
          <div className="py-3 px-4 border-b border-gray-800 bg-background-surface flex-shrink-0">
            <h3 className="text-sm font-medium">Available Workflows</h3>
          </div>
          <div className="flex-1 flex items-center justify-center overflow-hidden">
            <div className="text-gray-400">Loading flows...</div>
          </div>
        </div>
        <div className="flex-grow min-h-0 overflow-hidden">
          <div className="flex items-center justify-center h-full text-gray-400">
            Loading...
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className={`flex h-full overflow-hidden ${className}`} style={{ height }}>
        {/* Available Workflows Sidebar */}
        <div className="w-1/3 border-r border-gray-800 bg-background-dark flex flex-col min-h-0 relative">
          <div className="py-3 px-4 border-b border-gray-800 bg-background-surface flex-shrink-0 space-y-2">
            <h3 className="text-sm font-medium">Available Workflows ({filteredFlows.length})</h3>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400 pointer-events-none" />
              <Input
                placeholder="Search workflows..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 pl-8 pr-8 text-xs bg-background-dark border-gray-700 focus:border-primary"
              />
              {searchQuery && (
                <SimpleTooltip content={<p>Clear search</p>}>
                  <button
                    type="button"
                    aria-label="Clear search"
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-200"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </SimpleTooltip>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto py-2 max-h-full relative">
            {filteredFlows.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-gray-400 text-sm text-center px-4">
                  {searchQuery.trim()
                    ? `No workflows match "${searchQuery.trim()}"`
                    : "No flows available"}
                </div>
              </div>
            ) : (
              filteredFlows.map((flow) => (
                <motion.div
                  key={flow.id}
                  className={`px-4 py-2 border-l-2 cursor-pointer ${
                    selectedFlow?.id === flow.id
                      ? "border-primary bg-primary/20"
                      : "border-transparent hover:bg-background-surface"
                  }`}
                  onClick={() => handleFlowSelect(flow)}
                  whileHover={{ x: 2 }}
                  transition={{ duration: 0.1 }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center min-w-0 flex-1">
                      {flow.icon}
                      <span className="text-sm font-medium truncate">{flow.name}</span>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {showActiveStatus && isFlowActive(flow.id) && (
                        <span className="text-xs bg-primary text-white px-2 py-1 rounded-full">
                          Active
                        </span>
                      )}
                      {showEditButton && (
                        <SimpleTooltip content={<p>Edit this workflow</p>}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0 hover:bg-primary/20 hover:text-primary"
                            onClick={(e) => handleEditClick(flow, e)}
                          >
                            <Pencil className="h-3 w-3" />
                          </Button>
                        </SimpleTooltip>
                      )}
                      <SimpleTooltip content={<p>Share this workflow</p>}>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 hover:bg-blue-500/20 hover:text-blue-400"
                          onClick={(e) => handleShareClick(flow, e)}
                        >
                          <Users className="h-3 w-3" />
                        </Button>
                      </SimpleTooltip>
                      <SimpleTooltip content={<p>Duplicate this workflow</p>}>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 hover:bg-green-500/20 hover:text-green-400"
                          onClick={(e) => handleDuplicateClick(flow, e)}
                          disabled={isDuplicating === flow.id}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </SimpleTooltip>
                      {showDeleteButton && (
                        <SimpleTooltip content={<p>Delete this workflow</p>}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0 hover:bg-red-500/20 hover:text-red-400"
                            onClick={(e) => handleDeleteClick(flow, e)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </SimpleTooltip>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 truncate">
                    {flow.description}
                  </p>
                </motion.div>
              ))
            )}
          </div>
        </div>

        {/* Graph Visualization and Share Section */}
        <div className="flex-grow min-h-0 overflow-hidden flex flex-col">
          {selectedFlow ? (
            <>
              {/* Share Section */}
              <div className="border-b border-gray-800 bg-background-surface p-4">
                <ShareWorkflow 
                  blueprintId={selectedFlow.id} 
                  isValid={isValid}
                  isValidating={isValidating}
                  initialSharingEnabled={selectedBlueprintData?.sharingEnabled ?? false}
                />
              </div>
            {selectedBlueprintData?.specDict ? (
              <GraphDisplay
                blueprintId={selectedFlow.id}
                specDict={selectedBlueprintData.specDict}
                height="100%"
                showBackground={graphProps?.showBackground}
                interactive={graphProps?.interactive}
                centerInView={true}
                animated={true}
                validationResults={validationResults}
                isValidating={isValidating}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400">
                Loading graph...
              </div>
            )}
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              Select a flow to view its visualization
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteButton && (
        <Dialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
          <DialogContent className="bg-background-card border-gray-800">
            <DialogHeader>
              <DialogTitle>Delete Flow</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete "{flowToDelete?.name}"?
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={handleDeleteCancel}
                disabled={isDeleting}
                className="bg-background-dark border-gray-700 hover:bg-background-surface"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteConfirm}
                disabled={isDeleting}
              >
                {isDeleting ? "Deleting..." : "Confirm"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
