import { useMemo } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useView } from "@/contexts/ViewContext";

export interface WorkspaceIdentity {
  /** True when the active workspace is a team workspace. */
  isTeam: boolean;
  /** Team ID when in team view, null otherwise. Send as `teamId` in API calls. */
  teamId: string | null;
  /**
   * The logged-in user's username — always the human, even in team view.
   * Use for credential/OAuth lookups where the key is per-member, not per-team.
   */
  credentialUserId: string;
}

/**
 * Single source of truth for "who owns the current workspace".
 *
 * The backend resolves the authenticated user from the session (X-Session-Id).
 * For team context, the UI only needs to send the teamId — the backend
 * validates membership and resolves the display name server-side.
 */
export function useWorkspaceIdentity(): WorkspaceIdentity {
  const { user } = useAuth();
  const { viewMode, selectedTeam } = useView();

  return useMemo(() => {
    const isTeam = viewMode === "team" && !!selectedTeam;
    return {
      isTeam,
      teamId: isTeam ? selectedTeam!.id : null,
      credentialUserId: user?.username || "default",
    };
  }, [viewMode, selectedTeam, user?.username]);
}
