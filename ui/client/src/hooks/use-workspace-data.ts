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
import { useAgenticAI } from "@/contexts/AgenticAIContext";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";

// Types for Resources API responses
interface ResourceInstance {
  rid: string;
  user_id: string;
  category: string;
  type: string;
  name: string;
  version: number;
  cfg_dict: any;
  nested_refs: string[];
  contributed_by?: string;
  created: string;
  updated: string;
  builtin_status?: 'public' | 'private' | null;
  configurable_keys?: string[];
}

interface ResourcesListResponse {
  resources: ResourceInstance[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
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
  const { userId: USER_ID, displayName: USER_DISPLAY_NAME, identityType } = useWorkspaceIdentity();

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

        const response = await axios.get<ResourcesListResponse>(
          `/resources/resources.list?userId=${USER_ID}&identityType=${identityType}&category=${category}&type=${type}`,
        );

        // Transform ResourceInstance to ElementInstance format
        const instances: ElementInstance[] = response.data.resources.map(
          (resource: ResourceInstance) => ({
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
            builtinStatus: resource.builtin_status || null,
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
    [toast, USER_ID, identityType],
  );

  // Fetch single resource by ID
  const fetchResourceById = useCallback(
    async (resourceId: string) => {
      try {
        setIsLoading(true);
        setError(null);

        const response = await axios.get<ResourceInstance>(
          `/resources/resource.get?resourceId=${resourceId}`,
        );

        return response.data;
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
    async (category: string) => {
      try {
        const response = await axios.get<ResourcesListResponse>(
          `/resources/resources.list?userId=${USER_ID}&identityType=${identityType}&category=${category}`,
        );

        return response.data.resources.map((resource: ResourceInstance) => ({
          rid: resource.rid,
          name: resource.name,
          type: resource.type,
          config: resource.cfg_dict,
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
    [toast, USER_ID, identityType],
  );

  // Fetch element schema for form generation (combines resource schema + element-specific schema)
  const fetchElementSchema = useCallback(
    async (category: string, type: string) => {
      try {
        setIsLoading(true);
        setError(null);

        // First fetch the resource schema (first-level schema)
        const resourceSchemaResponse = await axios.get(
          "/resources/resource.schema",
        );
        const resourceSchema = resourceSchemaResponse.data;

        // Then fetch the element-specific schema (cfg_dict schema)
        const elementSchemaResponse = await axios.get<ElementSchema>(
          `/catalog/element.spec.get?category=${category}&type=${type}`,
        );
        const elementSchema = elementSchemaResponse.data;

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
          // Update existing resource
          const response = await axios.put("/resources/resource.update", {
            resourceId: rid,
            config: elementData.cfg_dict,
            name: elementData.name,
          });
          
          // Update the resource mapping immediately
          if (response.data) {
            addOrUpdateResource({
              rid: response.data.rid || rid,
              name: response.data.name || elementData.name,
              category: response.data.category || category,
              type: response.data.type || type,
            });
            // Revalidate resource after update
            revalidateResourceAndAncestors(response.data.rid || rid);
          }
          
          toast({
            title: "Success",
            description: "Element updated successfully",
          });
          return response.data;
        } else {
          // Create new resource
          const { cfg_dict, ...firstLevelFields } = elementData;
          const savePayload = {
            userId: USER_ID,
            identityType: identityType,
            displayName: USER_DISPLAY_NAME,
            category,
            type,
            config: cfg_dict,
            ...firstLevelFields,
          };

          const response = await axios.post(
            "/resources/resource.save",
            savePayload,
          );
          
          // Update the resource mapping immediately
          if (response.data) {
            addOrUpdateResource({
              rid: response.data.rid,
              name: response.data.name || elementData.name,
              category: response.data.category || category,
              type: response.data.type || type,
            });
            // Validate new resource immediately after creation
            revalidateResourceAndAncestors(response.data.rid);
          }
          
          toast({
            title: "Success",
            description: "Element created successfully",
          });
          return response.data;
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
    [toast, USER_ID, identityType],
  );

  // Delete element using Resources API
  const deleteElement = useCallback(
    async (rid: string) => {
      try {
        setIsLoading(true);
        setError(null);

        await axios.delete(`/resources/resource.delete?resourceId=${rid}`);
        
        removeResource(rid);
        
        toast({
          title: "Success",
          description: "Element deleted successfully",
        });
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
  // but each field has a readOnly hint based on the resource's configurable_keys)
  const fetchBuiltinSchema = useCallback(
    async (resourceId: string) => {
      try {
        setIsLoading(true);
        setError(null);

        const response = await axios.get(
          `/resources/builtin.schema?resourceId=${resourceId}`,
        );

        const builtinSchema = response.data;
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

  // Save per-user configuration for a built-in resource (only non-readOnly fields)
  const configureBuiltin = useCallback(
    async (resourceId: string, config: Record<string, any>) => {
      try {
        setIsLoading(true);
        setError(null);

        const response = await axios.patch("/resources/builtin.configure", {
          resourceId,
          userId: USER_ID,
          identityType: identityType,
          config,
        });

        toast({
          title: "Success",
          description: "Built-in resource configured successfully",
        });
        return response.data;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to configure built-in resource";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error configuring built-in:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast, USER_ID, identityType],
  );

  // Create a built-in resource directly (admin only)
  const saveBuiltinElement = useCallback(
    async (
      category: string,
      type: string,
      elementData: any,
      availableToAll: boolean = true,
      configurableKeys: string[] = [],
      rid?: string,
    ) => {
      try {
        setIsLoading(true);
        setError(null);

        if (rid) {
          const response = await axios.put("/resources/builtin.update", {
            resourceId: rid,
            config: elementData.cfg_dict,
            name: elementData.name,
            availableToAll,
            configurableKeys,
          });
          toast({
            title: "Success",
            description: "Built-in resource updated successfully",
          });
          return response.data;
        } else {
          const { cfg_dict, name } = elementData;
          const response = await axios.post("/resources/builtin.create", {
            category,
            type,
            name,
            config: cfg_dict,
            availableToAll,
            configurableKeys,
          });
          toast({
            title: "Success",
            description: "Built-in resource created successfully",
          });
          return response.data;
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
    [toast],
  );

  // Toggle available_to_all status for a resource (admin only)
  const toggleBuiltinStatus = useCallback(
    async (resourceId: string, availableToAll: boolean) => {
      try {
        setIsLoading(true);
        setError(null);

        const response = await axios.patch("/resources/builtin.toggle", {
          resourceId,
          availableToAll,
        });

        toast({
          title: "Success",
          description: availableToAll
            ? "Resource is now available to all users"
            : "Resource is no longer available to all users",
        });
        return response.data;
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

        await axios.delete(`/resources/resource.delete?resourceId=${rid}`);

        toast({
          title: "Success",
          description: "Built-in resource deleted successfully",
        });
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
    configureBuiltin,
    saveElement,
    deleteElement,
    saveBuiltinElement,
    toggleBuiltinStatus,
    deleteBuiltinElement,
    refetchCategories: fetchCategories,
  };
};