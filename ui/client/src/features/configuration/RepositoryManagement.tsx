import { useState, useCallback, useMemo, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus } from "lucide-react";
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { useBuiltinEditLockPoll } from "@/hooks/use-builtin-edit-lock-poll";
import { useBuiltinEditLockSession } from "@/hooks/use-builtin-edit-lock-session";
import { acquireBuiltinEditLock } from "@/api/resources";
import { ElementForm } from "@/components/agentic-ai/workspace/ElementForm";
import { ElementData } from "@/components/agentic-ai/workspace/ElementData";
import type { ElementType, ElementInstance } from "@/types/workspace";
import { AddResourceWizardPanel } from "./repository-management/AddResourceWizardPanel";
import { BuiltinResourceTable } from "./repository-management/BuiltinResourceTable";
import { DeleteResourceDialog } from "./repository-management/DeleteResourceDialog";
import { BUILTIN_DISABLED_CATEGORIES, type ResourceItem, type WizardStep } from "./repository-management/types";

export default function RepositoryManagement() {
  const {
    categories,
    elementSchema,
    elementActions,
    isLoading,
    fetchElementSchema,
    fetchElementActions,
    configureBuiltin,
    saveBuiltinElement,
    toggleBuiltinStatus,
    deleteBuiltinElement,
  } = useWorkspaceData();
  const { toast } = useToast();

  const [step, setStep] = useState<WizardStep>("idle");
  const [selectedCategoryKey, setSelectedCategoryKey] = useState<string>("");
  const [selectedElementType, setSelectedElementType] =
    useState<ElementType | null>(null);
  const [isLoadingSchema, setIsLoadingSchema] = useState(false);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingElement, setEditingElement] = useState<ElementInstance | null>(
    null,
  );
  const [configuringBuiltin, setConfiguringBuiltin] = useState<ResourceItem | null>(null);

  const [categoryResources, setCategoryResources] = useState<
    Record<string, ResourceItem[]>
  >({});
  const [availableToAll, setAvailableToAll] = useState<
    Record<string, boolean>
  >({});

  const [deleteTarget, setDeleteTarget] = useState<ResourceItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const [typeFilters, setTypeFilters] = useState<Record<string, string>>({});

  const [detailsElement, setDetailsElement] =
    useState<ElementInstance | null>(null);
  const [detailsElementType, setDetailsElementType] =
    useState<ElementType | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  const [newElementAvailableToAll, setNewElementAvailableToAll] = useState(false);
  const [isTogglingStatus, setIsTogglingStatus] = useState<string | null>(null);

  const { user } = useAuth();
  const currentUsername = user?.username ?? "";

  const allBuiltinRids = useMemo(
    () => Object.values(categoryResources).flat().map((r) => r.rid),
    [categoryResources],
  );
  const editLocks = useBuiltinEditLockPoll(allBuiltinRids, allBuiltinRids.length > 0);
  const { startLockHeartbeat, stopLockHeartbeat } = useBuiltinEditLockSession();

  const availableCategories = useMemo(
    () => categories.filter(
      (c) => c.elements.length > 0 && !BUILTIN_DISABLED_CATEGORIES.has(c.category)
    ),
    [categories],
  );

  const selectedCategoryElements = useMemo(() => {
    if (!selectedCategoryKey) return [];
    return (
      availableCategories.find((c) => c.category === selectedCategoryKey)
        ?.elements ?? []
    );
  }, [selectedCategoryKey, availableCategories]);

  const reloadBuiltins = useCallback(async () => {
    try {
      const { listBuiltins } = await import("@/api/resources");
      const data = await listBuiltins();
      const resources = data.resources || [];
      const grouped: Record<string, ResourceItem[]> = {};
      const newAvailable: Record<string, boolean> = {};
      for (const r of resources) {
        const cat = r.category?.toLowerCase() || "other";
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push({
          rid: r.rid,
          name: r.name,
          type: r.type,
          config: r.cfg_dict,
          category: cat,
          ownership: r.ownership || 'builtin',
          visibility: r.visibility || 'draft',
        });
        newAvailable[r.rid] = r.visibility === "public";
      }
      setCategoryResources(grouped);
      setAvailableToAll(newAvailable);
    } catch (err) {
      console.error("Failed to load built-in resources:", err);
      toast({
        title: "Error",
        description: "Failed to load built-in resources. Please refresh the page.",
        variant: "destructive",
      });
    }
  }, [toast]);

  useEffect(() => {
    reloadBuiltins();
  }, [reloadBuiltins]);

  const handleAddNew = () => {
    setStep("select-category");
    setSelectedCategoryKey("");
    setSelectedElementType(null);
  };

  const handleAddToCategory = useCallback((categoryKey: string) => {
    setStep("select-category");
    setSelectedCategoryKey(categoryKey);
    setSelectedElementType(null);
  }, []);

  const handleCategoryChange = (value: string) => {
    setSelectedCategoryKey(value);
    setSelectedElementType(null);
  };

  const handleTypeChange = (value: string) => {
    const el = selectedCategoryElements.find((e) => e.type === value) ?? null;
    setSelectedElementType(el);
  };

  const resolveElementType = (
    categoryKey: string,
    typeKey: string,
  ): ElementType | null => {
    const cat = availableCategories.find((c) => c.category === categoryKey);
    return cat?.elements.find((e) => e.type === typeKey) ?? null;
  };

  const handleNext = useCallback(async () => {
    if (!selectedElementType) return;
    setIsLoadingSchema(true);
    try {
      await Promise.all([
        fetchElementSchema(
          selectedElementType.category,
          selectedElementType.type,
        ),
        fetchElementActions(
          selectedElementType.category,
          selectedElementType.type,
        ),
      ]);
      setEditingElement(null);
      setIsFormOpen(true);
      setStep("configure");
    } finally {
      setIsLoadingSchema(false);
    }
  }, [selectedElementType, fetchElementSchema, fetchElementActions]);

  const handleEditResource = useCallback(
    async (resource: ResourceItem) => {
      const categoryKey = resource.category!;
      const elType = resolveElementType(categoryKey, resource.type);
      if (!elType) return;

      const lockResult = await acquireBuiltinEditLock(resource.rid);
      if (!lockResult.acquired) {
        const who = (lockResult as any).lockedBy?.displayName || "Another admin";
        alert(`Cannot edit — currently locked by ${who}`);
        return;
      }
      startLockHeartbeat(resource.rid);

      setSelectedCategoryKey(categoryKey);
      setSelectedElementType(elType);
      setIsLoadingSchema(true);
      setStep("configure");
      setNewElementAvailableToAll(resource.visibility === "public");

      try {
        await Promise.all([
          fetchElementSchema(categoryKey, resource.type),
          fetchElementActions(categoryKey, resource.type),
        ]);
        setEditingElement({
          rid: resource.rid,
          name: resource.name,
          config: resource.config,
          category: categoryKey,
          type: resource.type,
        });
        setIsFormOpen(true);
      } finally {
        setIsLoadingSchema(false);
      }
    },
    [availableCategories, fetchElementSchema, fetchElementActions, startLockHeartbeat],
  );

  const handleSaveBuiltinConfig = async (elementData: any) => {
    if (!configuringBuiltin) return null;
    const result = await configureBuiltin(
      configuringBuiltin.rid,
      elementData.cfg_dict || elementData,
    );
    return result;
  };

  const handleViewDetails = (resource: ResourceItem) => {
    const categoryKey = resource.category!;
    const elType = resolveElementType(categoryKey, resource.type);
    setDetailsElement({
      rid: resource.rid,
      name: resource.name,
      config: resource.config,
      category: categoryKey,
      type: resource.type,
    });
    setDetailsElementType(elType);
    setIsDetailsOpen(true);
  };

  const handleSaveElement = async (elementData: any) => {
    if (!selectedElementType) return null;
    const result = await saveBuiltinElement(
      selectedElementType.category,
      selectedElementType.type,
      elementData,
      newElementAvailableToAll,
      editingElement?.rid,
    );
    if (result) {
      reloadBuiltins();
    }
    return result;
  };

  const handleFormClose = () => {
    stopLockHeartbeat();
    setIsFormOpen(false);
    setEditingElement(null);
    setConfiguringBuiltin(null);
    setStep("idle");
    setSelectedCategoryKey("");
    setSelectedElementType(null);
    setNewElementAvailableToAll(false);
  };

  const handleBack = () => {
    setStep("idle");
    setSelectedCategoryKey("");
    setSelectedElementType(null);
  };

  const handleDeleteClick = (resource: ResourceItem) => {
    setDeleteTarget(resource);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      const success = await deleteBuiltinElement(deleteTarget.rid);
      if (success) {
        reloadBuiltins();
      }
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  };

  const toggleAvailableToAll = async (rid: string) => {
    const currentValue = availableToAll[rid] ?? false;
    const newValue = !currentValue;
    setIsTogglingStatus(rid);
    const result = await toggleBuiltinStatus(rid, newValue);
    if (result) {
      setAvailableToAll((prev) => ({ ...prev, [rid]: newValue }));
    }
    setIsTogglingStatus(null);
  };

  const handleTypeFilterChange = (category: string, value: string) => {
    setTypeFilters((prev) => ({ ...prev, [category]: value }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-heading font-semibold">
            Repository Management
          </h2>
          <p className="text-sm text-gray-400 mt-1 max-w-2xl">
            Create and manage built-in resources that are available to all users.
            Add pre-configured LLMs, Agents, Providers, Tools, and more to the
            shared repository.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="text-xs text-amber-400 border-amber-400/30"
          >
            Admin Only
          </Badge>
          <Button
            onClick={handleAddNew}
            className="bg-primary hover:bg-primary/80"
            size="sm"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add New
          </Button>
        </div>
      </div>

      <AddResourceWizardPanel
        step={step}
        availableCategories={availableCategories}
        selectedCategoryKey={selectedCategoryKey}
        selectedCategoryElements={selectedCategoryElements}
        selectedElementType={selectedElementType}
        isLoadingSchema={isLoadingSchema}
        newElementAvailableToAll={newElementAvailableToAll}
        editingElementName={editingElement?.name}
        onCategoryChange={handleCategoryChange}
        onTypeChange={handleTypeChange}
        onAvailableToAllChange={setNewElementAvailableToAll}
        onBack={handleBack}
        onNext={handleNext}
        onCancel={handleFormClose}
      />

      <BuiltinResourceTable
        isLoading={isLoading}
        availableCategories={availableCategories}
        categoryResources={categoryResources}
        typeFilters={typeFilters}
        availableToAll={availableToAll}
        isTogglingStatus={isTogglingStatus}
        editLocks={editLocks}
        currentUsername={currentUsername}
        onTypeFilterChange={handleTypeFilterChange}
        onToggleAvailableToAll={toggleAvailableToAll}
        onViewDetails={handleViewDetails}
        onEditResource={handleEditResource}
        onDeleteClick={handleDeleteClick}
        onAddToCategory={handleAddToCategory}
      />

      {/* ElementForm Dialog (create & edit, including built-in configure) */}
      {isFormOpen && selectedElementType && elementSchema && (
        <ElementForm
          isOpen={isFormOpen}
          onClose={handleFormClose}
          elementType={selectedElementType}
          elementSchema={elementSchema}
          elementActions={elementActions}
          editingElement={editingElement}
          existingNames={[]}
          onSave={configuringBuiltin ? handleSaveBuiltinConfig : handleSaveElement}
          builtinOnly
        />
      )}

      {/* View Details Dialog */}
      {isDetailsOpen && detailsElement && detailsElementType && (
        <ElementData
          element={detailsElement}
          elementType={detailsElementType}
          isOpen={isDetailsOpen}
          onOpenChange={setIsDetailsOpen}
          elementSchema={elementSchema}
        />
      )}

      <DeleteResourceDialog
        target={deleteTarget}
        isDeleting={isDeleting}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
