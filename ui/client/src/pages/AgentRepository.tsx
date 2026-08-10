import React, { useState, useEffect, useMemo, useRef } from 'react';
import Header from "@/components/layout/Header";
import { Button } from "@/components/ui/button";
import { Plus, Search, X } from 'lucide-react';
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { CategorySidebar } from '../components/agentic-ai/workspace/CategorySidebar';
import { ElementGrid } from '../components/agentic-ai/workspace/ElementGrid';
import { ElementForm } from '../components/agentic-ai/workspace/ElementForm';
import {
  WorkspaceElementDeletionFlow,
  type WorkspaceElementDeletionFlowHandle,
} from '../components/agentic-ai/workspace/WorkspaceElementDeletionFlow';
import { ElementType, ElementInstance } from '../types/workspace';
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import { useView } from "@/contexts/ViewContext";
import { cn } from "@/lib/utils";

type ResourceFilter = "all" | "built-in" | "personal";

export default function UserWorkspace() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedElementType, setSelectedElementType] = useState<ElementType | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingElement, setEditingElement] = useState<ElementInstance | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [resourceFilter, setResourceFilter] = useState<ResourceFilter>("all");
  const deletionFlowRef = useRef<WorkspaceElementDeletionFlowHandle>(null);
  const { viewMode, selectedTeam } = useView();
  const isTeam = viewMode === "team";

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
    fetchResourcesForCategory,
    fetchResourceById,
    checkElementUsage,
    saveElement,
    deleteElement,
    forceDeleteElement,
    configureBuiltin,
  } = useWorkspaceData();

  const deletionWorkspace = useMemo(
    () => ({
      fetchElementInstances,
      fetchResourceById,
      checkElementUsage,
      deleteElement,
      forceDeleteElement,
      fetchResourcesForCategory,
    }),
    [
      fetchElementInstances,
      fetchResourceById,
      checkElementUsage,
      deleteElement,
      forceDeleteElement,
      fetchResourcesForCategory,
    ],
  );

  const filterCounts = useMemo(() => ({
    all: elementInstances.length,
    "built-in": elementInstances.filter(el => el.ownership === 'builtin').length,
    personal: elementInstances.filter(el => el.ownership !== 'builtin').length,
  }), [elementInstances]);

  const filteredInstances = useMemo(() => {
    let instances = elementInstances;
    if (resourceFilter === "built-in") {
      instances = instances.filter(el => el.ownership === 'builtin');
    } else if (resourceFilter === "personal") {
      instances = instances.filter(el => el.ownership !== 'builtin');
    }

    const query = searchQuery.trim().toLowerCase();
    if (!query) return instances;
    return instances.filter(el => el.name?.toLowerCase().includes(query));
  }, [elementInstances, resourceFilter, searchQuery]);

  useEffect(() => {
    if (selectedElementType) {
      setResourceFilter("all");
      fetchElementInstances(selectedElementType.category, selectedElementType.type);
    }
  }, [selectedElementType, fetchElementInstances, viewMode, selectedTeam?.id]);

  const handleElementTypeSelect = async (category: string, elementType: ElementType) => {
    setSelectedCategory(category);
    setSelectedElementType(elementType);
    setSearchQuery("");
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
                <div className="mb-6 sticky top-0 z-10 pb-4 pt-px -mt-px bg-[hsl(var(--background-dark))] shadow-[0_4px_12px_-2px_rgba(0,0,0,0.4)]">
                  <div className="flex justify-between items-center">
                    <div>
                      <h2 className="text-2xl font-heading font-bold">
                        {selectedElementType.name} Instances
                      </h2>
                      <p className="text-gray-400 text-sm">
                        {isTeam
                          ? `Shared ${selectedElementType.name.toLowerCase()} configurations from your team`
                          : `Manage your ${selectedElementType.name.toLowerCase()} configurations`}
                      </p>
                    </div>
                    <div className="flex gap-2">
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

                  {/* Resource filter tabs */}
                  <div className="flex items-center gap-1 mt-4 p-1 bg-background-card rounded-lg border border-white/10 w-fit">
                    {([
                      { key: "all" as const, label: "All" },
                      { key: "built-in" as const, label: "Built-in" },
                      { key: "personal" as const, label: "My Resources" },
                    ]).map(({ key, label }) => (
                      <button
                        key={key}
                        onClick={() => setResourceFilter(key)}
                        className={cn(
                          "px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                          resourceFilter === key
                            ? "bg-primary text-white shadow-sm"
                            : "text-gray-400 hover:text-gray-200 hover:bg-white/5"
                        )}
                      >
                        {label}
                        <span className={cn(
                          "ml-1.5 text-[10px] tabular-nums",
                          resourceFilter === key ? "text-white/70" : "text-gray-500"
                        )}>
                          {filterCounts[key]}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {selectedElementType && elementInstances.length > 0 && (
                <div className="relative mb-4">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={`Search ${selectedElementType.name.toLowerCase()}s by name...`}
                    className="w-full pl-9 pr-9 py-2 text-sm bg-background-card border border-white/10 rounded-md text-gray-200 placeholder-gray-500 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/25 transition-colors"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery("")}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              )}

              <div className="flex-1">
                {!selectedElementType ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center text-gray-400">
                      <p className="text-lg font-medium mb-2">Select an element type</p>
                      <p className="text-sm">Choose a category and element type from the sidebar to view instances</p>
                    </div>
                  </div>
                ) : searchQuery && filteredInstances.length === 0 && !isLoadingInstances ? (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                    <Search className="h-12 w-12 mb-4 opacity-50" />
                    <h3 className="text-lg font-medium mb-2">No matches found</h3>
                    <p className="text-sm">
                      No {selectedElementType.name.toLowerCase()}s matching "{searchQuery}"
                    </p>
                  </div>
                ) : (
                  <ElementGrid
                    elements={filteredInstances}
                    elementType={selectedElementType}
                    isLoading={isLoadingInstances}
                    onEditElement={handleEditElement}
                    onDeleteElement={(rid) =>
                      deletionFlowRef.current?.handleDeleteElement(rid)
                    }
                    onConfigureBuiltin={configureBuiltin}
                    elementSchema={elementSchema}
                  />
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

      <WorkspaceElementDeletionFlow
        ref={deletionFlowRef}
        selectedElementType={selectedElementType}
        elementInstances={elementInstances}
        categories={categories}
        workspace={deletionWorkspace}
      />
    </>
  );
}
