import { useQuery } from "@tanstack/react-query";
import { listSchedules } from "@/api/schedules";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";

/**
 * Returns the set of blueprint IDs that have at least one active scheduled prompt
 * for the given identity. Shares the "scheduled-prompts" query cache with
 * ScheduledWorkflows so cross-component invalidation works automatically.
 */
export function useScheduledBlueprints(
  teamId?: string,
): Set<string> {
  const { userId } = useWorkspaceIdentity();
  const scopeKey = teamId ?? userId;

  const { data = new Set<string>() } = useQuery({
    queryKey: ["scheduled-prompts", scopeKey],
    queryFn: () => listSchedules(teamId),
    select: (prompts) =>
      new Set(
        prompts
          .filter((p) => p.schedule_status === "active")
          .map((p) => p.blueprint_id),
      ),
    staleTime: 30_000,
  });
  return data;
}

/**
 * Returns a map of blueprint ID -> active schedule count.
 * Shares the same query cache as useScheduledBlueprints / ScheduledWorkflows.
 */
export function useScheduledBlueprintCounts(
  teamId?: string,
): Map<string, number> {
  const { userId } = useWorkspaceIdentity();
  const scopeKey = teamId ?? userId;

  const { data = new Map<string, number>() } = useQuery({
    queryKey: ["scheduled-prompts", scopeKey],
    queryFn: () => listSchedules(teamId),
    select: (prompts) => {
      const counts = new Map<string, number>();
      for (const p of prompts) {
        if (p.schedule_status === "active") {
          counts.set(p.blueprint_id, (counts.get(p.blueprint_id) ?? 0) + 1);
        }
      }
      return counts;
    },
    staleTime: 30_000,
  });
  return data;
}
