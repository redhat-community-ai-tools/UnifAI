import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import {
  fetchAgenticStats,
  fetchBlueprints,
  fetchActiveSessions,
  fetchAllResources,
  fetchResourceCategories,
} from "@/api/agentic";

export function useAgenticData() {
  const { user } = useAuth();
  const userId = user?.username || "default";

  // Use aggregated stats endpoint for optimal performance
  const agenticStats = useQuery({
    queryKey: ["agenticStats", userId],
    queryFn: () => fetchAgenticStats(userId),
    staleTime: 0,
  });

  // Individual queries for granular data when needed by components
  const workflows = useQuery({
    queryKey: ["blueprints", userId],
    queryFn: () => fetchBlueprints(userId),
    staleTime: 0,
  });

  const activeSessions = useQuery({
    queryKey: ["activeSessions", userId],
    queryFn: () => fetchActiveSessions(userId),
    staleTime: 0,
  });

  // blueprintSessionCounts is now always sourced from agenticStats
  // No separate query needed - follows SOLID principles by using aggregated endpoint

  const resources = useQuery({
    queryKey: ["allResources", userId],
    queryFn: () => fetchAllResources(userId),
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

