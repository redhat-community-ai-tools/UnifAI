import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { motion } from "framer-motion";
import { useLocation } from "wouter";
import { useMyNewContext } from "@/contexts/MyNewContext";
import { CollabAvatar } from "@/components/shared/CollabAvatar";
import { useAuth } from "@/contexts/AuthContext";
import type { MemberDisplay } from "@/utils/memberDisplay";

export default function TeamWorkflows() {
  const { user } = useAuth();
  const [, setLocation] = useLocation();
  const {
    teamName,
    teamMemberDisplays,
    teamEffectiveMemberCount,
    setSelectedMember,
  } = useMyNewContext();

  function handleClick(member: MemberDisplay) {
    if (member.id === user?.username) {
      setLocation("/inventory");
      return;
    }
    setSelectedMember(member);
    setLocation("/agentic-ai");
  }

  return (
    <>
      <Header
        title="Team Members"
        onToggleSidebar={() => {}}
      />
      <main className="flex-1 overflow-y-auto bg-background-dark">
        <div className="p-6 max-w-md">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <h1 className="text-xl font-semibold text-white mb-1">
              Team Members{teamName ? ` — ${teamName}` : ""}
            </h1>
            <p className="text-sm text-gray-500 mb-4">
              {teamEffectiveMemberCount} member
              {teamEffectiveMemberCount !== 1 ? "s" : ""}
            </p>

            <ul className="rounded-lg border border-gray-800 bg-white/[.02] overflow-hidden divide-y divide-gray-800/60">
              {teamMemberDisplays.map((member) => (
                <li key={member.id}>
                  <button
                    type="button"
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/[.02] transition-colors text-left"
                    onClick={() => handleClick(member)}
                  >
                    <CollabAvatar member={member} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-200 truncate">
                        {member.name}
                      </p>
                      <p className="text-xs text-gray-500 truncate">{member.id}</p>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        </div>
      </main>
      <StatusBar />
    </>
  );
}
