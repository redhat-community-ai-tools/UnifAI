import { useEffect, useState, useRef } from "react";
import { listScheduledPrompts } from "@/api/prompts";

/**
 * Returns the set of blueprint IDs that have at least one active scheduled prompt
 * for the given identity. Refetches when identity context changes.
 */
export function useScheduledBlueprints(
  userId: string,
  identityType: string,
): Set<string> {
  const [scheduledIds, setScheduledIds] = useState<Set<string>>(new Set());
  const scopeRef = useRef({ userId, identityType });
  scopeRef.current = { userId, identityType };

  useEffect(() => {
    let cancelled = false;

    const fetchScheduled = async () => {
      try {
        const prompts = await listScheduledPrompts(userId, identityType);
        if (cancelled) return;
        setScheduledIds(
          new Set(
            prompts
              .filter((p) => p.schedule_status === "active")
              .map((p) => p.blueprint_id),
          ),
        );
      } catch {
        if (!cancelled) setScheduledIds(new Set());
      }
    };

    void fetchScheduled();
    return () => { cancelled = true; };
  }, [userId, identityType]);

  return scheduledIds;
}
