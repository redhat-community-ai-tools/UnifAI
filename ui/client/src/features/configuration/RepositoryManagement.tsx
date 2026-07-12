import { useState, useCallback, useMemo, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  ChevronRight,
  PackagePlus,
  Brain,
  Bot,
  Server,
  Wrench,
  Search,
  GitBranch,
  Lock,
  Layers,
  ArrowLeft,
  LoaderCircle,
  Trash2,
  Globe,
  FileText,
  Settings,
  Eye,
  KeyRound,
} from "lucide-react";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { ElementForm } from "@/components/agentic-ai/workspace/ElementForm";
import { ElementData } from "@/components/agentic-ai/workspace/ElementData";
import type {
  ElementType,
  ElementInstance,
} from "@/types/workspace";

const DROPDOWN_BG = "bg-[#1a1a2e] border-gray-700";

const CATEGORY_META: Record<
  string,
  { label: string; icon: React.ReactNode; description: string }
> = {
  nodes: {
    label: "Agents",
    icon: <Bot className="h-4 w-4" />,
    description: "Custom node agents, orchestrators, and AI agent types",
  },
  llms: {
    label: "LLMs",
    icon: <Brain className="h-4 w-4" />,
    description: "Large Language Model providers and configurations",
  },
  providers: {
    label: "Providers",
    icon: <Server className="h-4 w-4" />,
    description: "MCP servers, RAG clients, and external service connectors",
  },
  tools: {
    label: "Tools",
    icon: <Wrench className="h-4 w-4" />,
    description: "Web fetch, SSH exec, MCP proxy, and other tool integrations",
  },
  retrievers: {
    label: "Retrievers",
    icon: <Search className="h-4 w-4" />,
    description: "Document retrieval and search integrations",
  },
  conditions: {
    label: "Conditions",
    icon: <GitBranch className="h-4 w-4" />,
    description: "Routing conditions and branching logic",
  },
  auths: {
    label: "Auths",
    icon: <Lock className="h-4 w-4" />,
    description: "Authentication strategies and credential stores",
  },
};

function getCategoryMeta(key: string) {
  return (
    CATEGORY_META[key] ?? {
      label: key.charAt(0).toUpperCase() + key.slice(1),
      icon: <Layers className="h-4 w-4" />,
      description: "",
    }
  );
}

interface ResourceItem {
  rid: string;
  name: string;
  type: string;
  config: any;
  category?: string;
  builtin_status?: 'public' | 'private' | null;
  configurable_keys?: string[];
}

type WizardStep = "idle" | "select-category" | "configure" | "configure-builtin";

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

  const [newElementAvailableToAll, setNewElementAvailableToAll] = useState(true);
  const [configurableKeys, setConfigurableKeys] = useState<string[]>([]);
  const [showConfigurableKeys, setShowConfigurableKeys] = useState(false);
  const [isTogglingStatus, setIsTogglingStatus] = useState<string | null>(null);

  const availableCategories = useMemo(
    () => categories.filter((c) => c.elements.length > 0),
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
      const axios = (await import("@/http/axiosAgentConfig")).default;
      const response = await axios.get(`/resources/builtins.list`);
      const resources = response.data.resources || [];
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
          builtin_status: r.builtin_status || null,
          configurable_keys: r.configurable_keys || [],
        });
        newAvailable[r.rid] = r.builtin_status === "public";
      }
      setCategoryResources(grouped);
      setAvailableToAll(newAvailable);
    } catch (err) {
      console.error("Failed to load built-in resources:", err);
    }
  }, []);

  useEffect(() => {
    reloadBuiltins();
  }, [reloadBuiltins]);

  const handleAddNew = () => {
    setStep("select-category");
    setSelectedCategoryKey("");
    setSelectedElementType(null);
  };

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
      setConfigurableKeys([]);
      setShowConfigurableKeys(false);
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

      setSelectedCategoryKey(categoryKey);
      setSelectedElementType(elType);
      setIsLoadingSchema(true);
      setStep("configure");
      setNewElementAvailableToAll(resource.builtin_status === "public");
      setConfigurableKeys(resource.configurable_keys ?? []);
      setShowConfigurableKeys((resource.configurable_keys ?? []).length > 0);

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
    [availableCategories, fetchElementSchema, fetchElementActions],
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
      configurableKeys,
      editingElement?.rid,
    );
    if (result) {
      reloadBuiltins();
    }
    return result;
  };

  const handleFormClose = () => {
    setIsFormOpen(false);
    setEditingElement(null);
    setConfiguringBuiltin(null);
    setStep("idle");
    setSelectedCategoryKey("");
    setSelectedElementType(null);
    setNewElementAvailableToAll(true);
    setConfigurableKeys([]);
    setShowConfigurableKeys(false);
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

  const getTypeName = (categoryKey: string, typeKey: string): string => {
    const cat = availableCategories.find((c) => c.category === categoryKey);
    const el = cat?.elements.find((e) => e.type === typeKey);
    return el?.name ?? typeKey;
  };

  const getUniqueTypes = (categoryKey: string): string[] => {
    const resources = categoryResources[categoryKey];
    if (!resources) return [];
    const types = new Set(resources.map((r) => r.type));
    return Array.from(types);
  };

  const getFilteredResources = (categoryKey: string): ResourceItem[] => {
    const resources = categoryResources[categoryKey];
    if (!resources) return [];
    const filter = typeFilters[categoryKey];
    if (!filter || filter === "__all__") return resources;
    return resources.filter((r) => r.type === filter);
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

      {/* Add New Wizard */}
      <AnimatePresence>
        {step === "select-category" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
          >
            <Card className="bg-background-card shadow-card border-gray-800 border-primary/30">
              <CardContent className="p-6">
                <div className="flex items-center gap-2 mb-6">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleBack}
                    className="text-gray-400 hover:text-white -ml-2"
                  >
                    <ArrowLeft className="h-4 w-4 mr-1" />
                    Cancel
                  </Button>
                  <div className="h-4 w-px bg-gray-700" />
                  <h3 className="text-sm font-medium text-gray-300">
                    Add New Resource
                  </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-300">
                      Resource Category
                    </label>
                    <Select
                      value={selectedCategoryKey}
                      onValueChange={handleCategoryChange}
                    >
                      <SelectTrigger className="bg-background-dark border-gray-700">
                        <SelectValue placeholder="Choose a category..." />
                      </SelectTrigger>
                      <SelectContent className={DROPDOWN_BG}>
                        {availableCategories.map((cat) => {
                          const meta = getCategoryMeta(cat.category);
                          return (
                            <SelectItem
                              key={cat.category}
                              value={cat.category}
                            >
                              <div className="flex items-center gap-2">
                                {meta.icon}
                                <span>{meta.label}</span>
                                <span className="text-xs text-gray-500 ml-1">
                                  ({cat.elements.length})
                                </span>
                              </div>
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                    {selectedCategoryKey && (
                      <p className="text-xs text-gray-500">
                        {getCategoryMeta(selectedCategoryKey).description}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-300">
                      Resource Type
                    </label>
                    <Select
                      value={selectedElementType?.type ?? ""}
                      onValueChange={handleTypeChange}
                      disabled={!selectedCategoryKey}
                    >
                      <SelectTrigger className="bg-background-dark border-gray-700">
                        <SelectValue
                          placeholder={
                            selectedCategoryKey
                              ? "Choose a type..."
                              : "Select a category first"
                          }
                        />
                      </SelectTrigger>
                      <SelectContent className={DROPDOWN_BG}>
                        {selectedCategoryElements.map((el) => (
                          <SelectItem key={el.type} value={el.type}>
                            {el.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Available to All toggle */}
                {selectedElementType && (
                  <div className="mt-6 pt-4 border-t border-gray-800 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Globe className="h-4 w-4 text-green-400" />
                        <div>
                          <p className="text-sm font-medium text-gray-200">
                            Available to All
                          </p>
                          <p className="text-xs text-gray-500">
                            When enabled, all users will see this resource in their workspace
                          </p>
                        </div>
                      </div>
                      <Switch
                        checked={newElementAvailableToAll}
                        onCheckedChange={setNewElementAvailableToAll}
                      />
                    </div>

                    {newElementAvailableToAll && (
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <KeyRound className="h-4 w-4 text-amber-400" />
                          <div>
                            <p className="text-sm font-medium text-gray-200">
                              User-Configurable Fields
                            </p>
                            <p className="text-xs text-gray-500">
                              Choose which fields users can edit (all others will be read-only)
                            </p>
                          </div>
                        </div>
                        <Switch
                          checked={showConfigurableKeys}
                          onCheckedChange={setShowConfigurableKeys}
                        />
                      </div>
                    )}
                  </div>
                )}

                <div className="flex justify-end mt-6 pt-4 border-t border-gray-800">
                  <Button
                    onClick={handleNext}
                    disabled={!selectedElementType || isLoadingSchema}
                    className="bg-primary hover:bg-primary/80"
                  >
                    {isLoadingSchema ? (
                      <>
                        <LoaderCircle className="h-4 w-4 mr-2 animate-spin" />
                        Loading...
                      </>
                    ) : (
                      <>
                        Next
                        <ChevronRight className="h-4 w-4 ml-2" />
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {(step === "configure" || step === "configure-builtin") && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
          >
            <Card className={`bg-background-card shadow-card border-gray-800 ${step === "configure-builtin" ? "border-blue-500/30" : "border-green-500/30"}`}>
              <CardContent className="p-6">
                <div className="flex items-center justify-center py-4 gap-3">
                  <LoaderCircle className={`h-5 w-5 animate-spin ${step === "configure-builtin" ? "text-blue-400" : "text-green-400"}`} />
                  <p className="text-sm text-gray-300">
                    {step === "configure-builtin"
                      ? "Configuring your settings for"
                      : editingElement
                        ? "Editing"
                        : "Configuring"}{" "}
                    <span className="text-white font-medium">
                      {selectedElementType?.name}
                    </span>{" "}
                    — {step === "configure-builtin"
                      ? "editable fields are unlocked, read-only fields are locked."
                      : "fill in the form and save."}
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleFormClose}
                    className="text-gray-400 hover:text-white ml-2"
                  >
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Resource Browser — Accordion by category */}
      {isLoading && availableCategories.length === 0 ? (
        <div className="flex items-center justify-center py-16 text-gray-400 gap-2">
          <LoaderCircle className="h-5 w-5 animate-spin" />
          <span className="text-sm">Loading catalog...</span>
        </div>
      ) : (
        <Card className="bg-background-card shadow-card border-gray-800">
          <CardContent className="p-0">
            <Accordion
              type="multiple"
              className="w-full"
            >
              {availableCategories.map((cat) => {
                const meta = getCategoryMeta(cat.category);
                const resources = categoryResources[cat.category] ?? [];
                const count = resources.length;

                return (
                  <AccordionItem
                    key={cat.category}
                    value={cat.category}
                    className="border-gray-800"
                  >
                    <AccordionTrigger className="px-6 py-4 hover:no-underline hover:bg-white/[.02] transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="rounded-lg bg-primary/10 p-2 text-primary">
                          {meta.icon}
                        </div>
                        <div className="text-left">
                          <p className="text-sm font-medium">{meta.label}</p>
                          <p className="text-xs text-gray-500 font-normal">
                            {meta.description}
                          </p>
                        </div>
                        <Badge
                          variant="outline"
                          className="ml-2 text-xs text-gray-400 border-gray-700"
                        >
                          {count} resource{count !== 1 ? "s" : ""}
                        </Badge>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="px-6 pb-4">
                      {resources.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-8 text-gray-500 gap-2">
                          <PackagePlus className="h-6 w-6 opacity-40" />
                          <p className="text-sm">
                            No {meta.label.toLowerCase()} configured yet.
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            className="mt-1 border-gray-700 text-xs"
                            onClick={() => {
                              setStep("select-category");
                              setSelectedCategoryKey(cat.category);
                              setSelectedElementType(null);
                            }}
                          >
                            <Plus className="h-3 w-3 mr-1" />
                            Add {meta.label}
                          </Button>
                        </div>
                      ) : (
                        <div className="space-y-0">
                          {/* Table Header */}
                          <div className="grid grid-cols-12 gap-4 px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-800">
                            <div className="col-span-4">Name</div>
                            <div className="col-span-2">
                              <Select
                                value={
                                  typeFilters[cat.category] ?? "__all__"
                                }
                                onValueChange={(v) =>
                                  setTypeFilters((prev) => ({
                                    ...prev,
                                    [cat.category]: v,
                                  }))
                                }
                              >
                                <SelectTrigger className="h-auto border-0 bg-transparent p-0 shadow-none text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-300 transition-colors focus:ring-0 focus:ring-offset-0 gap-1 w-fit [&>svg]:h-3 [&>svg]:w-3">
                                  <SelectValue placeholder="Type" />
                                </SelectTrigger>
                                <SelectContent className={DROPDOWN_BG}>
                                  <SelectItem value="__all__">
                                    All Types
                                  </SelectItem>
                                  {getUniqueTypes(cat.category).map(
                                    (typeKey) => (
                                      <SelectItem
                                        key={typeKey}
                                        value={typeKey}
                                      >
                                        {getTypeName(
                                          cat.category,
                                          typeKey,
                                        )}
                                      </SelectItem>
                                    ),
                                  )}
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="col-span-3 text-center">
                              Available to All
                            </div>
                            <div className="col-span-3 text-right">
                              Actions
                            </div>
                          </div>
                          {/* Rows */}
                          {(() => {
                            const filtered = getFilteredResources(
                              cat.category,
                            );
                            if (filtered.length === 0) {
                              return (
                                <div className="flex items-center justify-center py-6 text-gray-500 text-sm">
                                  No resources match the selected type filter.
                                </div>
                              );
                            }
                            return filtered.map((resource, idx) => (
                              <motion.div
                                key={resource.rid}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: idx * 0.03 }}
                                className="grid grid-cols-12 gap-4 items-center px-4 py-3 border-b border-gray-800/50 last:border-b-0 hover:bg-white/[.02] transition-colors group"
                              >
                                {/* Name */}
                                <div className="col-span-4 flex items-center gap-2 min-w-0">
                                  <FileText className="h-4 w-4 text-gray-500 flex-shrink-0" />
                                  <span className="text-sm font-medium truncate">
                                    {resource.name || "Unnamed"}
                                  </span>
                                  {resource.builtin_status && (
                                    <Badge
                                      variant="outline"
                                      className={`text-[10px] px-1.5 py-0 flex-shrink-0 ${
                                        resource.builtin_status === "public"
                                          ? "text-blue-400 border-blue-400/30"
                                          : "text-gray-400 border-gray-500/30"
                                      }`}
                                    >
                                      {resource.builtin_status === "public" ? "Public" : "Private"}
                                    </Badge>
                                  )}
                                </div>
                                {/* Type */}
                                <div className="col-span-2">
                                  <Badge
                                    variant="outline"
                                    className="text-xs border-gray-700 text-gray-400 font-normal"
                                  >
                                    {getTypeName(
                                      cat.category,
                                      resource.type,
                                    )}
                                  </Badge>
                                </div>
                                {/* Available to All toggle */}
                                <div className="col-span-3 flex justify-center">
                                  <SimpleTooltip
                                    content={
                                      <p>
                                        {availableToAll[resource.rid]
                                          ? "This resource is visible to all users"
                                          : "Toggle to make this resource available to all users"}
                                      </p>
                                    }
                                  >
                                    <div className="flex items-center gap-2">
                                      {isTogglingStatus === resource.rid ? (
                                        <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
                                      ) : (
                                        <Switch
                                          checked={
                                            availableToAll[resource.rid] ??
                                            false
                                          }
                                          onCheckedChange={() =>
                                            toggleAvailableToAll(resource.rid)
                                          }
                                        />
                                      )}
                                      {availableToAll[resource.rid] && (
                                        <Globe className="h-3.5 w-3.5 text-green-400" />
                                      )}
                                    </div>
                                  </SimpleTooltip>
                                </div>
                                {/* Actions */}
                                <div className="col-span-3 flex justify-end gap-1">
                                  <SimpleTooltip
                                    content={<p>View details</p>}
                                  >
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-8 w-8 p-0 text-gray-500 hover:text-blue-400 hover:bg-blue-500/10"
                                      onClick={() =>
                                        handleViewDetails(resource)
                                      }
                                    >
                                      <Eye className="h-4 w-4" />
                                    </Button>
                                  </SimpleTooltip>
                                  <SimpleTooltip
                                    content={<p>Edit configuration</p>}
                                  >
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-8 w-8 p-0 text-gray-500 hover:text-white hover:bg-white/10"
                                      onClick={() =>
                                        handleEditResource(resource)
                                      }
                                    >
                                      <Settings className="h-4 w-4" />
                                    </Button>
                                  </SimpleTooltip>
                                  <SimpleTooltip
                                    content={<p>Delete this resource</p>}
                                  >
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-8 w-8 p-0 text-gray-500 hover:text-red-400 hover:bg-red-500/10"
                                      onClick={() =>
                                        handleDeleteClick(resource)
                                      }
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </SimpleTooltip>
                                </div>
                              </motion.div>
                            ));
                          })()}
                          {/* Add more link */}
                          <div className="px-4 py-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-xs text-primary/70 hover:text-primary -ml-2"
                              onClick={() => {
                                setStep("select-category");
                                setSelectedCategoryKey(cat.category);
                                setSelectedElementType(null);
                              }}
                            >
                              <Plus className="h-3 w-3 mr-1" />
                              Add {meta.label}
                            </Button>
                          </div>
                        </div>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          </CardContent>
        </Card>
      )}

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
        />
      )}

      {/* Configurable Keys Selector — shows when form is open and admin enabled configurable keys */}
      {isFormOpen && showConfigurableKeys && newElementAvailableToAll && elementSchema && !configuringBuiltin && (
        <ConfigurableKeysSelector
          schema={elementSchema}
          selectedKeys={configurableKeys}
          onSelectionChange={setConfigurableKeys}
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

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Resource</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;
              {deleteTarget?.name || "Unnamed"}&quot;?
              <br />
              <br />
              <strong>This action is irreversible.</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-background-dark border-gray-700 hover:bg-background-surface">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  ConfigurableKeysSelector — lets admin pick which fields users can edit
// ─────────────────────────────────────────────────────────────────────────────

function ConfigurableKeysSelector({
  schema,
  selectedKeys,
  onSelectionChange,
}: {
  schema: any;
  selectedKeys: string[];
  onSelectionChange: (keys: string[]) => void;
}) {
  const fields = useMemo(() => {
    const props = schema?.config_schema?.properties;
    if (!props) return [];
    return Object.entries(props)
      .filter(([key, fieldSchema]: [string, any]) => {
        if (fieldSchema?.hints?.hidden?.hint_type === "hidden") return false;
        const systemFields = [
          "name", "category", "type", "cfg_dict", "version",
          "created", "updated", "nested_refs", "rid", "user_id",
        ];
        return !systemFields.includes(key);
      })
      .map(([key, fieldSchema]: [string, any]) => ({
        key,
        title: fieldSchema.title || key,
        description: fieldSchema.description || "",
      }));
  }, [schema]);

  const toggleKey = (key: string) => {
    if (selectedKeys.includes(key)) {
      onSelectionChange(selectedKeys.filter((k) => k !== key));
    } else {
      onSelectionChange([...selectedKeys, key]);
    }
  };

  if (fields.length === 0) return null;

  return (
    <Card className="bg-background-card shadow-card border-amber-500/20 mt-4">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <KeyRound className="h-4 w-4 text-amber-400" />
          <h4 className="text-sm font-medium text-gray-200">
            User-Configurable Fields
          </h4>
          <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-400/30">
            {selectedKeys.length} selected
          </Badge>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          Selected fields will be editable by users. All other fields will be read-only.
        </p>
        <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
          {fields.map(({ key, title }) => (
            <div
              key={key}
              className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/[.03] transition-colors"
            >
              <Checkbox
                id={`ck-${key}`}
                checked={selectedKeys.includes(key)}
                onCheckedChange={() => toggleKey(key)}
                className="border-gray-600"
              />
              <Label
                htmlFor={`ck-${key}`}
                className="text-xs text-gray-300 cursor-pointer truncate"
              >
                {title}
              </Label>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
