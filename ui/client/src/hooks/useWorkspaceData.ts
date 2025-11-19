import { useState, useEffect, useCallback } from "react";
import axios from "../http/axiosAgentConfig";
import {
  ElementCategory,
  ElementType,
  ElementInstance,
  ElementSchema,
  CatalogResponse,
} from "../types/workspace";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "./use-toast";

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
  created: string;
  updated: string;
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
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const { user } = useAuth();
  const USER_ID = user?.username || "default";

  // Fetch all available categories and element types
  const fetchCategories = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await axios.get<CatalogResponse>(
        "/catalog/elements.list.get",
      );

      const categoryList: ElementCategory[] = Object.entries(
        response.data.elements,
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
        setIsLoading(true);
        setError(null);
        setElementInstances([]);

        const response = await axios.get<ResourcesListResponse>(
          `/resources/resources.list?userId=${USER_ID}&category=${category}&type=${type}`,
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
        setIsLoading(false);
      }
    },
    [toast],
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
          `/resources/resources.list?userId=${USER_ID}&category=${category}`,
        );

        return response.data.resources.map((resource: ResourceInstance) => ({
          rid: resource.rid,
          name: resource.name,
          type: resource.type,
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
    [toast],
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
            category,
            type,
            config: cfg_dict,
            ...firstLevelFields,
          };

          const response = await axios.post(
            "/resources/resource.save",
            savePayload,
          );
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
    [toast],
  );

  // Delete element using Resources API
  const deleteElement = useCallback(
    async (rid: string) => {
      try {
        setIsLoading(true);
        setError(null);

        await axios.delete(`/resources/resource.delete?resourceId=${rid}`);
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
    error,
    fetchCategories,
    fetchElementInstances,
    fetchElementSchema,
    fetchElementActions,
    fetchResourcesForCategory,
    fetchResourceById,
    saveElement,
    deleteElement,
    refetchCategories: fetchCategories,
  };
};