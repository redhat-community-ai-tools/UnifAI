import React, { createContext, useState, useContext, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { listUserTeams, Team, TeamMember } from "@/api/teams";

export type ViewMode = "private" | "team";

export interface TeamInfo {
  id: string;
  name: string;
  members: TeamMember[];
  created_by: string;
  effective_member_count?: number;
}

export interface ViewContextType {
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  selectedTeam: TeamInfo | null;
  setSelectedTeam: (team: TeamInfo | null) => void;
  teams: TeamInfo[];
  refreshTeams: () => Promise<void>;
  teamsLoading: boolean;
  teamsReady: boolean;
  userGroups: string[];
}

function toTeamInfo(t: Team): TeamInfo {
  return {
    id: t.team_id,
    name: t.name,
    members: t.members,
    created_by: t.created_by,
    effective_member_count: t.effective_member_count,
  };
}

const defaultViewContext: ViewContextType = {
  viewMode: "private",
  setViewMode: () => {},
  selectedTeam: null,
  setSelectedTeam: () => {},
  teams: [],
  refreshTeams: async () => {},
  teamsLoading: false,
  teamsReady: false,
  userGroups: [],
};

const ViewContext = createContext<ViewContextType>(defaultViewContext);

export function ViewProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [viewMode, setViewModeRaw] = useState<ViewMode>("private");
  const [selectedTeam, setSelectedTeam] = useState<TeamInfo | null>(null);
  const [teams, setTeams] = useState<TeamInfo[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [userGroups, setUserGroups] = useState<string[]>([]);
  /** True after we finish a teams fetch attempt (success or error), or when there is no user to query. */
  const [teamsBootstrapComplete, setTeamsBootstrapComplete] = useState(false);
  /** True only after a successful teams list load (used to optionally re-fetch when entering team mode). */
  const teamsListSucceededRef = useRef(false);

  const selectedTeamRef = useRef(selectedTeam);
  selectedTeamRef.current = selectedTeam;

  const refreshTeams = useCallback(async () => {
    if (!user?.username) {
      setTeams([]);
      setTeamsLoading(false);
      setTeamsBootstrapComplete(true);
      teamsListSucceededRef.current = false;
      return;
    }

    setTeamsBootstrapComplete(false);
    setTeamsLoading(true);
    teamsListSucceededRef.current = false;
    try {
      let roverGroupIds: string[] | undefined;
      try {
        const { api } = await import('@/http/authClient');
        const res = await api.get<{ groups: string[] }>('/auth/user/groups', {
          params: { fresh: '1' },
        });
        roverGroupIds = res.data.groups ?? [];
        setUserGroups(roverGroupIds);
      } catch {
        // Groups endpoint may not be available; fall back gracefully
        roverGroupIds = undefined;
      }

      const fetched = await listUserTeams(user.username, roverGroupIds);
      const mapped = fetched.map(toTeamInfo);
      setTeams(mapped);
      teamsListSucceededRef.current = true;
      const current = selectedTeamRef.current;
      if (current) {
        const updated = mapped.find((t) => t.id === current.id);
        if (updated) {
          setSelectedTeam(updated);
        } else if (mapped.length > 0) {
          setSelectedTeam(mapped[0]);
        } else {
          setSelectedTeam(null);
        }
      } else if (mapped.length > 0) {
        setSelectedTeam(mapped[0]);
      }
    } catch (err) {
      console.error("Failed to fetch teams:", err);
    } finally {
      setTeamsLoading(false);
      setTeamsBootstrapComplete(true);
    }
  }, [user?.username]);

  useEffect(() => {
    void refreshTeams();
  }, [refreshTeams]);

  const setViewMode = useCallback((mode: ViewMode) => {
    setViewModeRaw(mode);
    if (
      mode === "team" &&
      user?.username &&
      !teamsListSucceededRef.current &&
      !teamsLoading
    ) {
      void refreshTeams();
    }
  }, [refreshTeams, user?.username, teamsLoading]);

  const teamsReady = teamsBootstrapComplete && !teamsLoading;

  return (
    <ViewContext.Provider
      value={{
        viewMode,
        setViewMode,
        selectedTeam,
        setSelectedTeam,
        teams,
        refreshTeams,
        teamsLoading,
        teamsReady,
        userGroups,
      }}
    >
      {children}
    </ViewContext.Provider>
  );
}

export function useView() {
  return useContext(ViewContext);
}
