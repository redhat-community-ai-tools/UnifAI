import { useMemo } from "react";
import { useView } from "@/contexts/ViewContext";
import { MemberDisplay, buildMemberDisplay } from "@/utils/memberDisplay";

/**
 * Derives the flat, deduplicated list of team members (as MemberDisplay[])
 * from the currently-selected team.  Groups are expanded so every individual
 * user appears exactly once.
 *
 * Returns an empty array when no team is selected.
 */
export function useTeamMembers(): MemberDisplay[] {
  const { selectedTeam } = useView();

  return useMemo(() => {
    if (!selectedTeam?.members) return [];
    const seen = new Set<string>();
    const result: MemberDisplay[] = [];
    for (const m of selectedTeam.members) {
      if (m.type === "user") {
        if (!seen.has(m.id)) {
          seen.add(m.id);
          result.push(buildMemberDisplay(m.id, result.length));
        }
      } else if (m.type === "group" && m.group_members) {
        for (const uid of m.group_members) {
          if (!seen.has(uid)) {
            seen.add(uid);
            result.push(buildMemberDisplay(uid, result.length));
          }
        }
      }
    }
    return result;
  }, [selectedTeam?.members]);
}
