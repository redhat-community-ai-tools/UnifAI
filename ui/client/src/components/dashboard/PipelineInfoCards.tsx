import { Card, CardContent } from "@/components/ui/card";
import { motion } from "framer-motion";
import { Activity, Database, TrendingUp, FileText, MessageSquare, Bug, Slack as SlackIcon, Clock, Menu, PieChart, Plug } from "lucide-react";
import type { PipelineMetrics, ActivePipeline } from "@/api/pipelines";
import { useQuery } from "@tanstack/react-query";
import { fetchQdrantChunksCounts, fetchConnectedSources } from "@/api/pipelines";
import { useTheme } from "@/contexts/ThemeContext";

interface PipelineInfoCardsProps {
  metrics?: PipelineMetrics;
  activePipelines?: ActivePipeline[];
  showProcessing?: boolean;
  showConnected?: boolean;
  showActive?: boolean;
  showLastSync?: boolean;
}

export function PipelineInfoCards({ metrics, activePipelines = [], showProcessing = true, showConnected = true, showActive = true, showLastSync = false }: PipelineInfoCardsProps) {
  const ProcessingStatsCard = () => (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
      <Card className="rounded-xl border-0">
        <div className="relative p-4 border-b border-border">
          <div className="absolute top-2 right-4 w-8 h-8 rounded-lg bg-primary text-white flex items-center justify-center shadow-lg/30 shadow-primary/40">
            <Menu className="w-4 h-4" />
          </div>
          <h3 className="text-lg font-semibold text-white flex items-center">
            <TrendingUp className="text-primary mr-3 h-5 w-5" />
            Processing Stats
          </h3>
        </div>
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Success Rate</p>
              <p className="text-xl font-bold" style={{ color: 'hsl(var(--success))' }}>{(metrics?.successRate ?? 0).toFixed(1)}%</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Active Pipelines</p>
              <p className="text-xl font-bold text-white">{metrics?.activePipelines || 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Total Pipelines</p>
              <p className="text-xl font-bold text-white">{metrics?.totalPipelines || 0}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );

  const ConnectedSourcesCard = () => {
    const sourceTypes = ["slack", "document"] as const;
    const getSourceIcon = (type: string) => {
      switch (type) {
        case "slack":
          return <MessageSquare className="h-4 w-4" />;
        case "document":
          return <FileText className="h-4 w-4" />;
        default:
          return <Database className="h-4 w-4" />;
      }
    };
    const { primaryHex } = useTheme();
    const slackColor = primaryHex || "#A60000";

    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
        <Card className="rounded-xl border-0">
          <div className="relative px-4 pt-3 pb-2 border-b border-border">
            <div className="absolute top-2 right-4 w-8 h-8 rounded-lg bg-gray-800/70 text-white flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </div>
            <h3 className="text-lg font-semibold text-white flex items-center">
              <Database className="text-primary mr-3 h-5 w-5" />
              Connected Sources
            </h3>
          </div>
          <CardContent className="p-0">
            <div className="divide-y divide-gray-800/80">
              {sourceTypes.map((type) => {
                const count = activePipelines.filter((p) => p.source_type === (type as any) || (p as any).type === type).length;
                const isActive = count > 0;
                const leftColor = type === 'slack' ? slackColor : 'hsl(var(--secondary))';
                return (
                  <div
                    key={type}
                    className="flex items-center justify-between px-4 py-4 hover:bg-gray-900/40 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="relative inline-flex items-center justify-center">
                        <span className="absolute inline-flex h-5 w-5 rounded-full opacity-30" style={{ backgroundColor: leftColor }}></span>
                        <span className="relative inline-flex h-3.5 w-3.5 rounded-full" style={{ backgroundColor: leftColor }}></span>
                      </span>
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-white font-medium text-sm sm:text-base capitalize truncate">{type}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs sm:text-sm text-gray-400">{count} active</span>
                      <span className={`h-2 w-2 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-600'}`}></span>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </motion.div>
    );
  };

  const LastSyncCard = () => {
    // Repurposed as Embedded Sources compact chart
    const { data: sources } = useQuery({
      queryKey: ["embeddedSourcesCounts"],
      queryFn: fetchConnectedSources,
      refetchInterval: 30000,
      refetchOnWindowFocus: true,
    });
    const { primaryHex } = useTheme();
    const slackColor = primaryHex || "#A60000";
    const slack = sources?.byType?.slack ?? 0;
    const docs = sources?.byType?.document ?? 0;
    const total = Math.max(slack + docs, 1);
    const slackPct = Math.round((slack / total) * 100);
    const docsPct = Math.round((docs / total) * 100);


    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.25 }} className="h-full">
        <Card className="rounded-xl border-0 h-full min-h-[200px]">
          <div className="relative p-4 border-b border-border">
            <div className="absolute top-2 right-4 w-8 h-8 rounded-lg bg-gray-800 text-white flex items-center justify-center shadow-lg/20">
              <Plug className="w-4 h-4" />
            </div>
            <h3 className="text-lg font-semibold text-white flex items-center">
              <Clock className="text-primary mr-3 h-5 w-5" />
              Embedded Sources
            </h3>
          </div>
          <CardContent className="p-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span>Slack</span>
                <span className="text-white font-medium">{slack} ({slackPct}%)</span>
              </div>
              <div className="w-full h-2 bg-gray-800 rounded">
                <div className="h-2 rounded" style={{ width: `${slackPct}%`, backgroundColor: slackColor }}></div>
              </div>
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span>Documents</span>
                <span className="text-white font-medium">{docs} ({docsPct}%)</span>
              </div>
              <div className="w-full h-2 bg-gray-800 rounded">
                <div className="h-2 rounded" style={{ width: `${docsPct}%`, backgroundColor: 'hsl(var(--secondary))' }}></div>
              </div>
              <div className="mt-1 text-xs text-gray-500">Total: {total} • Auto-updates every 30s</div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    );
  };

  const ActivePipelinesCard = () => {
    const activeCount = activePipelines.filter(
      (p) => p.status === "PROCESSING" || p.status === "COLLECTING" || p.status === "CHUNKING_AND_EMBEDDING"
    ).length;

    const getStatusBadge = (status: string) => {
      switch (status) {
        case 'Done':
        case 'complete':
          return { color: 'badge-slack-green', label: status === 'Done' ? 'Success' : 'Complete' };
        case 'PROCESSING':
        case 'COLLECTING':
        case 'CHUNKING_AND_EMBEDDING':
          return { color: 'badge-slack-blue', label: 'Processing' };
        case 'FAILED':
        case 'error':
          return { color: 'badge-slack-red', label: 'Error' };
        default:
          return { color: 'badge-slack-purple', label: status };
      }
    };

    const getActivityIcon = (type: string) => {
      switch (type) {
        case 'slack':
          return <SlackIcon className="text-white text-sm" />;
        case 'document':
          return <FileText className="text-white text-sm" />;
        default:
          return <MessageSquare className="text-white text-sm" />;
      }
    };

    const { primaryHex } = useTheme();
    const getActivityColor = (type: string) => {
      if (type === 'slack') {
        return primaryHex || '#A60000';
      }
      if (type === 'document') {
        return 'hsl(var(--secondary))';
      }
      return '#4B5563';
    };

    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.3 }}>
        <Card className="rounded-xl border-0">
          <div className="p-4 border-b border-border">
            <h3 className="text-lg font-semibold text-white flex items-center">
              <Activity className="text-primary mr-3 h-5 w-5" />
              Active Pipelines
              <div className="ml-2 flex items-center">
                <div className="w-2 h-2 bg-secondary rounded-full animate-pulse mr-1"></div>
                <span className="text-secondary text-xs font-medium">{activeCount}</span>
              </div>
            </h3>
          </div>
          <CardContent className="p-4">
            {activePipelines.length === 0 ? (
              <div className="text-center text-gray-400 py-4">No active pipelines</div>
            ) : (
              <div className="divide-y divide-gray-800/80 max-h-80 overflow-y-auto overflow-x-hidden">
                {activePipelines.map((pipeline) => {
                  const statusBadge = getStatusBadge(pipeline.status);
                  const borderColor = pipeline.status === 'FAILED' ? 'border-red-900' : 'border-gray-700';
                  return (
                    <motion.div
                      key={pipeline.id}
                      initial={{ opacity: 0, y: 12, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -12, scale: 0.98 }}
                      transition={{ type: "spring", stiffness: 380, damping: 26, mass: 0.8 }}
                      className={`w-full min-w-0 h-full p-4 flex flex-col justify-between`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-9 h-9 rounded-full flex items-center justify-center`} style={{ backgroundColor: getActivityColor(pipeline.source_type) }}>
                            {getActivityIcon(pipeline.source_type)}
                          </div>
                          <span className="text-white font-semibold text-base break-words" title={pipeline.source_name}>
                            {pipeline.source_name}
                          </span>
                        </div>
                        <span className="text-gray-400 text-sm ml-3 whitespace-nowrap">
                          {(pipeline.pipeline_stats?.documents_retrieved || 0)} docs
                        </span>
                      </div>
                      <div className="flex items-center mt-3 gap-2">
                        <span className={`px-2.5 py-1 ${statusBadge.color} text-sm rounded`}>
                          {statusBadge.label}
                        </span>
                        <span className="px-2.5 py-1 bg-gray-800 text-gray-300 text-sm rounded capitalize">
                          {pipeline.source_type}
                        </span>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    );
  };

  return (
    <div className="space-y-6">
      {showProcessing && <ProcessingStatsCard />}
      {showConnected && <ConnectedSourcesCard />}
      {showLastSync && <LastSyncCard />}
      {showActive && <ActivePipelinesCard />}
    </div>
  );
}


