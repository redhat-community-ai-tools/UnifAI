import React, { createContext, useContext, useEffect, useState, ReactNode, useCallback, useRef } from 'react';
import axios from '@/http/axiosAgentConfig';
import { useAuth } from './AuthContext';
import { catalogService } from '@/api/catalog';
import { ElementValidationResult, CachedValidationResult, BlueprintValidationResult } from '@/types/validation';

// Validation status type
export type ValidationStatus = 'loading' | 'valid' | 'invalid';

interface ResourceMapping {
  rid: string;
  name: string;
  category: string;
  type: string;
}

interface AgenticAIContextType {
  // Mapping from UUID (rid) to resource name
  uuidToNameMap: Map<string, string>;
  // Mapping from UUID (rid) to full resource info
  uuidToResourceMap: Map<string, ResourceMapping>;
  isLoading: boolean;
  error: string | null;
  getResourceName: (ref: string | any) => string;
  getResource: (ref: string | any) => ResourceMapping | null;
  // Recursively resolve all refs in a config object
  resolveRefsInConfig: (config: any) => any;
  refreshMapping: () => Promise<void>;
  // Incrementally update resource mapping (smart updates)
  addOrUpdateResource: (resource: ResourceMapping) => void;
  removeResource: (rid: string) => void;
  // Validation functions
  getValidationResult: (rid: string) => ElementValidationResult | null;
  getValidationStatus: (rid: string) => ValidationStatus;
  validateResources: (rids: string[]) => Promise<void>;
  // Dependency parent tracking - revalidate resource and all ancestors after edit
  revalidateResourceAndAncestors: (rid: string) => Promise<void>;
  // Get all ancestor rids for a given resource
  getAllAncestors: (rid: string) => string[];
  // Cache all element results from a blueprint validation result
  cacheBlueprintValidationResults: (blueprintResult: BlueprintValidationResult) => void;
}

const AgenticAIContext = createContext<AgenticAIContextType | undefined>(undefined);

interface AgenticAIProviderProps {
  children: ReactNode;
}

export const AgenticAIProvider: React.FC<AgenticAIProviderProps> = ({ children }) => {
  const [uuidToNameMap, setUuidToNameMap] = useState<Map<string, string>>(new Map());
  const [uuidToResourceMap, setUuidToResourceMap] = useState<Map<string, ResourceMapping>>(new Map());
  const [validationCache, setValidationCache] = useState<Map<string, CachedValidationResult>>(new Map());
  const [validationStatusMap, setValidationStatusMap] = useState<Map<string, ValidationStatus>>(new Map());
  // Dependency parent tracking: maps resourceId -> [parentIds] where parents are resources that depend on this resource
  const [dependencyParentMap, setDependencyParentMap] = useState<Map<string, string[]>>(new Map());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const USER_ID = user?.username || "default";
  
  // Use ref to access latest cache without causing re-renders in callbacks
  const validationCacheRef = useRef(validationCache);
  validationCacheRef.current = validationCache;
  
  // Use ref to access latest dependency parent map without causing re-renders in callbacks
  const dependencyParentMapRef = useRef(dependencyParentMap);
  dependencyParentMapRef.current = dependencyParentMap;

  // Use ref for validation status map to access latest status without stale closures
  const validationStatusMapRef = useRef(validationStatusMap);
  validationStatusMapRef.current = validationStatusMap;

  // Ref to hold the revalidate ancestors function (avoids circular dependency in useCallback)
  const revalidateAncestorsRef = useRef<((rid: string) => Promise<void>) | null>(null);

  // ==================== Helper Functions ====================

  // Helper: Remove rid from validation cache
  const removeFromValidationCache = useCallback((rid: string) => {
    setValidationCache((prevCache) => {
      const newCache = new Map(prevCache);
      newCache.delete(rid);
      return newCache;
    });
    setValidationStatusMap((prevStatus) => {
      const newStatus = new Map(prevStatus);
      newStatus.delete(rid);
      return newStatus;
    });
  }, []);

  // Helper: Set validation status for a rid
  const setValidationStatus = useCallback((rid: string, status: ValidationStatus) => {
    setValidationStatusMap((prevStatus) => {
      const newStatus = new Map(prevStatus);
      newStatus.set(rid, status);
      return newStatus;
    });
  }, []);

  // Helper: Cache a validation result and update status
  // Automatically triggers ancestor revalidation if status changed
  const cacheValidationResult = useCallback((rid: string, result: ElementValidationResult) => {
    // Get previous status before updating (use ref to get latest)
    const previousStatus = validationCacheRef.current.get(rid)?.result.is_valid ? 'valid' : 'invalid';
    const newStatus: ValidationStatus = result.is_valid ? 'valid' : 'invalid';
    
    // Check if status actually changed (not first-time validation, and status differs)
    const statusChanged = previousStatus !== undefined &&  
                          previousStatus !== newStatus;

    // Update the cache
    setValidationCache((prevCache) => {
      const newCache = new Map(prevCache);
      newCache.set(rid, {
        result,
        timestamp: Date.now(),
      });
      return newCache;
    });
    
    // Update the status map
    setValidationStatusMap((prevStatusMap) => {
      const updatedStatusMap = new Map(prevStatusMap);
      updatedStatusMap.set(rid, newStatus);
      return updatedStatusMap;
    });

    // If status changed, trigger ancestor revalidation
    if (statusChanged && revalidateAncestorsRef.current) {
      // Use setTimeout to avoid blocking the current call stack
      // and to ensure state updates have been processed
      setTimeout(() => {
        revalidateAncestorsRef.current?.(rid);
      }, 0);
    }
  }, []);

  // Helper: Create error validation result
  const createErrorResult = useCallback((rid: string, errorMessage: string): ElementValidationResult => {
    return {
      is_valid: false,
      element_rid: rid,
      element_type: 'unknown',
      name: null,
      messages: [{
        severity: 'error',
        code: 'NETWORK_ERROR',
        message: errorMessage,
        field: null,
      }],
      dependency_results: {},
    };
  }, []);

  // Helper: Update dependency parent map based on validation result
  // This tracks which resources are "parents" (depend on) each resource
  const updateDependencyParentMap = useCallback((rid: string, dependencyResults: Record<string, ElementValidationResult>) => {
    setDependencyParentMap((prevMap) => {
      const newMap = new Map(prevMap);
      
      // Ensure the validated resource exists in the map
      if (!newMap.has(rid)) {
        newMap.set(rid, []);
      }
      
      // For each dependency, add the current resource as a parent
      const dependencyRids = Object.keys(dependencyResults);
      for (const depRid of dependencyRids) {
        const existingParents = newMap.get(depRid) || [];
        // Only add if not already present
        if (!existingParents.includes(rid)) {
          newMap.set(depRid, [...existingParents, rid]);
        }
      }
      
      return newMap;
    });
  }, []);

  // Helper: Fetch validation from API and cache result
  const fetchAndCacheValidation = useCallback(async (rid: string): Promise<ElementValidationResult> => {
    try {
      const response = await axios.post<ElementValidationResult>(
        '/resources/resource.validate',
        { resourceId: rid }
      );
      const result = response.data;
      updateDependencyParentMap(rid, result.dependency_results);
      cacheValidationResult(rid, result);
      return result;
    } catch (err: any) {
      console.error(`Error validating resource ${rid}:`, err);
      const errorResult = createErrorResult(
        rid, 
        err.response?.data?.error || 'Failed to validate resource'
      );
      cacheValidationResult(rid, errorResult);
      return errorResult;
    }
  }, [cacheValidationResult, createErrorResult, updateDependencyParentMap]);

  // ==================== Resource Mapping Functions ====================

  // Fetch all resources for all categories
  const fetchAllResources = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch categories from backend using centralized catalog service
      const categories = await catalogService.fetchCategories();      

      const nameMap = new Map<string, string>();
      const resourceMap = new Map<string, ResourceMapping>();

      // Fetch resources for each category
      await Promise.all(
        categories.map(async (category) => {
          try {
            const response = await axios.get<{
              resources: Array<{
                rid: string;
                name: string;
                category: string;
                type: string;
              }>;
            }>(`/resources/resources.list?userId=${USER_ID}&category=${category}&limit=1000`);

            response.data.resources.forEach((resource) => {
              nameMap.set(resource.rid, resource.name);
              resourceMap.set(resource.rid, {
                rid: resource.rid,
                name: resource.name,
                category: resource.category,
                type: resource.type,
              });
            });
          } catch (err: any) {
            console.warn(`Failed to fetch resources for category ${category}:`, err);
          }
        })
      );

      setUuidToNameMap(nameMap);
      setUuidToResourceMap(resourceMap);
    } catch (err: any) {
      const errorMessage = err.response?.data?.error || "Failed to fetch resource mappings";
      setError(errorMessage);
      console.error("Error fetching resource mappings:", err);
    } finally {
      setIsLoading(false);
    }
  }, [USER_ID]);

  // Get resource name from a ref (falls back to type if no name)
  const getResourceName = useCallback((ref: string | any): string => {
    if (!ref) return '';
    
// Helper to get display name from resource (name or type as fallback)
const getDisplayName = (uuid: string): string => {
  const resource = uuidToResourceMap.get(uuid);
  if (resource) {
    // Return name if available, otherwise return type
    return resource.name || resource.type || uuid;
  }
  return uuidToNameMap.get(uuid) || uuid;
};

if (typeof ref === 'string') {
  if (ref.startsWith('$ref:')) {
    const uuid = ref.substring(5);
    return getDisplayName(uuid);
  }
  // Handle raw UUIDs (check if it exists in the map)
  if (uuidToResourceMap.has(ref) || uuidToNameMap.has(ref)) {
    return getDisplayName(ref);
  }
  return ref;
}

if (typeof ref === 'object' && ref !== null) {
  if (ref.$ref) {
    const uuid = typeof ref.$ref === 'string' && ref.$ref.startsWith('$ref:') 
      ? ref.$ref.substring(5) 
      : ref.$ref;
    return getDisplayName(uuid);
  }
}

return String(ref);
}, [uuidToNameMap, uuidToResourceMap]);

  // Get full resource info from a ref
  const getResource = useCallback((ref: string | any): ResourceMapping | null => {
    if (!ref) return null;
    
    let uuid: string | null = null;

    // Handle string references like "$ref:uuid"
    if (typeof ref === 'string') {
      if (ref.startsWith('$ref:')) {
        uuid = ref.substring(5);
      } else if (uuidToResourceMap.has(ref)) {
        uuid = ref;
      } else {
        return null;
      }
    } else if (typeof ref === 'object' && ref !== null && ref.$ref) {
      uuid = typeof ref.$ref === 'string' && ref.$ref.startsWith('$ref:') 
        ? ref.$ref.substring(5) 
        : ref.$ref;
    }
    
    if (uuid) {
      return uuidToResourceMap.get(uuid) || null;
    }
    
    return null;
  }, [uuidToResourceMap]);

  // Check if a string is a known resource ID (exists in our resource map)
  const isKnownResourceId = useCallback((str: string): boolean => {
    return uuidToResourceMap.has(str);
  }, [uuidToResourceMap]);

  // Recursively resolve all refs in a config object
  const resolveRefsInConfig = useCallback((config: any): any => {
    // Handle null/undefined
    if (config === null || config === undefined) {
      return config;
    }

    // Handle arrays - map over items and resolve refs
    if (Array.isArray(config)) {
      return config.map((item) => {
        // If item is a string ref, resolve it directly
        if (typeof item === 'string' && item.startsWith('$ref:')) {
          return getResourceName(item);
        }
        // If item is an object ref like { "$ref": "uuid" }, resolve it
        if (typeof item === 'object' && item !== null && item.$ref) {
          return getResourceName(item);
        }
        // If item is a known resource ID (raw UUID), resolve it
        if (typeof item === 'string' && isKnownResourceId(item)) {
          return getResourceName(item);
        }
        // Otherwise, recursively resolve
        return resolveRefsInConfig(item);
      });
    }

    // Handle primitives (strings, numbers, booleans)
    if (typeof config !== 'object') {
      // If it's a string ref, resolve it
      if (typeof config === 'string' && config.startsWith('$ref:')) {
        return getResourceName(config);
      }
      // If it's a known resource ID (raw UUID), resolve it
      if (typeof config === 'string' && isKnownResourceId(config)) {
        return getResourceName(config);
      }
      return config;
    }

    // Handle object refs like { "$ref": "uuid" } - resolve to name directly
    if (config.$ref) {
      return getResourceName(config);
    }

    // Handle objects - recursively resolve all properties
    const resolved: any = {};
    for (const [key, value] of Object.entries(config)) {
      if (typeof value === 'string' && value.startsWith('$ref:')) {
        // Resolve the ref to a name
        resolved[key] = getResourceName(value);
      } else if (typeof value === 'string' && isKnownResourceId(value)) {
        // Resolve known resource IDs (raw UUIDs)
        resolved[key] = getResourceName(value);
      } else if (typeof value === 'object' && value !== null) {
        // Check if this object is itself a ref
        if ('$ref' in value) {
          resolved[key] = getResourceName(value);
        } else {
          // Recursively resolve nested objects and arrays
          resolved[key] = resolveRefsInConfig(value);
        }
      } else {
        resolved[key] = value;
      }
    }
    return resolved;
  }, [getResourceName, isKnownResourceId]);

  // Refresh the mapping
  const refreshMapping = useCallback(async () => {
    await fetchAllResources();
  }, [fetchAllResources]);

  // Incrementally add or update a single resource in the mapping
  const addOrUpdateResource = useCallback((resource: ResourceMapping) => {
    setUuidToNameMap((prevMap) => {
      const newMap = new Map(prevMap);
      newMap.set(resource.rid, resource.name);
      return newMap;
    });
    setUuidToResourceMap((prevMap) => {
      const newMap = new Map(prevMap);
      newMap.set(resource.rid, resource);
      return newMap;
    });
  }, []);

  // Incrementally remove a resource from the mapping
  const removeResource = useCallback((rid: string) => {
    setUuidToNameMap((prevMap) => {
      const newMap = new Map(prevMap);
      newMap.delete(rid);
      return newMap;
    });
    setUuidToResourceMap((prevMap) => {
      const newMap = new Map(prevMap);
      newMap.delete(rid);
      return newMap;
    });
    removeFromValidationCache(rid);
  }, [removeFromValidationCache]);

  // ==================== Validation Functions ====================

  // Get cached validation result for a resource
  const getValidationResult = useCallback((rid: string): ElementValidationResult | null => {
    const cached = validationCache.get(rid);
    return cached ? cached.result : null;
  }, [validationCache]);

  // Get validation status for a resource
  const getValidationStatus = useCallback((rid: string): ValidationStatus => {
    return validationStatusMap.get(rid) || 'loading';
  }, [validationStatusMap]);

  // Validate multiple resources in parallel (only those not already cached)
  const validateResources = useCallback(async (rids: string[]): Promise<void> => {
    // Filter out resources that are already cached
    const uncachedRids = rids.filter(rid => !validationCacheRef.current.has(rid));
    
    if (uncachedRids.length === 0) {
      return;
    }

    // Set all uncached resources to loading state
    uncachedRids.forEach(rid => setValidationStatus(rid, 'loading'));

    // Validate all uncached resources in parallel
    await Promise.all(
      uncachedRids.map(rid => fetchAndCacheValidation(rid))
    );
  }, [setValidationStatus, fetchAndCacheValidation]);

  // Get all ancestors (parents, grandparents, etc.) of a resource recursively
  // Uses ref to access latest map and avoid stale closures
  const getAllAncestors = useCallback((rid: string): string[] => {
    const ancestors: Set<string> = new Set();
    const visited: Set<string> = new Set();
    
    const collectAncestors = (currentRid: string) => {
      // Avoid cycles by tracking visited nodes
      if (visited.has(currentRid)) {
        return;
      }
      visited.add(currentRid);
      
      // Get parents from the current map ref
      const parents = dependencyParentMapRef.current.get(currentRid) || [];
      for (const parentRid of parents) {
        ancestors.add(parentRid);
        collectAncestors(parentRid);
      }
    };
    
    collectAncestors(rid);
    return Array.from(ancestors);
  }, []);

  // Revalidate all ancestors of a resource
  // This ensures that when a child resource's status changes, all parent resources
  // that depend on it are also revalidated to reflect potential cascading status changes
  const revalidateAncestors = useCallback(async (rid: string): Promise<void> => {    
    // Find all ancestors and revalidate them
    const ancestors = getAllAncestors(rid);
    if (ancestors.length > 0) {
      // Invalidate all ancestors
      ancestors.forEach(ancestorRid => {
        setValidationStatus(ancestorRid, 'loading');
      });
      
      // Revalidate all ancestors in parallel
      await Promise.all(
        ancestors.map(ancestorRid => fetchAndCacheValidation(ancestorRid))
      );
    }
  }, [removeFromValidationCache, setValidationStatus, fetchAndCacheValidation, getAllAncestors]);

  // Keep the ref updated with the latest revalidateAncestors function
  revalidateAncestorsRef.current = revalidateAncestors;

  // Public function to manually trigger revalidation of a resource and its ancestors
  // Useful when explicitly needing to refresh validation (e.g., after resource edit/save)
  // Note: ancestors will be automatically revalidated if status changed via cacheValidationResult
  const revalidateResourceAndAncestors = useCallback(async (rid: string): Promise<void> => {
    setValidationStatus(rid, 'loading');
    await fetchAndCacheValidation(rid);
  }, [fetchAndCacheValidation]);

  // Cache all element results from a blueprint validation result
  // This leverages the blueprint.validate API response to populate our validation cache
  const cacheBlueprintValidationResults = useCallback((blueprintResult: BlueprintValidationResult) => {
    // Helper function to recursively cache an element and its dependencies
    const cacheElementAndDependencies = (elementResult: ElementValidationResult) => {
      cacheValidationResult(elementResult.element_rid, elementResult);

      // Recursively cache all dependency results
      Object.values(elementResult.dependency_results).forEach(depResult => {
        cacheElementAndDependencies(depResult);
      });
    };

    // Cache all top-level element results
    Object.values(blueprintResult.element_results).forEach(elementResult => {
      cacheElementAndDependencies(elementResult);
    });
  }, [cacheValidationResult, updateDependencyParentMap]);

  // ==================== Effects ====================

  // Fetch resources when user changes or component mounts
  useEffect(() => {
    if (USER_ID) {
      fetchAllResources();
    }
  }, [USER_ID, fetchAllResources]);

  // ==================== Context Value ====================

  const value: AgenticAIContextType = {
    uuidToNameMap,
    uuidToResourceMap,
    isLoading,
    error,
    getResourceName,
    getResource,
    resolveRefsInConfig,
    refreshMapping,
    addOrUpdateResource,
    removeResource,
    getValidationResult,
    getValidationStatus,
    validateResources,
    revalidateResourceAndAncestors,
    getAllAncestors,
    cacheBlueprintValidationResults,
  };

  return (
    <AgenticAIContext.Provider value={value}>
      {children}
    </AgenticAIContext.Provider>
  );
};

export const useAgenticAI = (): AgenticAIContextType => {
  const context = useContext(AgenticAIContext);
  if (context === undefined) {
    throw new Error('useAgenticAI must be used within an AgenticAIProvider');
  }
  return context;
};

