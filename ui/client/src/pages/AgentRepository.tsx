import React, { useState, useEffect, useMemo } from 'react';
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
import { useView } from "@/contexts/ViewContext";
import { cn } from "@/lib/utils";

type ResourceFilter = "all" | "built-in" | "personal";

const MOCK_BUILTIN_INSTANCES: Record<string, ElementInstance[]> = {
  openai: [
    {
      rid: "builtin-openai-gpt4o",
      name: "GPT-4o",
      type: "openai",
      category: "llms",
      config: {
        model_name: "gpt-4o",
        base_url: "https://api.openai.com/v1",
        temperature: 0.7,
        max_tokens: 4096,
        verify_ssl: true,
      },
      version: 1,
      isBuiltIn: true,
    },
  ],
  mcp_server: [
    {
      rid: "builtin-mcp-github",
      name: "GitHub MCP",
      type: "mcp_server",
      category: "providers",
      config: {
        mcp_url: "https://mcp.github.com/sse",
        transport_type: "streamable http",
        auth_method: "access_token",
        tool_names: ["get_repo", "list_issues", "create_issue", "search_code"],
        additional_headers: {},
      },
      version: 1,
      isBuiltIn: true,
    },
  ],
  web_fetch: [
    {
      rid: "builtin-tool-webfetch",
      name: "Web Fetch",
      type: "web_fetch",
      category: "tools",
      config: {},
      version: 1,
      isBuiltIn: true,
    },
  ],
  deep_agent_node: [
    {
      rid: "builtin-node-deep-agent",
      name: "Research Assistant",
      type: "deep_agent_node",
      category: "nodes",
      config: {
        system_message: "You are a thorough research assistant.",
        retries: 1,
      },
      version: 1,
      isBuiltIn: true,
    },
  ],
};

export default function UserWorkspace() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedElementType, setSelectedElementType] = useState<ElementType | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingElement, setEditingElement] = useState<ElementInstance | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [elementToDelete, setElementToDelete] = useState<ElementInstance | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [resourceFilter, setResourceFilter] = useState<ResourceFilter>("all");
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
    saveElement,
    deleteElement
  } = useWorkspaceData();

  const builtInForType = useMemo(() => {
    if (!selectedElementType) return [];
    return MOCK_BUILTIN_INSTANCES[selectedElementType.type] ?? [];
  }, [selectedElementType]);

  const mergedInstances = useMemo(() => {
    return [...builtInForType, ...elementInstances];
  }, [builtInForType, elementInstances]);

  const filteredInstances = useMemo(() => {
    if (resourceFilter === "all") return mergedInstances;
    if (resourceFilter === "built-in") return mergedInstances.filter(el => el.isBuiltIn);
    return mergedInstances.filter(el => !el.isBuiltIn);
  }, [mergedInstances, resourceFilter]);

  const filterCounts = useMemo(() => ({
    all: mergedInstances.length,
    "built-in": mergedInstances.filter(el => el.isBuiltIn).length,
    personal: mergedInstances.filter(el => !el.isBuiltIn).length,
  }), [mergedInstances]);

  useEffect(() => {
    if (selectedElementType) {
      fetchElementInstances(selectedElementType.category, selectedElementType.type);
    }
  }, [selectedElementType, fetchElementInstances, viewMode, selectedTeam?.id]);

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

                  {/* Resource filter tabs */}
                  <div className="flex items-center gap-1 mt-4 p-1 bg-background-card rounded-lg border border-gray-800 w-fit">
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

              <div className="flex-1">
                {selectedElementType ? (
                  <ElementGrid
                    elements={filteredInstances}
                    elementType={selectedElementType}
                    isLoading={isLoadingInstances}
                    onEditElement={handleEditElement}
                    onDeleteElement={handleDeleteElement}
                    elementSchema={elementSchema}
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
    </>
  );
}
