import { useState, useCallback, useMemo, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus } from "lucide-react";
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { useBuiltinEditLockPoll } from "@/hooks/use-builtin-edit-lock-poll";
import { useBuiltinEditLockSession } from "@/hooks/use-builtin-edit-lock-session";
import { acquireBuiltinEditLock, previewBuiltinCascade, listBuiltins } from "@/api/resources";
import type { ResourceDependencySummary } from "@/api/resources";
import { ElementForm } from "@/components/agentic-ai/workspace/ElementForm";
import { ElementData } from "@/components/agentic-ai/workspace/ElementData";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import type { ElementType, ElementInstance } from "@/types/workspace";
import { AddResourceWizardPanel } from "./repository-management/AddResourceWizardPanel";
import { BuiltinResourceTable } from "./repository-management/BuiltinResourceTable";
import { CascadeConfirmDialog } from "./repository-management/CascadeConfirmDialog";
import { BUILTIN_DISABLED_CATEGORIES, type ResourceItem, type WizardStep } from "./repository-management/types";

export default function RepositoryManagement() {
  const {
    categories,
    elementSchema,
    elementActions,
    isLoading,
    fetchElementSchema,
    fetchElementActions,
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

  const [cascadePreview, setCascadePreview] = useState<{
    rid: string;
    resourceName: string;
    cascaded: ResourceDependencySummary[];
  } | null>(null);
  const [isApplyingCascade, setIsApplyingCascade] = useState(false);

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
      const [schema] = await Promise.all([
        fetchElementSchema(
          selectedElementType.category,
          selectedElementType.type,
        ),
        fetchElementActions(
          selectedElementType.category,
          selectedElementType.type,
        ),
      ]);
      if (!schema) {
        // fetchElementSchema already surfaces its own error toast — just
        // abort the wizard step transition, matching the edit path's unwind.
        return;
      }
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

      let lockResult;
      try {
        lockResult = await acquireBuiltinEditLock(resource.rid);
      } catch {
        toast({
          title: "Error",
          description: "Failed to acquire edit lock. Please try again.",
          variant: "destructive",
        });
        return;
      }
      if (!lockResult.acquired) {
        toast({
          title: "Resource locked",
          description: `Cannot edit — currently locked by ${lockResult.lockedBy?.displayName || "Another admin"}`,
          variant: "destructive",
        });
        return;
      }
      startLockHeartbeat(resource.rid);

      setSelectedCategoryKey(categoryKey);
      setSelectedElementType(elType);
      setIsLoadingSchema(true);
      setStep("configure");
      setNewElementAvailableToAll(resource.visibility === "public");

      try {
        const [schema] = await Promise.all([
          fetchElementSchema(categoryKey, resource.type),
          fetchElementActions(categoryKey, resource.type),
        ]);
        if (!schema) {
          // fetchElementSchema/fetchElementActions already surface their own
          // error toast — just unwind the lock + wizard state here.
          stopLockHeartbeat();
          setIsFormOpen(false);
          setEditingElement(null);
          setStep("idle");
          setSelectedCategoryKey("");
          setSelectedElementType(null);
          setNewElementAvailableToAll(false);
          return;
        }
        setEditingElement({
          rid: resource.rid,
          name: resource.name,
          config: resource.config,
          category: categoryKey,
          type: resource.type,
        });
        setIsFormOpen(true);
      } catch {
        stopLockHeartbeat();
        setIsFormOpen(false);
        setEditingElement(null);
        setStep("idle");
        setSelectedCategoryKey("");
        setSelectedElementType(null);
        setNewElementAvailableToAll(false);
        toast({
          title: "Error",
          description: "Failed to load resource for editing.",
          variant: "destructive",
        });
      } finally {
        setIsLoadingSchema(false);
      }
    },
    [availableCategories, fetchElementSchema, fetchElementActions, startLockHeartbeat, stopLockHeartbeat, toast],
  );

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

  const applyToggle = useCallback(async (rid: string, newValue: boolean) => {
    setIsTogglingStatus(rid);
    try {
      // toggleBuiltinStatus already catches its own failures (e.g. blocked
      // because a public agent still uses this resource, or a 409 because
      // another admin holds the edit lock) and surfaces an error toast
      // internally, returning null rather than rejecting.
      const result = await toggleBuiltinStatus(rid, newValue);
      if (result) {
        if (result.cascaded_resources?.length) {
          // Aggregated elements (LLMs, providers, tools, etc.) were swept
          // along to "available to all" too — refresh everything so their
          // switches/badges reflect the new state, not just this row's.
          await reloadBuiltins();
        } else {
          setAvailableToAll((prev) => ({ ...prev, [rid]: newValue }));
          const nextVisibility = newValue ? "public" : "draft";
          setCategoryResources((prev) => {
            const next: Record<string, ResourceItem[]> = {};
            for (const [cat, items] of Object.entries(prev)) {
              next[cat] = items.map((item) =>
                item.rid === rid ? { ...item, visibility: nextVisibility } : item,
              );
            }
            return next;
          });
        }
      }
    } finally {
      setIsTogglingStatus(null);
    }
  }, [toggleBuiltinStatus, reloadBuiltins]);

  const toggleAvailableToAll = useCallback(async (rid: string) => {
    const currentValue = availableToAll[rid] ?? false;
    const newValue = !currentValue;

    if (newValue) {
      // Turning "available to all" on can cascade to not-yet-public
      // dependencies (LLMs, providers, tools, etc.). Preview first so the
      // admin can confirm *before* the mutation, rather than only being
      // told about it in the success toast afterward.
      setIsTogglingStatus(rid);
      let cascaded: ResourceDependencySummary[] = [];
      try {
        cascaded = await previewBuiltinCascade(rid);
      } catch {
        // If the preview call itself fails, don't block the toggle on it —
        // proceed with the mutation and rely on its own error handling /
        // the post-mutation cascade disclaimer as a fallback.
        cascaded = [];
      } finally {
        setIsTogglingStatus(null);
      }
      if (cascaded.length > 0) {
        const resource = Object.values(categoryResources).flat().find((r) => r.rid === rid);
        setCascadePreview({ rid, resourceName: resource?.name ?? "This resource", cascaded });
        return;
      }
    }

    await applyToggle(rid, newValue);
  }, [availableToAll, applyToggle, categoryResources]);

  const confirmCascade = useCallback(async () => {
    if (!cascadePreview) return;
    setIsApplyingCascade(true);
    try {
      await applyToggle(cascadePreview.rid, true);
    } finally {
      setIsApplyingCascade(false);
      setCascadePreview(null);
    }
  }, [cascadePreview, applyToggle]);

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
          onSave={handleSaveElement}
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

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Resource"
        message={`Are you sure you want to delete "${deleteTarget?.name || "Unnamed"}"? This action is irreversible.`}
        confirmLabel="Delete"
        loading={isDeleting}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />

      <CascadeConfirmDialog
        target={cascadePreview}
        isConfirming={isApplyingCascade}
        onOpenChange={(open) => !open && setCascadePreview(null)}
        onConfirm={confirmCascade}
      />
    </div>
  );
}
