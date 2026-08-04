import { useState, useEffect, useCallback } from "react";
import axios from "../http/axiosAgentConfig";
import {
  ElementCategory,
  ElementType,
  ElementInstance,
  ElementSchema,
  CatalogResponse,
} from "../types/workspace";
import { useToast } from "./use-toast";
import { catalogService } from "@/api/catalog";
import * as resourcesApi from "@/api/resources";
import { useAgenticAI } from "@/contexts/AgenticAIContext";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";
import type { ResourceInstance } from "@/api/resources";

/**
 * When a resource is made available to all, any aggregated elements it
 * references (LLMs, providers, tools, etc.) that weren't already public
 * built-ins get swept along automatically. Builds the disclaimer text for
 * the success toast when that happened.
 */
function describeCascadedResources(result: ResourceInstance | null): string | null {
  const cascaded = result?.cascaded_resources;
  if (!cascaded || cascaded.length === 0) return null;
  const names = cascaded.map((r) => `"${r.name}"`).join(", ");
  return `Also made available to all, since this resource uses ${names}.`;
}

export const useWorkspaceData = () => {
  const [categories, setCategories] = useState<ElementCategory[]>([]);
  const [elementInstances, setElementInstances] = useState<ElementInstance[]>(
    [],
  );
  const [elementSchema, setElementSchema] = useState<ElementSchema | null>(
    null,
  );
  const [elementActions, setElementActions] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingInstances, setIsLoadingInstances] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const { addOrUpdateResource, removeResource, revalidateResourceAndAncestors } = useAgenticAI();
  const { userId: USER_ID, teamId } = useWorkspaceIdentity();

  // Fetch all available categories and element types
  const fetchCategories = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const catalogData = await catalogService.fetchAllElements();

      const categoryList: ElementCategory[] = Object.entries(
        catalogData.elements,
      ).map(([category, elements]) => ({
        category,
        // Filter out elements with hints array containing hint_type === "hidden"
        elements: (elements || []).filter((element: ElementType) => 
          !element.hints?.some(hint => hint.hint_type === "hidden")
        ),
      }))
      // Filter out categories that have no visible elements after filtering
      .filter(category => category.elements.length > 0);

      setCategories(categoryList);
      return categoryList;
    } catch (err: any) {
      const errorMessage =
        err.response?.data?.error || "Failed to fetch categories";
      setError(errorMessage);
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
      console.error("Error fetching categories:", err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  // Fetch element instances for a specific category and type using Resources API
  const fetchElementInstances = useCallback(
    async (category: string, type: string) => {
      try {
        setIsLoadingInstances(true);
        setError(null);
        setElementInstances([]);

        const resources = await resourcesApi.listAllResources({
          teamId,
          category,
          type,
        });

        const instances: ElementInstance[] = resources.map(
          (resource) => ({
            rid: resource.rid,
            name: resource.name,
            config: resource.cfg_dict,
            category: resource.category,
            type: resource.type,
            version: resource.version,
            created: resource.created,
            updated: resource.updated,
            nested_refs: resource.nested_refs,
            contributed_by: resource.contributed_by,
            ownership: resource.ownership || 'custom',
            visibility: resource.visibility,
            userConfigured: resource.user_configured ?? false,
          }),
        );

        setElementInstances(instances);
        return instances;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to fetch element instances";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching element instances:", err);
        setElementInstances([]);
        return null;
      } finally {
        setIsLoadingInstances(false);
      }
    },
    [toast, teamId],
  );

  // Fetch single resource by ID
  const fetchResourceById = useCallback(
    async (resourceId: string) => {
      try {
        setIsLoading(true);
        setError(null);

        return await resourcesApi.getResource(resourceId);
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to fetch resource";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching resource:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  // Fetch all resources for a category (for $ref dropdowns)
  const fetchResourcesForCategory = useCallback(
    async (category: string, ownership?: string) => {
      try {
        const resources = await resourcesApi.listAllResources({
          teamId,
          category,
          ownership,
        });

        return resources.map((resource) => ({
          rid: resource.rid,
          name: resource.name,
          type: resource.type,
          config: resource.cfg_dict,
          ownership: resource.ownership || 'custom',
          visibility: resource.visibility,
        }));
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error ||
          `Failed to fetch resources for category ${category}`;
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching resources for category:", err);
        return [];
      }
    },
    [toast, teamId],
  );

  // Fetch element schema for form generation (combines resource schema + element-specific schema)
  const fetchElementSchema = useCallback(
    async (category: string, type: string) => {
      try {
        setIsLoading(true);
        setError(null);

        // First fetch the resource schema (first-level schema)
        const resourceSchema = await resourcesApi.getResourceSchema();

        // Then fetch the element-specific schema (cfg_dict schema)
        const elementSchema = await resourcesApi.getElementSpec(category, type);

        // Combine both schemas into a unified schema
        const combinedSchema: ElementSchema = {
          ...elementSchema,
          config_schema: {
            ...elementSchema.config_schema,
            properties: {
              // Add resource schema properties (excluding category, type, cfg_dict)
              ...Object.fromEntries(
                Object.entries(resourceSchema.properties || {}).filter(
                  ([key]) => !["category", "type", "cfg_dict"].includes(key),
                ),
              ),
              // Add element-specific config properties
              ...elementSchema.config_schema.properties,
            },
            required: [
              // Add resource schema required fields (excluding category, type, cfg_dict)
              ...(resourceSchema.required || []).filter(
                (field: string) =>
                  !["category", "type", "cfg_dict"].includes(field),
              ),
              // Add element-specific required fields
              ...(elementSchema.config_schema.required || []),
            ],
          },
        };

        setElementSchema(combinedSchema);
        return combinedSchema;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to fetch element schema";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching element schema:", err);
        setElementSchema(null);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  // Fetch available actions for a given element category and type
  const fetchElementActions = useCallback(
    async (category: string, type: string) => {
      try {
        setIsLoading(true);
        setError(null);

        const response = await axios.get<any>(
          `/actions/actions.list?category=${category}&type=${type}`,
        );

        setElementActions(response.data.actions || []);
        return response.data.actions || [];
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to fetch element actions";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching element actions:", err);
        setElementActions([]);
        return [];
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  // Save element (create or update) using Resources API
  const saveElement = useCallback(
    async (category: string, type: string, elementData: any, rid?: string) => {
      try {
        setIsLoading(true);
        setError(null);

        if (rid) {
          const result = await resourcesApi.updateResource({
            resourceId: rid,
            config: elementData.cfg_dict,
            name: elementData.name,
          });

          if (result) {
            addOrUpdateResource({
              rid: result.rid || rid,
              name: result.name || elementData.name,
              category: result.category || category,
              type: result.type || type,
            });
            revalidateResourceAndAncestors(result.rid || rid);
          }

          toast({ title: "Success", description: "Element updated successfully" });
          return result;
        } else {
          const { cfg_dict, ...firstLevelFields } = elementData;
          const result = await resourcesApi.createResource({
            teamId,
            category,
            type,
            config: cfg_dict,
            ...firstLevelFields,
          });

          if (result) {
            addOrUpdateResource({
              rid: result.rid,
              name: result.name || elementData.name,
              category: result.category || category,
              type: result.type || type,
            });
            revalidateResourceAndAncestors(result.rid);
          }

          toast({ title: "Success", description: "Element created successfully" });
          return result;
        }
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to save element";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error saving element:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast, teamId],
  );

  // Delete element using Resources API
  const deleteElement = useCallback(
    async (rid: string) => {
      try {
        setIsLoading(true);
        setError(null);

        await resourcesApi.deleteResource(rid);

        removeResource(rid);

        toast({ title: "Success", description: "Element deleted successfully" });
        return true;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to delete element";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error deleting element:", err);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  // Fetch the annotated schema for a built-in resource (same schema as inventory,
  // but each field has a readOnly hint based on the resource's BuiltinSchema)
  const fetchBuiltinSchema = useCallback(
    async (resourceId: string) => {
      try {
        setIsLoading(true);
        setError(null);

        const builtinSchema = await resourcesApi.getBuiltinSchema(resourceId);
        setElementSchema({
          category: "",
          name: "",
          type: "",
          description: "",
          tags: [],
          config_schema: builtinSchema,
        });
        return builtinSchema;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to fetch built-in schema";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching built-in schema:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  const fetchBuiltinUserConfig = useCallback(
    async (resourceId: string): Promise<Record<string, any> | null> => {
      try {
        return await resourcesApi.getBuiltinUserConfig({
          resourceId,
          teamId,
        });
      } catch (err: any) {
        console.error("Error fetching built-in user config:", err);
        return null;
      }
    },
    [teamId],
  );

  // Save per-user configuration for a built-in resource (only non-readOnly fields)
  const configureBuiltin = useCallback(
    async (
      resourceId: string,
      config: Record<string, any>,
      options?: { silent?: boolean },
    ) => {
      const silent = options?.silent ?? false;
      try {
        // Silent background writes (e.g. persisting a discovered auth
        // identifier) must not toggle the shared loading state — that would
        // spuriously show a loading spinner elsewhere in the workspace for
        // a save the user didn't initiate.
        if (!silent) setIsLoading(true);
        setError(null);

        const result = await resourcesApi.configureBuiltin({
          resourceId,
          teamId,
          config,
        });

        // The resource's validation status may have flipped (e.g. a
        // previously-missing token is now set) — the cached badge on the
        // card would otherwise keep showing the pre-save status forever.
        revalidateResourceAndAncestors(resourceId);

        // `silent` is used for background writes (e.g. persisting the
        // discovered auth identifier right after a sign-in flow completes)
        // that aren't a user-initiated "Configure" save and shouldn't pop a
        // toast every time.
        if (!silent) {
          toast({
            title: "Success",
            description: "Built-in resource configured successfully",
          });
        }
        return result;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to configure built-in resource";
        setError(errorMessage);
        if (!silent) {
          toast({
            title: "Error",
            description: errorMessage,
            variant: "destructive",
          });
        }
        console.error("Error configuring built-in:", err);
        // Rethrow (rather than returning null) so callers - notably
        // BuiltinConfigureModal's handleSave - know the save failed and
        // don't dismiss the modal as if it had succeeded.
        throw err;
      } finally {
        if (!silent) setIsLoading(false);
      }
    },
    [toast, teamId, revalidateResourceAndAncestors],
  );

  // Create a built-in resource directly (admin only).
  // Configurable keys are derived from the schema's ReadOnlyHint annotations
  // on the backend — no need to pass them from the frontend.
  const saveBuiltinElement = useCallback(
    async (
      category: string,
      type: string,
      elementData: any,
      availableToAll: boolean = false,
      rid?: string,
    ) => {
      try {
        setIsLoading(true);
        setError(null);

        if (rid) {
          const result = await resourcesApi.updateBuiltin({
            resourceId: rid,
            config: elementData.cfg_dict,
            name: elementData.name,
            availableToAll,
          });
          const cascadeNote = describeCascadedResources(result);
          toast({
            title: "Success",
            description: cascadeNote
              ? `Built-in resource updated successfully. ${cascadeNote}`
              : "Built-in resource updated successfully",
          });
          return result;
        } else {
          const { cfg_dict, name } = elementData;
          const result = await resourcesApi.createBuiltin({
            teamId,
            category,
            type,
            name,
            config: cfg_dict,
            availableToAll,
          });
          const cascadeNote = describeCascadedResources(result);
          toast({
            title: "Success",
            description: cascadeNote
              ? `Built-in resource created successfully. ${cascadeNote}`
              : "Built-in resource created successfully",
          });
          return result;
        }
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to save built-in resource";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error saving built-in element:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast, teamId],
  );

  // Toggle available_to_all status for a resource (admin only)
  const toggleBuiltinStatus = useCallback(
    async (resourceId: string, availableToAll: boolean) => {
      try {
        setIsLoading(true);
        setError(null);

        const result = await resourcesApi.toggleBuiltinVisibility({
          resourceId,
          availableToAll,
        });

        const cascadeNote = describeCascadedResources(result);
        toast({
          title: "Success",
          description: availableToAll
            ? cascadeNote
              ? `Resource is now available to all users. ${cascadeNote}`
              : "Resource is now available to all users"
            : "Resource is no longer available to all users",
        });
        return result;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to toggle resource status";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error toggling built-in status:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  // Delete a built-in/admin resource (admin only)
  const deleteBuiltinElement = useCallback(
    async (rid: string) => {
      try {
        setIsLoading(true);
        setError(null);

        await resourcesApi.deleteResource(rid);

        toast({ title: "Success", description: "Built-in resource deleted successfully" });
        return true;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to delete built-in resource";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error deleting built-in element:", err);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  // Initialize categories on mount
  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  return {
    categories,
    elementInstances,
    elementSchema,
    elementActions,
    isLoading,
    isLoadingInstances,
    error,
    fetchCategories,
    fetchElementInstances,
    fetchElementSchema,
    fetchElementActions,
    fetchResourcesForCategory,
    fetchResourceById,
    fetchBuiltinSchema,
    fetchBuiltinUserConfig,
    configureBuiltin,
    saveElement,
    deleteElement,
    saveBuiltinElement,
    toggleBuiltinStatus,
    deleteBuiltinElement,
    refetchCategories: fetchCategories,
  };
};