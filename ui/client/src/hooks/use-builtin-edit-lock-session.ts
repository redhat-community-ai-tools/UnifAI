import { useCallback, useEffect, useRef } from "react";
import {
  releaseBuiltinEditLock,
  heartbeatBuiltinEditLock,
} from "@/api/resources";

const HEARTBEAT_MS = 60_000;

/**
 * Manages the lifecycle of a single held admin edit-lock: renews it on an
 * interval while active, and releases it on stop / unmount.
 *
 * Acquiring the lock (and handling the "already locked by someone else"
 * case) stays with the caller — this hook only owns what happens *after*
 * a lock has been successfully acquired.
 */
export function useBuiltinEditLockSession() {
  const lockedRidRef = useRef<string | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopLockHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
    if (lockedRidRef.current) {
      releaseBuiltinEditLock(lockedRidRef.current).catch(() => {});
      lockedRidRef.current = null;
    }
  }, []);

  const startLockHeartbeat = useCallback((rid: string) => {
    stopLockHeartbeat();
    lockedRidRef.current = rid;
    heartbeatRef.current = setInterval(() => {
      heartbeatBuiltinEditLock(rid).catch(() => {});
    }, HEARTBEAT_MS);
  }, [stopLockHeartbeat]);

  useEffect(() => {
    return () => { stopLockHeartbeat(); };
  }, [stopLockHeartbeat]);

  return { startLockHeartbeat, stopLockHeartbeat };
}
