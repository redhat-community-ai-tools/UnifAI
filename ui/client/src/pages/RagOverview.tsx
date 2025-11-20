import { useState } from "react";
import { FaStream, FaPlug, FaChartPie, FaProjectDiagram, FaRobot, FaDatabase, FaChevronRight } from "react-icons/fa";
import { useProject } from "@/contexts/ProjectContext";
import { motion } from "framer-motion";

// Layout components
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";

// Dashboard components
import StatusCard from "@/components/dashboard/StatusCard";
import { PipelineVisualizerWrapper } from "@/components/dashboard/PipelineVisualizerWrapper";
import ProjectCard from "@/components/dashboard/ProjectCard";
import { LiveActivityFeed } from "@/components/dashboard/LiveActivityFeed";
import DataSourceStats from "@/components/dashboard/DataSourceStats";
import { PipelineInfoCards } from "@/components/dashboard/PipelineInfoCards";
import GlassPanel from "@/components/ui/GlassPanel";
import { useQuery } from "@tanstack/react-query";
import { fetchActivePipelines, fetchPipelineMetrics, fetchConnectedSources, fetchQdrantChunksCounts } from "@/api/pipelines";
import { PIPELINE_STATUS } from "@/constants/pipelineStatus";
import { PieChart, Pie, Cell } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { Separator } from "@/components/ui/separator";
import { useTheme } from "@/contexts/ThemeContext";

export default function RagOverview() {
  const { projects } = useProject();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { primaryHex } = useTheme();
  const slackFill = primaryHex || "#A60000";

  // Live metrics for summary cards
  const { data: metrics } = useQuery({
    queryKey: ['pipelineMetricsSummary'],
    queryFn: fetchPipelineMetrics,
    refetchInterval: 10000,
    refetchOnWindowFocus: true,
  });

  const { data: connectedSources } = useQuery({
    queryKey: ['connectedSourcesSummary'],
    queryFn: fetchConnectedSources,
    refetchInterval: 30000,
    refetchOnWindowFocus: true,
  });

  const slackCount = connectedSources?.byType?.slack ?? 0;
  const documentCount = connectedSources?.byType?.document ?? 0;
  const totalSources = slackCount + documentCount;

  const { data: activePipelines = [] } = useQuery({
    queryKey: ['activePipelinesListSummary'],
    queryFn: fetchActivePipelines,
    refetchInterval: 10000,
    refetchOnWindowFocus: true,
  });

  const processingCount = activePipelines.filter(p => [
    PIPELINE_STATUS.COLLECTING,
    PIPELINE_STATUS.PROCESSING,
    PIPELINE_STATUS.CHUNKING_AND_EMBEDDING,
    PIPELINE_STATUS.STORING,
    PIPELINE_STATUS.ORCHESTRATING,
  ].includes(p.status as any)).length;

  const waitingCount = activePipelines.filter(p => p.status === PIPELINE_STATUS.PENDING || p.status === PIPELINE_STATUS.ACTIVE).length;
  const pausedCount = activePipelines.filter(p => p.status === PIPELINE_STATUS.PAUSED).length;

  const totalDocs = activePipelines.reduce((sum, p) => sum + (p.pipeline_stats?.documents_retrieved || 0), 0);
  const totalEmbeddings = activePipelines.reduce((sum, p) => sum + (p.pipeline_stats?.embeddings_created || 0), 0);
  const totalProcessingTime = activePipelines.reduce((sum, p) => sum + (p.pipeline_stats?.processing_time || 0), 0);
  const docsPerMin = totalProcessingTime > 0 ? Math.round((totalDocs / totalProcessingTime) * 60) : 0;
  
  // Qdrant chunks counts for the middle-right card
  const { data: chunkCounts } = useQuery({
    queryKey: ['qdrantChunksCountsDashboard'],
    queryFn: fetchQdrantChunksCounts,
    refetchInterval: 30000,
    refetchOnWindowFocus: true,
  });
  const qSlack = chunkCounts?.slack ?? 0;
  const qDocs = chunkCounts?.document ?? 0;
  const qTotal = Math.max(qSlack + qDocs, 1);
  const qSlackPct = Math.round((qSlack / qTotal) * 100);
  const qDocsPct = Math.round((qDocs / qTotal) * 100);
  const size = 280; const center = size / 2; const outerRadius = 98; const innerRadius = 76; const stroke = 16;
  const outerCirc = 2 * Math.PI * outerRadius; const innerCirc = 2 * Math.PI * innerRadius;
  const outerDash = `${(qDocsPct / 100) * outerCirc} ${outerCirc}`; const innerDash = `${(qSlackPct / 100) * innerCirc} ${innerCirc}`;

  // Data source stats
  const dataSourceStats = {
    totalVectors: '26.7K',
    stats: [
      { source: 'Jira Issues', color: 'primary', count: '12.3K', percentage: 45 },
      { source: 'Slack Messages', color: 'secondary', count: '8.2K', percentage: 30 },
      { source: 'Documents', color: 'accent', count: '6.7K', percentage: 25 }
    ]
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <Header title="Overview Dashboard" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        
        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-6 bg-transparent">
          {/* Top row: Processing Stats and Embedded Sources side-by-side */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mb-6 grid grid-cols-1 xl:grid-cols-3 gap-6"
          >
            <GlassPanel className="h-full">
              <PipelineInfoCards metrics={metrics} activePipelines={activePipelines} showProcessing showConnected={false} showActive={false} />
            </GlassPanel>
            <GlassPanel className="h-full">
              <PipelineInfoCards metrics={metrics} activePipelines={activePipelines} showProcessing={false} showConnected showActive={false} />
            </GlassPanel>
            <GlassPanel className="h-full">
              <PipelineInfoCards metrics={metrics} activePipelines={activePipelines} showProcessing={false} showConnected={false} showActive={false} showLastSync />
            </GlassPanel>
          </motion.div>

          {/* Middle row: Pipeline tracker left, Connected Sources right (same line) */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mb-8 grid grid-cols-1 xl:grid-cols-3 gap-6"
          >
            <GlassPanel strong className="xl:col-span-2">
              <PipelineVisualizerWrapper />
            </GlassPanel>
            <GlassPanel className="xl:col-span-1" style={{ height: 500 }}>
              <Card className=" shadow-card border-gray-800 h-full flex flex-col">
                <CardHeader className="py-4 px-6">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-xl flex items-center gap-2">
                      <FaChartPie className="text-primary" />
                      Total Chunks (Approx)
                    </CardTitle>
                    <span className="text-sm text-gray-400">Slack vs Documents</span>
                  </div>
                </CardHeader>
                <CardContent className="px-6 pb-6 flex-1 flex flex-col justify-between min-h-0">
                  <div className="flex items-center gap-10 justify-center h-[400px]">
                    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
                      <g transform={`rotate(-90 ${center} ${center})`}>
                        <circle cx={center} cy={center} r={outerRadius} fill="none" stroke="#2F2F2F" strokeWidth={stroke} />
                        <circle cx={center} cy={center} r={outerRadius} fill="none" stroke="hsl(var(--secondary))" strokeWidth={stroke} strokeLinecap="round" strokeDasharray={outerDash} />
                        <circle cx={center} cy={center} r={innerRadius} fill="none" stroke="#2F2F2F" strokeWidth={stroke} />
                        <circle cx={center} cy={center} r={innerRadius} fill="none" stroke={slackFill} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={innerDash} />
                      </g>
                      <g>
                        <text x={center} y={center - 6} textAnchor="middle" className="fill-gray-300" style={{ fontSize: 26, fontWeight: 800 }}>{qDocs}</text>
                        <text x={center} y={center + 24} textAnchor="middle" className="fill-gray-300" style={{ fontSize: 22, fontWeight: 800 }}>{qSlack}</text>
                      </g>
                    </svg>
                    <div className="space-y-4">
                      <div>
                        <div className="text-3xl font-bold" style={{ color: 'hsl(var(--secondary))' }}>{qDocsPct}%</div>
                        <div className="text-sm text-gray-400">Documents</div>
                      </div>
                      <div>
                        <div className="text-3xl font-bold" style={{ color: slackFill }}>{qSlackPct}%</div>
                        <div className="text-sm text-gray-400">Slack</div>
                      </div>
                      <div className="pt-1 text-sm text-gray-400">Total: {qSlack + qDocs}</div>
                      <div className="text-sm text-gray-500">Auto-updates every 30s</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </GlassPanel>
          </motion.div>

          {/* Bottom row: Recent Activity (3/4) and Active Pipelines (1/4) */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mb-8 grid grid-cols-1 xl:grid-cols-12 gap-6"
          >
            <GlassPanel className="xl:col-span-5" style={{ height: 340 }}>
              <PipelineInfoCards metrics={metrics} activePipelines={activePipelines} showProcessing={false} showConnected={false} showActive />
            </GlassPanel>
            <GlassPanel className="xl:col-span-7" style={{ height: 340 }}>
              <LiveActivityFeed compact />
            </GlassPanel>
          </motion.div>
        </main>
            <StatusBar />
      </div>
    </div>
  );
}
