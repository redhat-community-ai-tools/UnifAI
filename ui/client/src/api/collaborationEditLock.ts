import axios from "@/http/axiosAgentConfig";

export type TeamEditLockEntityKind = "resource" | "blueprint";

export interface TeamEditLockHolder {
  userId: string;
  displayName: string;
}

/** Present when the server could not confirm lock state (do not assume unlocked). */
export const TEAM_EDIT_LOCK_UNKNOWN = "unknown" as const;
export type TeamEditLockResolved = TeamEditLockHolder | null | typeof TEAM_EDIT_LOCK_UNKNOWN;

function isUnavailable(status: number | undefined): boolean {
  return status === 501;
}

export async function acquireTeamEditLock(params: {
  teamId: string;
  entityKind: TeamEditLockEntityKind;
  entityId: string;
  userId: string;
  displayName: string;
}): Promise<{ acquired: true } | { acquired: false; lockedBy: TeamEditLockHolder }> {
  try {
    const { data } = await axios.post<{
      acquired: boolean;
      lockedBy?: TeamEditLockHolder;
    }>("/collaboration/edit_lock.acquire", {
      teamId: params.teamId,
      entityKind: params.entityKind,
      entityId: params.entityId,
      userId: params.userId,
      displayName: params.displayName,
    });
    if (data.acquired) {
      return { acquired: true };
    }
    return {
      acquired: false,
      lockedBy: data.lockedBy ?? {
        userId: "?",
        displayName: "Another user",
      },
    };
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (isUnavailable(status)) {
      return { acquired: true };
    }
    throw e;
  }
}

export async function releaseTeamEditLock(params: {
  teamId: string;
  entityKind: TeamEditLockEntityKind;
  entityId: string;
  userId: string;
}): Promise<void> {
  try {
    await axios.post("/collaboration/edit_lock.release", {
      teamId: params.teamId,
      entityKind: params.entityKind,
      entityId: params.entityId,
      userId: params.userId,
    });
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (isUnavailable(status)) {
      return;
    }
    throw e;
  }
}

export async function heartbeatTeamEditLock(params: {
  teamId: string;
  entityKind: TeamEditLockEntityKind;
  entityId: string;
  userId: string;
  displayName: string;
}): Promise<void> {
  try {
    await axios.post("/collaboration/edit_lock.heartbeat", {
      teamId: params.teamId,
      entityKind: params.entityKind,
      entityId: params.entityId,
      userId: params.userId,
      displayName: params.displayName,
    });
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (isUnavailable(status)) {
      return;
    }
    throw e;
  }
}

export async function fetchTeamEditLockStatuses(params: {
  teamId: string;
  entityKind: TeamEditLockEntityKind;
  entityIds: string[];
}): Promise<Record<string, TeamEditLockResolved>> {
  if (params.entityIds.length === 0) {
    return {};
  }
  const unknownMap = (): Record<string, TeamEditLockResolved> =>
    Object.fromEntries(params.entityIds.map((id) => [id, TEAM_EDIT_LOCK_UNKNOWN]));

  try {
    const { data } = await axios.post<{ locks: Record<string, TeamEditLockHolder | null> }>(
      "/collaboration/edit_lock.statuses",
      {
        teamId: params.teamId,
        entityKind: params.entityKind,
        entityIds: params.entityIds,
      },
    );
    return (data.locks ?? {}) as Record<string, TeamEditLockResolved>;
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (isUnavailable(status)) {
      return {};
    }
    return unknownMap();
  }
}
