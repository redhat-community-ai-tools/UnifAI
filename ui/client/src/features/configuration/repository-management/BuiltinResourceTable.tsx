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
import { motion } from "framer-motion";
import {
  Plus,
  PackagePlus,
  Eye,
  Settings,
  Trash2,
  Globe,
  FileText,
  LoaderCircle,
} from "lucide-react";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { ValidationStatusBadge } from "@/components/agentic-ai/workspace/validation/ValidationStatusBadge";
import type { ValidationStatus } from "@/contexts/AgenticAIContext";
import type { ElementType } from "@/types/workspace";
import { DROPDOWN_BG, getCategoryMeta, type ResourceItem } from "./types";

interface CategoryOption {
  category: string;
  elements: ElementType[];
}

interface BuiltinResourceTableProps {
  isLoading: boolean;
  availableCategories: CategoryOption[];
  categoryResources: Record<string, ResourceItem[]>;
  typeFilters: Record<string, string>;
  availableToAll: Record<string, boolean>;
  isTogglingStatus: string | null;
  getValidationStatus: (rid: string) => ValidationStatus;
  onTypeFilterChange: (category: string, value: string) => void;
  onToggleAvailableToAll: (rid: string) => void;
  onViewDetails: (resource: ResourceItem) => void;
  onEditResource: (resource: ResourceItem) => void;
  onDeleteClick: (resource: ResourceItem) => void;
  onAddToCategory: (category: string) => void;
  onValidationClick: (rid: string) => void;
}

/**
 * Accordion-by-category resource browser: per-category table of built-in
 * resources with type filtering, the "available to all" toggle, and
 * row actions (view / edit / delete). Split out of
 * ``RepositoryManagement.tsx`` to isolate the (large) list-rendering surface
 * from wizard/state-management concerns.
 */
export function BuiltinResourceTable({
  isLoading,
  availableCategories,
  categoryResources,
  typeFilters,
  availableToAll,
  isTogglingStatus,
  getValidationStatus,
  onTypeFilterChange,
  onToggleAvailableToAll,
  onViewDetails,
  onEditResource,
  onDeleteClick,
  onAddToCategory,
  onValidationClick,
}: BuiltinResourceTableProps) {
  const getTypeName = (categoryKey: string, typeKey: string): string => {
    const cat = availableCategories.find((c) => c.category === categoryKey);
    const el = cat?.elements.find((e) => e.type === typeKey);
    return el?.name ?? typeKey;
  };

  const getUniqueTypes = (categoryKey: string): string[] => {
    const resources = categoryResources[categoryKey];
    if (!resources) return [];
    return Array.from(new Set(resources.map((r) => r.type)));
  };

  const getFilteredResources = (categoryKey: string): ResourceItem[] => {
    const resources = categoryResources[categoryKey];
    if (!resources) return [];
    const filter = typeFilters[categoryKey];
    if (!filter || filter === "__all__") return resources;
    return resources.filter((r) => r.type === filter);
  };

  if (isLoading && availableCategories.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-400 gap-2">
        <LoaderCircle className="h-5 w-5 animate-spin" />
        <span className="text-sm">Loading catalog...</span>
      </div>
    );
  }

  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardContent className="p-0">
        <Accordion type="multiple" className="w-full">
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
                        onClick={() => onAddToCategory(cat.category)}
                      >
                        <Plus className="h-3 w-3 mr-1" />
                        Add {meta.label}
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-0">
                      <div className="grid grid-cols-12 gap-4 px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-800">
                        <div className="col-span-4">Name</div>
                        <div className="col-span-2">
                          <Select
                            value={typeFilters[cat.category] ?? "__all__"}
                            onValueChange={(v) => onTypeFilterChange(cat.category, v)}
                          >
                            <SelectTrigger className="h-auto border-0 bg-transparent p-0 shadow-none text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-300 transition-colors focus:ring-0 focus:ring-offset-0 gap-1 w-fit [&>svg]:h-3 [&>svg]:w-3">
                              <SelectValue placeholder="Type" />
                            </SelectTrigger>
                            <SelectContent className={DROPDOWN_BG}>
                              <SelectItem value="__all__">All Types</SelectItem>
                              {getUniqueTypes(cat.category).map((typeKey) => (
                                <SelectItem key={typeKey} value={typeKey}>
                                  {getTypeName(cat.category, typeKey)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="col-span-1 text-center">Status</div>
                        <div className="col-span-2 text-center">Available to All</div>
                        <div className="col-span-3 text-right">Actions</div>
                      </div>
                      {(() => {
                        const filtered = getFilteredResources(cat.category);
                        if (filtered.length === 0) {
                          return (
                            <div className="flex items-center justify-center py-6 text-gray-500 text-sm">
                              No resources match the selected type filter.
                            </div>
                          );
                        }
                        return filtered.map((resource, idx) => {
                          return (
                            <motion.div
                              key={resource.rid}
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              transition={{ delay: idx * 0.03 }}
                              className="grid grid-cols-12 gap-4 items-center px-4 py-3 border-b border-gray-800/50 last:border-b-0 hover:bg-white/[.02] transition-colors group"
                            >
                              <div className="col-span-4 flex items-center gap-2 min-w-0">
                                <FileText className="h-4 w-4 text-gray-500 flex-shrink-0" />
                                <span className="text-sm font-medium truncate">
                                  {resource.name || "Unnamed"}
                                </span>
                                {resource.ownership === "builtin" && (
                                  <Badge
                                    variant="outline"
                                    className={`text-[10px] px-1.5 py-0 flex-shrink-0 ${
                                      resource.visibility === "public"
                                        ? "text-blue-400 border-blue-400/30"
                                        : "text-gray-400 border-gray-500/30"
                                    }`}
                                  >
                                    {resource.visibility === "public" ? "Public" : "Draft"}
                                  </Badge>
                                )}
                              </div>
                              <div className="col-span-2">
                                <Badge
                                  variant="outline"
                                  className="text-xs border-gray-700 text-gray-400 font-normal"
                                >
                                  {getTypeName(cat.category, resource.type)}
                                </Badge>
                              </div>
                              <div className="col-span-1 flex justify-center">
                                <ValidationStatusBadge
                                  status={getValidationStatus(resource.rid)}
                                  onClick={() => onValidationClick(resource.rid)}
                                />
                              </div>
                              <div className="col-span-2 flex justify-center">
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
                                        checked={availableToAll[resource.rid] ?? false}
                                        onCheckedChange={() => onToggleAvailableToAll(resource.rid)}
                                      />
                                    )}
                                    {availableToAll[resource.rid] && (
                                      <Globe className="h-3.5 w-3.5 text-green-400" />
                                    )}
                                  </div>
                                </SimpleTooltip>
                              </div>
                              <div className="col-span-3 flex justify-end gap-1">
                                <SimpleTooltip content={<p>View details</p>}>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 w-8 p-0 text-gray-500 hover:text-blue-400 hover:bg-blue-500/10"
                                    onClick={() => onViewDetails(resource)}
                                  >
                                    <Eye className="h-4 w-4" />
                                  </Button>
                                </SimpleTooltip>
                                <SimpleTooltip content={<p>Edit configuration</p>}>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 w-8 p-0 text-gray-500 hover:text-white hover:bg-white/10"
                                    onClick={() => onEditResource(resource)}
                                    aria-label="Edit configuration"
                                  >
                                    <Settings className="h-4 w-4" />
                                  </Button>
                                </SimpleTooltip>
                                <SimpleTooltip content={<p>Delete this resource</p>}>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 w-8 p-0 text-gray-500 hover:text-red-400 hover:bg-red-500/10"
                                    onClick={() => onDeleteClick(resource)}
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </SimpleTooltip>
                              </div>
                            </motion.div>
                          );
                        });
                      })()}
                      <div className="px-4 py-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs text-primary/70 hover:text-primary -ml-2"
                          onClick={() => onAddToCategory(cat.category)}
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
  );
}
