import { useEffect, useState } from "react";
import {
  fetchTeamEditLockStatuses,
  type TeamEditLockEntityKind,
  type TeamEditLockResolved,
} from "@/api/collaborationEditLock";

const POLL_MS = 8000;

/**
 * Polls team edit-lock holders for a list of entity ids (team workspace only).
 */
export function useTeamEditLockPoll(
  teamId: string | undefined,
  entityKind: TeamEditLockEntityKind,
  entityIds: string[],
  enabled: boolean,
): Record<string, TeamEditLockResolved> {
  const [locks, setLocks] = useState<Record<string, TeamEditLockResolved>>({});
  const idsKey = JSON.stringify(entityIds);

  useEffect(() => {
    if (!enabled || !teamId) {
      setLocks({});
      return;
    }
    let parsed: string[];
    try {
      parsed = JSON.parse(idsKey) as string[];
    } catch {
      setLocks({});
      return;
    }
    if (parsed.length === 0) {
      setLocks({});
      return;
    }

    let cancelled = false;

    const run = async () => {
      const next = await fetchTeamEditLockStatuses({
        teamId,
        entityKind,
        entityIds: parsed,
      });
      if (!cancelled) {
        setLocks(next);
      }
    };

    void run();
    const timer = window.setInterval(run, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [teamId, entityKind, idsKey, enabled]);

  return locks;
}
