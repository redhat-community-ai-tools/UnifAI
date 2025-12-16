import { useState, useMemo } from "react";
import { FaProjectDiagram, FaChartPie, FaPlayCircle, FaBoxes } from "react-icons/fa";
import { motion } from "framer-motion";
import { getPaletteColor } from "@/lib/colorUtils";

// Layout components
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";

// Agentic Overview components
import GlassPanel from "@/components/ui/GlassPanel";
import { StatCard } from "@/components/ui/stat-card";
import { ResourceDistributionChart } from "@/components/ui/resource-distribution-chart";
import { WorkflowList } from "@/components/dashboard/WorkflowList";
import { WorkflowBlueprint } from "@/api/agentic";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTheme } from "@/contexts/ThemeContext";
import { Workflow, Database, Zap, TrendingUp } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import ReactFlowGraph from "@/components/agentic-ai/graphs/ReactFlowGraph";
import { ReactFlowProvider } from "reactflow";

// Custom hooks
import { useAgenticData } from "@/hooks/use-agentic-data";
import { useWorkflowCalculations } from "@/hooks/use-workflow-calculations";
import { useResourceDistribution } from "@/hooks/use-resource-distribution";

export default function AgenticOverview() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowBlueprint | null>(null);
  const [isWorkflowModalOpen, setIsWorkflowModalOpen] = useState(false);
  const { primaryHex } = useTheme();

  // Fetch all agentic data using custom hook
  const {
    agenticStats,
    workflows,
    activeSessions,
    blueprintSessionCounts,
    resources,
    resourceCategories,
  } = useAgenticData();

  // Calculate theme colors once using useMemo
  const themeColors = useMemo(() => {
    const primary = primaryHex || "#A60000";
    return {
      sessions: getPaletteColor(primary, 1, 4),
      resources: getPaletteColor(primary, 2, 4),
      categories: getPaletteColor(primary, 3, 4),
    };
  }, [primaryHex]);

  // Calculate resource distribution using custom hook
  const resourceDistribution = useResourceDistribution(
    resourceCategories.data,
    agenticStats.data?.resourcesByCategory || []
  );

  // Calculate workflow statistics using custom hook
  const { mostUsedWorkflows, unusedWorkflows } = useWorkflowCalculations(
    workflows.data,
    activeSessions.data,
    blueprintSessionCounts.data
  );

  // Handle workflow click
  const handleWorkflowClick = (workflow: WorkflowBlueprint) => {
    setSelectedWorkflow(workflow);
    setIsWorkflowModalOpen(true);
  };

  // Handle modal close
  const handleCloseModal = () => {
    setIsWorkflowModalOpen(false);
    setSelectedWorkflow(null);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <Header title="Agentic AI Overview" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        
        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-6 bg-transparent">
          {/* Top row: Key Metrics */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mb-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6"
          >
            {/* Total Workflows */}
            <GlassPanel className="h-full">
              <StatCard
                icon={<Workflow className="w-4 h-4" />}
                title={
                  <span className="flex items-center">
                    <FaProjectDiagram className="text-primary mr-3 h-5 w-5" />
                    Workflows
                  </span>
                }
                value={agenticStats.data?.totalWorkflows || 0}
                subtext="Total blueprints available"
                isLoading={agenticStats.isLoading}
                error={agenticStats.error}
              />
            </GlassPanel>

            {/* Active Sessions */}
            <GlassPanel className="h-full">
              <StatCard
                icon={<Zap className="w-4 h-4" />}
                title={
                  <span className="flex items-center">
                    <FaPlayCircle className="mr-3 h-5 w-5" style={{ color: themeColors.sessions }} />
                    Active Workflows
                  </span>
                }
                value={agenticStats.data?.activeSessions || 0}
                subtext="Currently running"
                isLoading={activeSessions.isLoading}
                error={activeSessions.error}
                iconColor={themeColors.sessions}
                iconBgColor={`${themeColors.sessions}33`}
              />
            </GlassPanel>

            {/* Total Resources */}
            <GlassPanel className="h-full">
              <StatCard
                icon={<Database className="w-4 h-4" />}
                title={
                  <span className="flex items-center">
                    <FaBoxes className="mr-3 h-5 w-5" style={{ color: themeColors.resources }} />
                    Inventory
                  </span>
                }
                value={agenticStats.data?.totalResources || 0}
                subtext="Total resources configured"
                isLoading={resources.isLoading}
                error={resources.error}
                iconColor={themeColors.resources}
                iconBgColor={`${themeColors.resources}33`}
              />
            </GlassPanel>

            {/* Resource Categories */}
            <GlassPanel className="h-full">
              <StatCard
                icon={<TrendingUp className="w-4 h-4" />}
                title={
                  <span className="flex items-center">
                    <FaChartPie className="mr-3 h-5 w-5" style={{ color: themeColors.categories }} />
                    Categories
                  </span>
                }
                value={agenticStats.data?.categoriesInUse || 0}
                subtext="Categories in use"
                isLoading={agenticStats.isLoading}
                error={agenticStats.error}
                iconColor={themeColors.categories}
                iconBgColor={`${themeColors.categories}33`}
              />
            </GlassPanel>
          </motion.div>

          {/* Middle row: Resource Distribution */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mb-8"
          >
            {/* Resource Distribution Chart */}
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

          {/* Bottom row: Most Used Workflows and Unused Available Workflows */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mb-8 grid grid-cols-1 xl:grid-cols-2 gap-6"
          >
            {/* Most Used Workflows */}
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

            {/* Unused Available Workflows */}
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
      </div>

      {/* Workflow View Modal */}
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
              <ReactFlowProvider>
                <div className="h-full w-full">
                  <ReactFlowGraph
                    blueprintId={selectedWorkflow.blueprint_id}
                    height="100%"
                    showControls={true}
                    showMiniMap={true}
                    showBackground={true}
                    interactive={false}
                    isLiveRequest={false}
                  />
                </div>
              </ReactFlowProvider>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

