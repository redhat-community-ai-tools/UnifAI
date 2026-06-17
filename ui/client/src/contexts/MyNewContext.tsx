import React, { createContext, useContext, useMemo, useEffect, useRef, ReactNode, useState } from "react";
import { useLocation } from "wouter";
import { useView } from "@/contexts/ViewContext";
import { useTeamMembers } from "@/hooks/use-team-members";
import type { MemberDisplay } from "@/utils/memberDisplay";
import { getEffectiveMemberCount } from "@/api/teams";

interface MyNewContextType {
  isTeamMode: boolean;
  teamId: string;
  teamName: string;
  selectedMember: MemberDisplay | undefined;
  teamMembers: string[];
  teamMemberDisplays: MemberDisplay[];
  teamCreatedBy: string;
  teamEffectiveMemberCount: number;
  setSelectedMember: (member: MemberDisplay | undefined) => void;
}

const MyNewContext = createContext<MyNewContextType | undefined>(undefined);

export function MyNewProvider({ children }: { children: ReactNode }) {
  const { viewMode, selectedTeam } = useView();
  const teamMemberDisplays = useTeamMembers();
  const [selectedMember, setSelectedMember] = useState<MemberDisplay | undefined>(undefined);
  const [location] = useLocation();
  const prevLocationRef = useRef(location);

  // Clear member filter when leaving /agentic-ai (any route change away from workflows).
  useEffect(() => {
    const prev = prevLocationRef.current;
    if (prev === "/agentic-ai" && location !== "/agentic-ai") {
      setSelectedMember(undefined);
    }
    prevLocationRef.current = location;
  }, [location]);

  // Clear when switching teams so a prior member selection does not carry over.
  useEffect(() => {
    setSelectedMember(undefined);
  }, [selectedTeam?.id]);

  // Memoize the context value to prevent unnecessary re-renders.
  const value = useMemo(() => {
    const teamEffectiveMemberCount = selectedTeam
      ? getEffectiveMemberCount(
          selectedTeam.members,
          selectedTeam.effective_member_count,
        )
      : teamMemberDisplays.length;

    return {
      selectedMember,
      isTeamMode: viewMode === "team",
      teamId: selectedTeam?.id ?? "",
      teamName: selectedTeam?.name ?? "",
      teamMembers: teamMemberDisplays.map((m) => m.id),
      teamMemberDisplays,
      teamCreatedBy: selectedTeam?.created_by ?? "",
      teamEffectiveMemberCount,
      setSelectedMember,
    };
  }, [viewMode, selectedTeam, teamMemberDisplays, selectedMember]);

  return (
    <MyNewContext.Provider value={value}>
      {children}
    </MyNewContext.Provider>
  );
}

export function useMyNewContext() {
  const context = useContext(MyNewContext);
  if (context === undefined) {
    throw new Error("useMyNewContext must be used within a MyNewProvider");
  }
  return context;
}
