import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Header from "@/components/layout/Header";
import { Button } from "@/components/ui/button";
import { Plus, Info } from 'lucide-react';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { CategorySidebar } from '../components/agentic-ai/workspace/CategorySidebar';
import { ElementGrid } from '../components/agentic-ai/workspace/ElementGrid';
import { ElementForm } from '../components/agentic-ai/workspace/ElementForm';
import { ElementType, ElementInstance } from '../types/workspace';
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import { useItemSelection } from '@/hooks/use-item-selection';
import { useBulkDelete } from '@/hooks/use-bulk-delete';
import { SelectionModeControls } from '@/components/shared/SelectionModeControls';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { useView } from "@/contexts/ViewContext";

export default function UserWorkspace() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedElementType, setSelectedElementType] = useState<ElementType | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingElement, setEditingElement] = useState<ElementInstance | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [elementToDelete, setElementToDelete] = useState<ElementInstance | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isResourceSelectionMode, setIsResourceSelectionMode] = useState(false);
  const { viewMode, selectedTeam } = useView();
  const isTeam = viewMode === "team";
  const {
    selection,
    setSelection,
    selectedCount,
    clearSelection,
    pruneToIds,
  } = useItemSelection();
  const {
    categories,
    elementInstances,
    elementSchema,
    elementActions,
    isLoading,
    isLoadingInstances,
    fetchElementInstances,
    fetchElementSchema,
    fetchElementActions,
    saveElement,
    deleteElement,
    deleteElementsBulk,
  } = useWorkspaceData();

  const {
    bulkDeleteConfirm,
    setBulkDeleteConfirm,
    bulkDeleteLoading,
    handleDeleteSelected,
    confirmBulkDelete: confirmBulkDeleteBase,
  } = useBulkDelete({
    deleteFunction: deleteElementsBulk,
    queryKeys: [],
    itemName: 'resource',
    onSuccess: () => {
      clearSelection();
      setIsResourceSelectionMode(false);
      if (selectedElementType) {
        fetchElementInstances(selectedElementType.category, selectedElementType.type);
      }
    },
  });

  useEffect(() => {
    if (selectedElementType) {
      fetchElementInstances(selectedElementType.category, selectedElementType.type);
    }
  }, [selectedElementType, fetchElementInstances, viewMode, selectedTeam?.id]);

  useEffect(() => {
    const ids = new Set(elementInstances.map((el) => el.rid));
    pruneToIds(ids);
  }, [elementInstances, pruneToIds]);

  const exitResourceSelectionMode = useCallback(() => {
    clearSelection();
    setIsResourceSelectionMode(false);
  }, [clearSelection]);

  const allResourcesSelected = useMemo(
    () =>
      elementInstances.length > 0 &&
      elementInstances.every((el) => selection[el.rid] === true),
    [elementInstances, selection],
  );

  const selectAllResources = useCallback(() => {
    setSelection((prev) => {
      const next = { ...prev };
      elementInstances.forEach((el) => {
        next[el.rid] = true;
      });
      return next;
    });
  }, [elementInstances, setSelection]);

  const handleElementTypeSelect = async (category: string, elementType: ElementType) => {
    setSelectedCategory(category);
    setSelectedElementType(elementType);
    await Promise.all([
      fetchElementSchema(category, elementType.type),
      fetchElementActions(category, elementType.type)
    ]);
  };

  const handleCreateNew = () => {
    setEditingElement(null);
    setIsFormOpen(true);
  };

  const handleEditElement = (element: ElementInstance) => {
    setEditingElement(element);
    setIsFormOpen(true);
  };

  const existingNames = useMemo(
    () =>
      elementInstances
        .map((el) => el.name)
        .filter((name): name is string => !!name),
    [elementInstances],
  );

  const handleSaveElement = async (elementData: any) => {
    if (!selectedElementType) return null;
    const result = await saveElement(
      selectedElementType.category,
      selectedElementType.type,
      elementData,
      editingElement?.rid,
    );
    if (result) {
      fetchElementInstances(selectedElementType.category, selectedElementType.type);
    }
    return result;
  };

  const handleDeleteElement = (rid: string) => {
    const element = elementInstances.find(el => el.rid === rid);
    if (element) {
      setElementToDelete(element);
      setShowDeleteModal(true);
    }
  };

  const confirmDeleteElement = async () => {
    if (!elementToDelete || !selectedElementType) return;
    setIsDeleting(true);
    try {
      await deleteElement(elementToDelete.rid);
      await fetchElementInstances(selectedElementType.category, selectedElementType.type);
      setShowDeleteModal(false);
      setElementToDelete(null);
    } catch (error) {
      console.error('Error deleting element:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  const cancelDeleteElement = () => {
    setShowDeleteModal(false);
    setElementToDelete(null);
  };

  return (
    <>
      <Header title={isTeam ? "Team Inventory" : "User Workspace"} onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

      <main className="flex-1 overflow-y-auto p-6 bg-background-dark">
        <div className="grid grid-cols-12 gap-6 h-full">
          <div className="col-span-12 md:col-span-3 lg:col-span-2">
            <CategorySidebar
              categories={categories}
              selectedCategory={selectedCategory}
              selectedElementType={selectedElementType}
              onElementTypeSelect={handleElementTypeSelect}
              isLoading={isLoading}
            />
          </div>

          <div className="col-span-12 md:col-span-9 lg:col-span-10">
            <div className="flex flex-col h-full">
              {selectedElementType && (
                <div className="flex justify-between items-center gap-4 mb-6 sticky top-0 z-10 pb-4 pt-px -mt-px bg-[hsl(var(--background-dark))] shadow-[0_4px_12px_-2px_rgba(0,0,0,0.4)]">
                  <div className="min-w-0 flex-1">
                    <h2 className="text-2xl font-heading font-bold">
                      {selectedElementType.name} Instances
                    </h2>
                    <p className="text-gray-400 text-sm">
                      {isTeam
                        ? `Shared ${selectedElementType.name.toLowerCase()} configurations from your team`
                        : `Manage your ${selectedElementType.name.toLowerCase()} configurations`}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                    <SelectionModeControls
                      entityPluralLabel="resources"
                      isSelectionMode={isResourceSelectionMode}
                      onEnterSelectionMode={() => setIsResourceSelectionMode(true)}
                      onExitSelectionMode={exitResourceSelectionMode}
                      selectedCount={selectedCount}
                      onBulkDeleteClick={() => handleDeleteSelected(selection)}
                      bulkDeleteDisabled={bulkDeleteLoading || isDeleting}
                      itemNameForDelete={selectedCount === 1 ? 'resource' : 'resources'}
                      totalSelectable={elementInstances.length}
                      allSelected={allResourcesSelected}
                      onSelectAll={selectAllResources}
                      onClearSelection={clearSelection}
                    />
                    <Button
                      variant="outline"
                      onClick={() => {
                        const guidesUrl = `/guides?section=agentic-inventory`;
                        window.open(guidesUrl, '_blank');
                      }}
                      className="border-gray-700 hover:bg-background-dark"
                      title="View guides"
                    >
                      <Info className="h-4 w-4" />
                    </Button>

                    <UmamiTrack
                      event={UmamiEvents.AGENT_REPOSITORY_CREATE_NEW_BUTTON}
                      eventData={{ elementType: selectedElementType?.name }}
                    >
                      <Button
                        onClick={handleCreateNew}
                        className="bg-primary hover:bg-opacity-80"
                        disabled={!elementSchema}
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Create New
                      </Button>
                    </UmamiTrack>
                  </div>
                </div>
              )}

              <div className="flex-1">
                {selectedElementType ? (
                  <ElementGrid
                    elements={elementInstances}
                    elementType={selectedElementType}
                    isLoading={isLoadingInstances}
                    onEditElement={handleEditElement}
                    onDeleteElement={handleDeleteElement}
                    elementSchema={elementSchema}
                    rowSelection={selection}
                    onRowSelectionChange={isResourceSelectionMode ? setSelection : undefined}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center text-gray-400">
                      <p className="text-lg font-medium mb-2">Select an element type</p>
                      <p className="text-sm">Choose a category and element type from the sidebar to view instances</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {isFormOpen && selectedElementType && elementSchema && (
          <ElementForm
            isOpen={isFormOpen}
            onClose={() => setIsFormOpen(false)}
            elementType={selectedElementType}
            elementSchema={elementSchema}
            elementActions={elementActions}
            editingElement={editingElement}
            existingNames={existingNames}
            onSave={handleSaveElement}
          />
        )}
      </main>

      <AlertDialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {selectedElementType?.name || 'Element'}</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{elementToDelete?.name || `${selectedElementType?.name || 'Element'} Instance`}"?
              <br /><br />
              <strong>Be aware that this action is irreversible.</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={cancelDeleteElement}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteElement}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <ConfirmDialog
        open={bulkDeleteConfirm.open}
        title="Delete Selected Resources"
        message={`Are you sure you want to delete ${bulkDeleteConfirm.count} selected resource${bulkDeleteConfirm.count > 1 ? 's' : ''}? This action cannot be undone.`}
        confirmLabel="Yes, Delete"
        cancelLabel="Cancel"
        loading={bulkDeleteLoading}
        onCancel={() => {
          if (!bulkDeleteLoading) {
            setBulkDeleteConfirm({ open: false, count: 0 });
          }
        }}
        onConfirm={() => confirmBulkDeleteBase(selection)}
      />
    </>
  );
}
