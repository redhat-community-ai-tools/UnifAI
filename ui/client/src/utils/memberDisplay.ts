export const MEMBER_COLORS = [
  "from-blue-500 to-blue-600",
  "from-emerald-500 to-emerald-600",
  "from-pink-500 to-pink-600",
  "from-orange-500 to-orange-600",
  "from-violet-500 to-violet-600",
  "from-cyan-500 to-cyan-600",
  "from-amber-500 to-amber-600",
  "from-rose-500 to-rose-600",
];

export interface MemberDisplay {
  id: string;
  name: string;
  initials: string;
  color: string;
}

export function buildMemberDisplay(username: string, index: number): MemberDisplay {
  const parts = username.split(/[._\-\s@]+/).filter(Boolean);
  const initials =
    parts.length >= 2
      ? (parts[0][0] + parts[1][0]).toUpperCase()
      : username.slice(0, 2).toUpperCase();
  return {
    id: username,
    name: username,
    initials,
    color: MEMBER_COLORS[index % MEMBER_COLORS.length],
  };
}
