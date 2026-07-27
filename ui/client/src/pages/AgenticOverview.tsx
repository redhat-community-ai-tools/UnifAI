import { useState, useMemo } from "react";
import { FaProjectDiagram, FaChartPie, FaPlayCircle, FaBoxes, FaTrophy } from "react-icons/fa";
import { motion } from "framer-motion";
import { getPaletteColor } from "@/lib/colorUtils";

import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";

import GlassPanel from "@/components/ui/GlassPanel";
import { StatCard } from "@/components/ui/stat-card";
import { ResourceDistributionChart } from "@/components/ui/resource-distribution-chart";
import { WorkflowList } from "@/components/dashboard/WorkflowList";
import { WorkflowBlueprint } from "@/api/blueprints";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTheme } from "@/contexts/ThemeContext";
import { useView } from "@/contexts/ViewContext";
import { getEffectiveMemberCount } from "@/api/teams";
import {
  Workflow, Database, Zap, TrendingUp, Users, Share2,
  Crown, Medal, Award, CircleDot,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import GraphDisplay from "@/components/agentic-ai/graphs/GraphDisplay";

import { useAgenticData } from "@/hooks/use-agentic-data";
import { useWorkflowCalculations } from "@/hooks/use-workflow-calculations";
import { useResourceDistribution } from "@/hooks/use-resource-distribution";
import { useTeamMembers } from "@/hooks/use-team-members";
import { CollabAvatar } from "@/components/shared/CollabAvatar";

// ─── Rank visuals ────────────────────────────────────────────────────────────

const RANK_STYLES = [
  "bg-gradient-to-br from-amber-400 to-amber-600 text-amber-950",
  "bg-gradient-to-br from-slate-300 to-slate-500 text-slate-900",
  "bg-gradient-to-br from-orange-500 to-orange-700 text-white",
];
const RANK_ICONS = [Crown, Medal, Award];

const TeamAvatar = CollabAvatar;

// ─── Component ───────────────────────────────────────────────────────────────

export default function AgenticOverview() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowBlueprint | null>(null);
  const [isWorkflowModalOpen, setIsWorkflowModalOpen] = useState(false);
  const { primaryHex } = useTheme();
  const { viewMode, selectedTeam } = useView();

  const {
    agenticStats,
    workflows,
    activeSessions,
    blueprintSessionCounts,
    resources,
    resourceCategories,
  } = useAgenticData();

  const themeColors = useMemo(() => {
    const primary = primaryHex || "#A60000";
    return {
      sessions: getPaletteColor(primary, 1, 4),
      resources: getPaletteColor(primary, 2, 4),
      categories: getPaletteColor(primary, 3, 4),
    };
  }, [primaryHex]);

  const resourceDistribution = useResourceDistribution(
    resourceCategories.data,
    agenticStats.data?.resourcesByCategory || []
  );

  const { mostUsedWorkflows, unusedWorkflows } = useWorkflowCalculations(
    workflows.data,
    activeSessions.data,
    blueprintSessionCounts.data
  );

  const handleWorkflowClick = (workflow: WorkflowBlueprint) => {
    setSelectedWorkflow(workflow);
    setIsWorkflowModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsWorkflowModalOpen(false);
    setSelectedWorkflow(null);
  };

  const isTeam = viewMode === "team";

  // ── Team-data computations ──

  const effectiveMemberCount = useMemo(() => {
    if (!selectedTeam?.members) return 0;
    return getEffectiveMemberCount(selectedTeam.members, selectedTeam.effective_member_count);
  }, [selectedTeam?.members, selectedTeam?.effective_member_count]);

  const teamMembers = useTeamMembers();

  const activeBlueprints = useMemo(() => {
    if (!activeSessions.data?.length || !workflows.data?.length) return [];
    const activeSet = new Set(activeSessions.data);
    return workflows.data
      .filter((w) => activeSet.has(w.blueprint_id))
      .map((w) => ({
        blueprint_id: w.blueprint_id,
        name: w.spec_dict?.name || w.blueprint_id,
      }));
  }, [activeSessions.data, workflows.data]);

  const leaderboard = useMemo(() => {
    const counts = blueprintSessionCounts.data;
    if (!counts || !workflows.data?.length) return [];
    const entries = Object.entries(counts)
      .map(([bid, runs]) => {
        const wf = workflows.data.find((w) => w.blueprint_id === bid);
        return { name: wf?.spec_dict?.name || bid, runs: runs as number };
      })
      .sort((a, b) => b.runs - a.runs)
      .slice(0, 8);
    const maxRuns = entries[0]?.runs || 1;
    return entries.map((e) => ({ ...e, pct: Math.round((e.runs / maxRuns) * 100) }));
  }, [blueprintSessionCounts.data, workflows.data]);

  return (
    <>
      <Header
        title={isTeam ? "Team Dashboard" : "Agentic AI Overview"}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

        {isTeam ? (
          <div className="flex h-full overflow-hidden">
            <div className="flex-1 overflow-y-auto p-6">
              {/* Summary Banner */}
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.05 }}>
                <Card className="mb-6 border-gray-800 bg-gradient-to-r from-primary/10 via-transparent to-pink-500/5 overflow-hidden">
                  <CardContent className="p-5 flex items-center gap-5">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-pink-500 flex items-center justify-center flex-shrink-0">
                      <Zap className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-bold text-white text-base">{selectedTeam?.name ?? "Team"} Overview</h3>
                      <p className="text-xs text-gray-400">
                        {effectiveMemberCount} member{effectiveMemberCount !== 1 ? "s" : ""} · {agenticStats.data?.totalWorkflows ?? 0} workflows · {agenticStats.data?.totalResources ?? 0} resources
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-3xl font-extrabold text-emerald-400 tracking-tight">{agenticStats.data?.activeSessions ?? 0}</div>
                      <div className="text-[11px] text-gray-500">active sessions</div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Stat Cards */}
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }} className="mb-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                <GlassPanel className="h-full">
                  <StatCard icon={<Share2 className="w-4 h-4" />} title={<span className="flex items-center"><FaProjectDiagram className="text-primary mr-3 h-5 w-5" />Workflows</span>} value={agenticStats.data?.totalWorkflows ?? 0} subtext="Team workflows" isLoading={agenticStats.isLoading} error={agenticStats.error} />
                </GlassPanel>
                <GlassPanel className="h-full">
                  <StatCard icon={<Users className="w-4 h-4" />} title={<span className="flex items-center"><Users className="text-blue-400 mr-3 h-5 w-5" />Team Members</span>} value={effectiveMemberCount} subtext={`In ${selectedTeam?.name ?? "team"}`} iconColor="#60a5fa" iconBgColor="rgba(96,165,250,.15)" />
                </GlassPanel>
                <GlassPanel className="h-full">
                  <StatCard icon={<Zap className="w-4 h-4" />} title={<span className="flex items-center"><Zap className="text-emerald-400 mr-3 h-5 w-5" />Active Sessions</span>} value={agenticStats.data?.activeSessions ?? 0} subtext="Currently running" isLoading={agenticStats.isLoading} error={agenticStats.error} iconColor="#34d399" iconBgColor="rgba(52,211,153,.15)" />
                </GlassPanel>
                <GlassPanel className="h-full">
                  <StatCard icon={<Database className="w-4 h-4" />} title={<span className="flex items-center"><FaBoxes className="text-amber-400 mr-3 h-5 w-5" />Resources</span>} value={agenticStats.data?.totalResources ?? 0} subtext="Total configured" isLoading={agenticStats.isLoading} error={agenticStats.error} iconColor="#fbbf24" iconBgColor="rgba(251,191,36,.15)" />
                </GlassPanel>
              </motion.div>

              {/* Active Sessions */}
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15 }} className="mb-6">
                <GlassPanel>
                  <Card className="bg-transparent border-0 shadow-none">
                    <CardHeader className="px-4 py-3 border-b border-gray-800/50">
                      <CardTitle className="text-base flex items-center gap-2">
                        <motion.div className="w-2 h-2 rounded-full bg-emerald-400" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 2, repeat: Infinity }} />
                        Active Workflow Sessions
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                      {activeBlueprints.length === 0 ? (
                        <div className="px-4 py-6 text-center text-sm text-gray-500">No active sessions right now</div>
                      ) : (
                        activeBlueprints.map((bp) => (
                          <div key={bp.blueprint_id} className="flex items-center gap-4 px-4 py-3 border-b border-gray-800/30 last:border-0 hover:bg-white/[.02] transition-colors">
                            <motion.div className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
                            <div className="flex-1 min-w-0">
                              <div className="font-semibold text-sm text-white truncate">{bp.name}</div>
                              <div className="text-xs text-gray-500">Running</div>
                            </div>
                          </div>
                        ))
                      )}
                    </CardContent>
                  </Card>
                </GlassPanel>
              </motion.div>

              {/* Workflow Usage */}
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
                <GlassPanel>
                  <Card className="bg-transparent border-0 shadow-none">
                    <CardHeader className="px-4 py-3 border-b border-gray-800/50">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base flex items-center gap-2">
                          <FaTrophy className="text-amber-400" />
                          Top Workflows by Sessions
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent className="p-0">
                      {leaderboard.length === 0 ? (
                        <div className="px-4 py-6 text-center text-sm text-gray-500">No workflow session data yet</div>
                      ) : (
                        leaderboard.map((item, i) => {
                          const RankIcon = RANK_ICONS[i] ?? CircleDot;
                          return (
                            <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-gray-800/30 last:border-0 hover:bg-white/[.02] transition-colors">
                              <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${i < 3 ? RANK_STYLES[i] : "bg-gray-800 text-gray-500"}`}>
                                {i < 3 ? <RankIcon className="w-3.5 h-3.5" /> : <span className="text-xs font-bold">{i + 1}</span>}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="font-semibold text-sm text-white">{item.name}</div>
                                <div className="text-xs text-gray-500">{item.runs} session{item.runs !== 1 ? "s" : ""}</div>
                              </div>
                              <div className="w-28 flex-shrink-0">
                                <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                  <motion.div className="h-full rounded-full bg-gradient-to-r from-primary to-pink-500" initial={{ width: 0 }} animate={{ width: `${item.pct}%` }} transition={{ duration: 0.8, delay: 0.3 + i * 0.1 }} />
                                </div>
                                <div className="text-[10px] text-gray-600 text-right mt-0.5">{item.runs} sessions</div>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </CardContent>
                  </Card>
                </GlassPanel>
              </motion.div>
            </div>

            {/* Team Members Panel */}
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.4, delay: 0.25 }} className="w-[280px] border-l border-gray-800 bg-background-card flex-col flex-shrink-0 hidden xl:flex">
              <div className="px-4 py-3 border-b border-gray-800 flex items-center gap-2">
                <Users className="w-4 h-4 text-gray-400" />
                <span className="font-semibold text-sm text-white">Team Members ({effectiveMemberCount})</span>
              </div>
              <div className="flex-1 overflow-y-auto">
                {teamMembers.map((member) => (
                  <div key={member.id} className="flex gap-2.5 px-4 py-2.5 border-b border-gray-800/40 hover:bg-white/[.02] transition-colors items-center">
                    <TeamAvatar member={member} size="xs" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-gray-200 truncate">{member.name}</p>
                    </div>
                  </div>
                ))}
                {teamMembers.length === 0 && (
                  <div className="px-4 py-6 text-center text-xs text-gray-600">No members in this team</div>
                )}
              </div>
            </motion.div>
          </div>
        ) : (
          /* ═══════ PRIVATE OVERVIEW VIEW ═══════ */
          <>
            <main className="flex-1 overflow-y-auto p-6 bg-transparent">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.1 }}
                className="mb-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6"
              >
                <GlassPanel className="h-full">
                  <StatCard
                    icon={<Workflow className="w-4 h-4" />}
                    title={<span className="flex items-center"><FaProjectDiagram className="text-primary mr-3 h-5 w-5" />Workflows</span>}
                    value={agenticStats.data?.totalWorkflows || 0}
                    subtext="Total blueprints available"
                    isLoading={agenticStats.isLoading}
                    error={agenticStats.error}
                  />
                </GlassPanel>
                <GlassPanel className="h-full">
                  <StatCard
                    icon={<Zap className="w-4 h-4" />}
                    title={<span className="flex items-center"><FaPlayCircle className="mr-3 h-5 w-5" style={{ color: themeColors.sessions }} />Active Workflows</span>}
                    value={agenticStats.data?.activeSessions || 0}
                    subtext="Currently running"
                    isLoading={activeSessions.isLoading}
                    error={activeSessions.error}
                    iconColor={themeColors.sessions}
                    iconBgColor={`${themeColors.sessions}33`}
                  />
                </GlassPanel>
                <GlassPanel className="h-full">
                  <StatCard
                    icon={<Database className="w-4 h-4" />}
                    title={<span className="flex items-center"><FaBoxes className="mr-3 h-5 w-5" style={{ color: themeColors.resources }} />Inventory</span>}
                    value={agenticStats.data?.totalResources || 0}
                    subtext="Total resources configured"
                    isLoading={resources.isLoading}
                    error={resources.error}
                    iconColor={themeColors.resources}
                    iconBgColor={`${themeColors.resources}33`}
                  />
                </GlassPanel>
                <GlassPanel className="h-full">
                  <StatCard
                    icon={<TrendingUp className="w-4 h-4" />}
                    title={<span className="flex items-center"><FaChartPie className="mr-3 h-5 w-5" style={{ color: themeColors.categories }} />Categories</span>}
                    value={agenticStats.data?.categoriesInUse || 0}
                    subtext="Categories in use"
                    isLoading={agenticStats.isLoading}
                    error={agenticStats.error}
                    iconColor={themeColors.categories}
                    iconBgColor={`${themeColors.categories}33`}
                  />
                </GlassPanel>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
                className="mb-8"
              >
                <GlassPanel style={{ height: 400 }}>
                  <Card className="shadow-card border-gray-800 h-full flex flex-col bg-transparent border-0">
                    <CardHeader className="py-4 px-6">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-xl flex items-center gap-2">
                          <FaChartPie className="text-primary" />
                          Resource Distribution
                        </CardTitle>
                        <span className="text-sm text-gray-400">By Category</span>
                      </div>
                    </CardHeader>
                    <CardContent className="px-6 pb-6 flex-1 overflow-hidden flex flex-col min-h-0">
                      <ResourceDistributionChart
                        data={resourceDistribution}
                        isLoading={agenticStats.isLoading}
                        primaryColor={primaryHex || "#A60000"}
                      />
                    </CardContent>
                  </Card>
                </GlassPanel>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.3 }}
                className="mb-8 grid grid-cols-1 xl:grid-cols-2 gap-6"
              >
                <GlassPanel style={{ height: 340 }}>
                  <WorkflowList
                    title="Most Used Workflows"
                    workflows={mostUsedWorkflows}
                    isLoading={workflows.isLoading || activeSessions.isLoading || blueprintSessionCounts.isLoading}
                    onWorkflowClick={handleWorkflowClick}
                    emptyMessage="No workflows currently in use"
                    showUsageCount={true}
                  />
                </GlassPanel>
                <GlassPanel style={{ height: 340 }}>
                  <WorkflowList
                    title="Unused Available Workflows"
                    workflows={unusedWorkflows}
                    isLoading={workflows.isLoading || activeSessions.isLoading || blueprintSessionCounts.isLoading}
                    onWorkflowClick={handleWorkflowClick}
                    emptyMessage={
                      workflows.data.length === 0
                        ? "No workflows available"
                        : "All workflows are currently in use"
                    }
                    maxItems={8}
                    countBadge={unusedWorkflows.length}
                  />
                </GlassPanel>
              </motion.div>
            </main>
            <StatusBar />
          </>
        )}

      <Dialog open={isWorkflowModalOpen} onOpenChange={handleCloseModal}>
        <DialogContent className="bg-background-card border-gray-800 max-w-6xl w-[90vw] h-[85vh] flex flex-col p-0 overflow-hidden">
          <DialogHeader className="px-6 py-4 border-b border-gray-800 flex-shrink-0">
            <DialogTitle className="text-xl flex items-center gap-2">
              <FaProjectDiagram className="text-primary" />
              {selectedWorkflow?.spec_dict?.name || selectedWorkflow?.blueprint_id || "Workflow View"}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-hidden p-6 min-h-0">
            {selectedWorkflow && (
              <div className="h-full w-full">
                <GraphDisplay
                  blueprintId={selectedWorkflow.blueprint_id}
                  specDict={selectedWorkflow.spec_dict}
                  height="100%"
                  showBackground={true}
                  interactive={true}
                  centerInView={true}
                  animated={true}
                />
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
