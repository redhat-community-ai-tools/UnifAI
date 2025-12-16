import { useMemo } from "react";
import { WorkflowBlueprint } from "@/api/agentic";

interface WorkflowWithUsage extends WorkflowBlueprint {
  usageCount: number;
  isCurrentlyActive: boolean;
}

export function useWorkflowCalculations(
  blueprints: WorkflowBlueprint[],
  activeSessions: string[],
  blueprintSessionCounts: Record<string, number>
) {
  const mostUsedWorkflows = useMemo<WorkflowWithUsage[]>(() => {
    return blueprints
      .map((blueprint) => {
        const sessionCount = blueprintSessionCounts[blueprint.blueprint_id] ?? 0;
        const isCurrentlyActive =
          Array.isArray(activeSessions) &&
          activeSessions.includes(blueprint.blueprint_id);
        const usageCount =
          sessionCount > 0 ? sessionCount : isCurrentlyActive ? 1 : 0;
        return {
          ...blueprint,
          usageCount,
          isCurrentlyActive,
        };
      })
      .filter((blueprint) => blueprint.usageCount > 0)
      .sort((a, b) => b.usageCount - a.usageCount)
      .slice(0, 5);
  }, [blueprints, activeSessions, blueprintSessionCounts]);

  const unusedWorkflows = useMemo(() => {
    return blueprints.filter(
      (blueprint) => !activeSessions.includes(blueprint.blueprint_id)
    );
  }, [blueprints, activeSessions]);

  return {
    mostUsedWorkflows,
    unusedWorkflows,
  };
}

