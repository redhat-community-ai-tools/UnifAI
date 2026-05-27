import { useState, useEffect, useCallback } from "react";
import {
  ElementCategory,
  ElementType,
  ElementInstance,
  ElementSchema,
  CatalogResponse,
} from "../types/workspace";
import { useToast } from "./use-toast";
import { catalogService, getElementSpec } from "@/api/catalog";
import { listActions } from "@/api/actions";
import {
  listResources,
  getResource,
  getResourceSchema,
  saveResource,
  updateResource,
  deleteResource,
  type ResourceInstance,
  type ResourcesListResponse,
} from "@/api/resources";
import { useAgenticAI } from "@/contexts/AgenticAIContext";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";

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
  const { teamId: TEAM_ID } = useWorkspaceIdentity();

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

        const response = await listResources({ category, type, teamId: TEAM_ID });

        // Transform ResourceInstance to ElementInstance format
        const instances: ElementInstance[] = response.resources.map(
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
    [toast, TEAM_ID],
  );

  // Fetch single resource by ID
  const fetchResourceById = useCallback(
    async (resourceId: string) => {
      try {
        setIsLoading(true);
        setError(null);

        return await getResource(resourceId);
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
        const response = await listResources({ category, teamId: TEAM_ID });

        return response.resources.map((resource: ResourceInstance) => ({
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
    [toast, TEAM_ID],
  );

  // Fetch element schema for form generation (combines resource schema + element-specific schema)
  const fetchElementSchema = useCallback(
    async (category: string, type: string) => {
      try {
        setIsLoading(true);
        setError(null);

        const resourceSchema = await getResourceSchema();

        const elementSchema = await getElementSpec<ElementSchema>(category, type);

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

        const actions = await listActions(category, type);

        setElementActions(actions);
        return actions;
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
          const response = await updateResource({
            resourceId: rid,
            config: elementData.cfg_dict,
            name: elementData.name,
          });
          
          // Update the resource mapping immediately
          if (response) {
            addOrUpdateResource({
              rid: response.rid || rid,
              name: response.name || elementData.name,
              category: response.category || category,
              type: response.type || type,
            });
            // Revalidate resource after update
           revalidateResourceAndAncestors(response.rid || rid);
          }
          
          toast({
            title: "Success",
            description: "Element updated successfully",
          });
          return response;
        } else {
          // Create new resource
          const { cfg_dict, ...firstLevelFields } = elementData;
          const response = await saveResource({
            category,
            type,
            config: cfg_dict,
            teamId: TEAM_ID,
            ...firstLevelFields,
          });
          
          // Update the resource mapping immediately
          if (response) {
            addOrUpdateResource({
              rid: response.rid,
              name: response.name || elementData.name,
              category: response.category || category,
              type: response.type || type,
            });
            revalidateResourceAndAncestors(response.rid);
          }
          
          toast({
            title: "Success",
            description: "Element created successfully",
          });
          return response;
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
    [toast, TEAM_ID],
  );

  // Delete element using Resources API
  const deleteElement = useCallback(
    async (rid: string) => {
      try {
        setIsLoading(true);
        setError(null);

        await deleteResource(rid);
        
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
    saveElement,
    deleteElement,
    refetchCategories: fetchCategories,
  };
};