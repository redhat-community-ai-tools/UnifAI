import { useMemo } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useView } from "@/contexts/ViewContext";

export interface WorkspaceIdentity {
  /** True when the active workspace is a team workspace. */
  isTeam: boolean;
  /** Owner id: team id in team view, else the logged-in user's username. */
  userId: string;
  /** Display name: team name in team view, else the user's name. */
  displayName: string;
  /** Team id when in team mode, undefined when in user mode (backend reads identity from session cookie). */
  teamId: string | undefined;
  /**
   * The logged-in user's username — always the human, even in team view.
   * Use for credential/OAuth lookups where the key is per-member, not per-team.
   */
  credentialUserId: string;
}

/**
 * Single source of truth for "who owns the current workspace".
 *
 * Replaces the repeated pattern of:
 * ```
 * const isTeam = viewMode === "team" && !!selectedTeam;
 * const contextUserId = isTeam ? selectedTeam!.id : (user?.username || "default");
 * const teamId = isTeam ? selectedTeam!.id : undefined;
 * ```
 */
export function useWorkspaceIdentity(): WorkspaceIdentity {
  const { user } = useAuth();
  const { viewMode, selectedTeam } = useView();

  return useMemo(() => {
    const isTeam = viewMode === "team" && !!selectedTeam;
    return {
      isTeam,
      userId: isTeam ? selectedTeam!.id : (user?.username || "default"),
      displayName: isTeam ? selectedTeam!.name : (user?.name || "User"),
      teamId: isTeam ? selectedTeam!.id : undefined,
      credentialUserId: user?.username || "default",
    };
  }, [viewMode, selectedTeam, user?.username, user?.name]);
}
