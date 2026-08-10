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
  const { teamId } = useWorkspaceIdentity();

  // Use aggregated stats endpoint for optimal performance
  const agenticStats = useQuery({
    queryKey: ["agenticStats", teamId],
    queryFn: () => fetchAgenticStats(teamId),
    staleTime: 0,
  });

  // Individual queries for granular data when needed by components
  const workflows = useQuery({
    queryKey: ["blueprints", teamId],
    queryFn: () => fetchResolvedBlueprints(teamId),
    staleTime: 0,
  });

  const activeSessions = useQuery({
    queryKey: ["activeSessions", teamId],
    queryFn: () => fetchActiveSessions(teamId),
    staleTime: 0,
  });
  
  // blueprintSessionCounts is now always sourced from agenticStats
  // No separate query needed - follows SOLID principles by using aggregated endpoint

  const resources = useQuery({
    queryKey: ["allResources", teamId],
    queryFn: () => fetchAllResources(teamId),
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

