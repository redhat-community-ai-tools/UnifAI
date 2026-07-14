import { useEffect, useState } from "react";
import {
  fetchBuiltinEditLockStatuses,
  type BuiltinEditLockResolved,
} from "@/api/resources";

const POLL_MS = 8000;

/**
 * Polls admin edit-lock holders for a list of built-in resource ids.
 */
export function useBuiltinEditLockPoll(
  entityIds: string[],
  enabled: boolean,
): Record<string, BuiltinEditLockResolved> {
  const [locks, setLocks] = useState<Record<string, BuiltinEditLockResolved>>({});
  const idsKey = JSON.stringify(entityIds);

  useEffect(() => {
    if (!enabled) {
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
      const next = await fetchBuiltinEditLockStatuses(parsed);
      if (!cancelled) setLocks(next);
    };

    void run();
    const timer = window.setInterval(run, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [idsKey, enabled]);

  return locks;
}
