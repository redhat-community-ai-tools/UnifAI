import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { motion } from "framer-motion";
import { Trash2, Users, Pencil, Search, X, MoreVertical, MessageSquare } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useView } from "@/contexts/ViewContext";
import { useShared } from "@/contexts/SharedContext";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { Switch } from "@/components/ui/switch";
import { ShieldCheck } from "lucide-react";
import { FlowObject } from "./graphs/interfaces";
import GraphDisplay from "./graphs/GraphDisplay";
import {
  fetchBlueprintSummaries,
  deleteBlueprint,
  deleteBlueprintsByIds,
  fetchResolvedBlueprint,
  setPromptShortcuts,
  PromptShortcutInput,
} from "@/api/blueprints";
import { convertGraphFlowToFlowObject } from "@/utils/blueprintHelpers";
import { hasHitlDynamicNodes } from "@/utils/hitlUtils";
import ShareWorkflow from "./ShareWorkflow";
import EditPromptShortcutsModal from "./EditPromptShortcutsModal";
import { BlueprintValidationResult } from "@/types/validation";
import { useBlueprintValidation } from "@/hooks/use-blueprint-validation";
import { useItemSelection } from "@/hooks/use-item-selection";
import { useBulkDelete } from "@/hooks/use-bulk-delete";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { SelectionCheckbox } from "@/components/shared/SelectionCheckbox";
import { SelectionModeControls } from "@/components/shared/SelectionModeControls";
import { useTeamEditLockPoll } from "@/hooks/use-team-edit-lock-poll";
import { cn } from "@/lib/utils";

export interface WorkflowsPanelProps {
  selectedFlow: FlowObject | null;
  onFlowSelect: (flow: FlowObject | null) => void;
  onFlowDelete?: (flow: FlowObject) => void;
  onFlowEdit?: (flow: FlowObject) => void;
  onValidationChange?: (isValid: boolean, validationResult: BlueprintValidationResult | null, isValidating: boolean) => void;
  /** HITL toggle state for dynamic nodes. */
  hitlEnabled?: boolean;
  /** Callback when the user toggles HITL for dynamic nodes. */
  onHitlToggle?: (enabled: boolean) => void;
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
  hitlEnabled = false,
  onHitlToggle,
  showDeleteButton = false,
  showEditButton = false,
  className = "",
  height = "100%",
  graphProps = {
    showBackground: true,
    interactive: true,
  },
}: WorkflowsPanelProps): React.ReactElement {
  const [graphFlows, setGraphFlows] = useState<FlowObject[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [flowToDelete, setFlowToDelete] = useState<FlowObject | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [selectedBlueprintData, setSelectedBlueprintData] = useState<{
    specDict: any;
    sharingEnabled: boolean;
  } | null>(null);
  
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isWorkflowSelectionMode, setIsWorkflowSelectionMode] = useState(false);
  const [promptShortcutsModalOpen, setPromptShortcutsModalOpen] = useState(false);
  const [promptShortcutsFlow, setPromptShortcutsFlow] = useState<FlowObject | null>(null);

  const {
    selection,
    setSelection,
    selectedCount,
    clearSelection,
    pruneToIds,
  } = useItemSelection();

  const {
    bulkDeleteConfirm,
    setBulkDeleteConfirm,
    bulkDeleteLoading,
    handleDeleteSelected,
    confirmBulkDelete: confirmBulkDeleteWorkflows,
  } = useBulkDelete({
    deleteFunction: deleteBlueprintsByIds,
    queryKeys: [],
    itemName: "workflow",
    onSuccess: (deletedIds) => {
      clearSelection();
      setIsWorkflowSelectionMode(false);
      const deletedSet = new Set(deletedIds);
      setGraphFlows((prev) => prev.filter((f) => !deletedSet.has(f.id)));
      if (selectedFlow && deletedSet.has(selectedFlow.id)) {
        onFlowSelect(null);
      }
    },
  });

  const { selectedTeam } = useView();
  const { openShareForItem } = useShared();
  const { isTeam, userId: contextUserId, identityType } = useWorkspaceIdentity();
  const workspaceScopeRef = useRef({ contextUserId, identityType });
  workspaceScopeRef.current = { contextUserId, identityType };
  
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

  const blueprintEditLocks = useTeamEditLockPoll(
    selectedTeam?.id,
    "blueprint",
    graphFlows.map((f) => f.id),
    isTeam && graphFlows.length > 0,
  );

  const hasDynamicNodes = useMemo(
    () => hasHitlDynamicNodes(selectedBlueprintData?.specDict),
    [selectedBlueprintData?.specDict],
  );

  const filteredFlows = useMemo(() => {
    const normalizedSearch = (searchQuery ?? "").trim().toLowerCase();
    if (!normalizedSearch) return graphFlows;
    return graphFlows.filter(
      (flow) =>
        flow.name.toLowerCase().includes(normalizedSearch) ||
        flow.description.toLowerCase().includes(normalizedSearch),
    );
  }, [graphFlows, searchQuery]);

  useEffect(() => {
    pruneToIds(new Set(filteredFlows.map((f) => f.id)));
  }, [filteredFlows, pruneToIds]);

  const exitWorkflowSelectionMode = useCallback(() => {
    clearSelection();
    setIsWorkflowSelectionMode(false);
  }, [clearSelection]);

  const allFilteredWorkflowsSelected = useMemo(
    () =>
      filteredFlows.length > 0 &&
      filteredFlows.every((f) => selection[f.id] === true),
    [filteredFlows, selection],
  );

  const selectAllFilteredWorkflows = useCallback(() => {
    setSelection((prev) => {
      const next = { ...prev };
      filteredFlows.forEach((f) => {
        next[f.id] = true;
      });
      return next;
    });
  }, [filteredFlows, setSelection]);

  // Fetch available blueprints from API (resolved – references replaced with actual data).
  // `forceAutoSelect` bypasses the `selectedFlow` check so the first item is always
  // picked after a scope change (where the closure still sees the stale value).
  const fetchAvailableFlows = async (forceAutoSelect = false): Promise<void> => {
    const scopeAtStart = { contextUserId, identityType };
    try {
      const summaries = await fetchBlueprintSummaries(contextUserId, identityType);

      if (
        workspaceScopeRef.current.contextUserId !== scopeAtStart.contextUserId ||
        workspaceScopeRef.current.identityType !== scopeAtStart.identityType
      ) {
        return;
      }

      const processedFlows = summaries
        .map((summary, index) =>
          convertGraphFlowToFlowObject(
            {
              name: summary.name,
              description: summary.description,
              contributedBy: summary.metadata?.contributed_by,
            },
            index,
            summary.blueprint_id
          ),
        )
        .filter((flow): flow is FlowObject => flow !== null);
      
      setGraphFlows(processedFlows);

      // Auto-select the first flow if none is selected and flows are available
      if (processedFlows.length > 0 && (forceAutoSelect || !selectedFlow)) {
        onFlowSelect(processedFlows[0]);
      }
    } catch (error) {
      console.error("Error fetching available blueprints:", error);
      throw error;
    } finally {
      if (
        workspaceScopeRef.current.contextUserId === scopeAtStart.contextUserId &&
        workspaceScopeRef.current.identityType === scopeAtStart.identityType
      ) {
        setIsLoading(false);
      }
    }
  };

  useEffect(() => {
    onFlowSelect(null);
    setSelectedBlueprintData(null);
    setGraphFlows([]);
    setIsLoading(true);
    fetchAvailableFlows(true).finally(() => {
      setIsLoading(false);
    });
  }, [contextUserId, identityType]);

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
        const blueprint = await fetchResolvedBlueprint(
          selectedFlow.id,
          contextUserId,
          identityType,
          isTeam ? selectedTeam!.name : undefined,
        );
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
  }, [selectedFlow?.id, contextUserId]);

  const handleFlowSelect = (flow: FlowObject): void => {
    onFlowSelect(flow);
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

  const handlePromptShortcutsClick = (flow: FlowObject, event: React.MouseEvent) => {
    event.stopPropagation();
    setPromptShortcutsFlow(flow);
    setPromptShortcutsModalOpen(true);
  };

  const handleSavePromptShortcuts = async (prompts: PromptShortcutInput[]) => {
    if (!promptShortcutsFlow) return;
    await setPromptShortcuts(promptShortcutsFlow.id, prompts, contextUserId, identityType);
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
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-sm font-medium leading-tight pt-0.5">
                Available Workflows ({filteredFlows.length})
              </h3>
              {showDeleteButton && (
                <SelectionModeControls
                  entityPluralLabel="workflows"
                  isSelectionMode={isWorkflowSelectionMode}
                  onEnterSelectionMode={() => setIsWorkflowSelectionMode(true)}
                  onExitSelectionMode={exitWorkflowSelectionMode}
                  selectedCount={selectedCount}
                  onBulkDeleteClick={() => handleDeleteSelected(selection)}
                  bulkDeleteDisabled={bulkDeleteLoading || isDeleting}
                  itemNameForDelete={selectedCount === 1 ? "workflow" : "workflows"}
                  totalSelectable={filteredFlows.length}
                  allSelected={allFilteredWorkflowsSelected}
                  onSelectAll={selectAllFilteredWorkflows}
                  onClearSelection={clearSelection}
                  compact
                />
              )}
            </div>
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
              filteredFlows.map((flow) => {
                const bpLock = blueprintEditLocks[flow.id];
                const bpLockUnknown = bpLock === "unknown";
                const bpLockedByOther =
                  isTeam &&
                  !bpLockUnknown &&
                  !!bpLock &&
                  !!contextUserId &&
                  bpLock.userId !== contextUserId;
                const bpLockedByLabel = bpLockUnknown
                  ? "unknown"
                  : bpLock?.displayName?.trim() || bpLock?.userId || "another teammate";

                return (
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
                    <div className="flex items-center min-w-0 flex-1 gap-1">
                      {showDeleteButton && isWorkflowSelectionMode && (
                        <div className="shrink-0" onClick={(e) => e.stopPropagation()}>
                          <SelectionCheckbox
                            checked={selection[flow.id] === true}
                            onCheckedChange={(checked) => {
                              const next = { ...selection };
                              if (checked) next[flow.id] = true;
                              else delete next[flow.id];
                              setSelection(next);
                            }}
                            ariaLabel={`Select workflow ${flow.name}`}
                          />
                        </div>
                      )}
                      {flow.icon}
                      <span className="text-sm font-medium truncate">{flow.name}</span>
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {selectedFlow?.id === flow.id && hasDynamicNodes && onHitlToggle && (
                        <SimpleTooltip content={<p>{hitlEnabled ? "Disable" : "Enable"} Human-in-the-Loop for dynamic nodes</p>}>
                          <div
                            className="flex items-center gap-1 cursor-pointer"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ShieldCheck className={cn(
                              "h-3 w-3 transition-colors",
                              hitlEnabled ? "text-yellow-500" : "text-gray-500",
                            )} />
                            <Switch
                              aria-label={`${hitlEnabled ? "Disable" : "Enable"} Human-in-the-Loop for dynamic nodes`}
                              checked={hitlEnabled}
                              onCheckedChange={onHitlToggle}
                              className="h-4 w-7 data-[state=checked]:bg-yellow-600 data-[state=unchecked]:bg-gray-600 [&>span]:h-3 [&>span]:w-3 [&>span]:data-[state=checked]:translate-x-3"
                            />
                          </div>
                        </SimpleTooltip>
                      )}
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Open actions for ${flow.name}`}
                            className="h-6 w-6 p-0 hover:bg-background-surface"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <MoreVertical className="h-3.5 w-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="bg-background-card border-gray-800 min-w-[160px]">
                          {showEditButton && (
                            <DropdownMenuItem
                              className={cn(
                                "cursor-pointer",
                                (bpLockedByOther || bpLockUnknown) && "opacity-50 pointer-events-none",
                              )}
                              disabled={bpLockedByOther || bpLockUnknown}
                              onClick={(e) => handleEditClick(flow, e as unknown as React.MouseEvent)}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                              <span>
                                {bpLockUnknown
                                  ? "Edit (lock unknown)"
                                  : bpLockedByOther
                                    ? `Locked by ${bpLockedByLabel}`
                                    : "Edit workflow"}
                              </span>
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem
                            className="cursor-pointer"
                            onClick={(e) => handleShareClick(flow, e as unknown as React.MouseEvent)}
                          >
                            <Users className="h-3.5 w-3.5" />
                            <span>Share workflow</span>
                          </DropdownMenuItem>
                          {showEditButton && (
                            <DropdownMenuItem
                              className={cn(
                                "cursor-pointer",
                                (bpLockedByOther || bpLockUnknown) && "opacity-50 pointer-events-none",
                              )}
                              disabled={bpLockedByOther || bpLockUnknown}
                              onClick={(e) => handlePromptShortcutsClick(flow, e as unknown as React.MouseEvent)}
                            >
                              <MessageSquare className="h-3.5 w-3.5" />
                              <span>Prompt Shortcuts</span>
                            </DropdownMenuItem>
                          )}
                          {showDeleteButton && (
                            <>
                              <DropdownMenuSeparator className="bg-gray-800" />
                              <DropdownMenuItem
                                className="cursor-pointer text-red-400 focus:text-red-400 focus:bg-red-500/10"
                                onClick={(e) => handleDeleteClick(flow, e as unknown as React.MouseEvent)}
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                                <span>Delete workflow</span>
                              </DropdownMenuItem>
                            </>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 truncate">
                    {flow.description}
                  </p>
                  {flow.contributedBy && (
                    <div className="flex items-center gap-1 mt-1">
                      <span className="inline-flex items-center gap-1 text-[10px] text-primary bg-primary/10 px-1.5 py-0.5 rounded-full">
                        <Users className="h-2.5 w-2.5" />
                        {flow.contributedBy}
                      </span>
                    </div>
                  )}
                </motion.div>
                );
              })
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
                hitlEnabled={hitlEnabled}
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
      <ConfirmDialog
        open={bulkDeleteConfirm.open}
        title="Delete Selected Workflows"
        message={`Are you sure you want to delete ${bulkDeleteConfirm.count} selected workflow${bulkDeleteConfirm.count > 1 ? "s" : ""}? This action cannot be undone.`}
        confirmLabel="Yes, Delete"
        cancelLabel="Cancel"
        loading={bulkDeleteLoading}
        onCancel={() => {
          if (!bulkDeleteLoading) {
            setBulkDeleteConfirm({ open: false, count: 0 });
          }
        }}
        onConfirm={() => confirmBulkDeleteWorkflows(selection)}
      />

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

      {/* Prompt Shortcuts Modal */}
      <EditPromptShortcutsModal
        isOpen={promptShortcutsModalOpen}
        onClose={() => setPromptShortcutsModalOpen(false)}
        blueprintId={promptShortcutsFlow?.id || ""}
        userId={contextUserId}
        identityType={identityType}
        onSave={handleSavePromptShortcuts}
      />
    </>
  );
}
