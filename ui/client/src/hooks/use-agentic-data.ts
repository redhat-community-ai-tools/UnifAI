import { useQuery } from "@tanstack/react-query";
import {
  fetchAgenticStats,
  fetchActiveSessions,
  fetchAllResources,
  fetchResourceCategories,
} from "@/api/agentic";
import { fetchResolvedBlueprints } from "@/api/blueprints";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";

export function useAgenticData() {
  const { userId, identityType } = useWorkspaceIdentity();

  // Use aggregated stats endpoint for optimal performance
  const agenticStats = useQuery({
    queryKey: ["agenticStats", userId, identityType],
    queryFn: () => fetchAgenticStats(userId, identityType),
    staleTime: 0,
  });

  // Individual queries for granular data when needed by components
  const workflows = useQuery({
    queryKey: ["blueprints", userId, identityType],
    queryFn: () => fetchResolvedBlueprints(userId, identityType),
    staleTime: 0,
  });

  const activeSessions = useQuery({
    queryKey: ["activeSessions", userId, identityType],
    queryFn: () => fetchActiveSessions(userId, identityType),
    staleTime: 0,
  });
  
  // blueprintSessionCounts is now always sourced from agenticStats
  // No separate query needed - follows SOLID principles by using aggregated endpoint

  const resources = useQuery({
    queryKey: ["allResources", userId, identityType],
    queryFn: () => fetchAllResources(userId, identityType),
    staleTime: 0,
  });

  const resourceCategories = useQuery({
    queryKey: ["resourceCategories"],
    queryFn: () => fetchResourceCategories(),
    staleTime: 0,
  });

  return {
    agenticStats: {
      data: agenticStats.data,
      isLoading: agenticStats.isLoading,
      error: agenticStats.error,
    },
    workflows: {
      data: workflows.data ?? [],
      isLoading: workflows.isLoading,
      error: workflows.error,
    },
    activeSessions: {
      data: activeSessions.data ?? [],
      isLoading: activeSessions.isLoading,
      error: activeSessions.error,
    },
    blueprintSessionCounts: {
      // Always use aggregated stats - follows SOLID principles
      data: agenticStats.data?.blueprintSessionCounts ?? {},
      isLoading: agenticStats.isLoading,
      error: agenticStats.error,
    },
    resources: {
      data: resources.data ?? [],
      isLoading: resources.isLoading,
      error: resources.error,
    },
    resourceCategories: {
      data: resourceCategories.data ?? [],
      isLoading: resourceCategories.isLoading,
      error: resourceCategories.error,
    },
    isLoading:
      agenticStats.isLoading ||
      workflows.isLoading ||
      activeSessions.isLoading ||
      resources.isLoading ||
      resourceCategories.isLoading,
  };
}

