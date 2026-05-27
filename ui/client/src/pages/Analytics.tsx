import { useState, useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { fetchSystemWideStats } from "@/api/systemStats";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import GlassPanel from "@/components/ui/GlassPanel";
import { StatCard } from "@/components/ui/stat-card";
import { 
  FaUsers, FaRocket, FaCheckCircle, FaSync, FaCubes, FaChartLine
} from "react-icons/fa";
import type { ReactNode } from "react";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import { AccessDenied } from "@/components/shared/AccessDenied";
import { LoadingSkeleton } from "@/components/analytics/LoadingSkeleton";
import { ErrorDisplay } from "@/components/shared/ErrorDisplay";
import { StatusBreakdownChart } from "@/components/analytics/StatusBreakdownChart";
import { TopUsersChart } from "@/components/analytics/TopUsersChart";
import { WorkflowExecutionChart } from "@/components/analytics/WorkflowExecutionChart";
import { ActiveTodayTable } from "@/components/analytics/ActiveTodayTable";
import { AllUsersTable } from "@/components/analytics/AllUsersTable";
import { TopBlueprintsQuickView } from "@/components/analytics/TopBlueprintsQuickView";
import { BlueprintsTable } from "@/components/analytics/BlueprintsTable";
import { truncateUserId } from "@/components/analytics/analyticsHelpers";
import { getWorkflowStatusColors } from "@/components/agentic-ai/chat/WorkPlanDisplayHelpers";
import type { TimeRange, UserActivity } from "@/types/systemStats";

export default function Analytics() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [timeRange, setTimeRange] = useState<TimeRange>('today');
  const [activeTodayPage, setActiveTodayPage] = useState(0);
  const [allUsersPage, setAllUsersPage] = useState(0);
  const itemsPerPage = 10;
  const { primaryHex } = useTheme();
  const { user } = useAuth();

  const hasAccess = user?.is_admin || false;

  // Fetch system-wide stats data
  const { data: analytics, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['systemStats', timeRange],
    queryFn: () => fetchSystemWideStats(timeRange),
    staleTime: 60000,
    gcTime: 300000,
    refetchInterval: 30000,
    refetchOnWindowFocus: true,
    enabled: hasAccess,
  });

  useEffect(() => {
    if (analytics) setLastUpdated(new Date());
  }, [analytics]);

  // Reset pagination when time range changes
  useEffect(() => {
    setActiveTodayPage(0);
    setAllUsersPage(0);
  }, [timeRange]);

  // Color configuration
  const colors = {
    primary: primaryHex || "#8B5CF6",
    success: "#10B981",
    warning: "#F59E0B",
    error: "#EF4444",
    info: "#3B82F6",
    gray: "#6B7280",
  };

  // Use WorkPlanDisplayHelpers color scheme for workflow statuses
  const statusColors = getWorkflowStatusColors();

  // Backend returns data already scoped to the selected time range
  const completedRuns = analytics?.status_breakdown?.COMPLETED || 0;
  const totalRuns = analytics?.total_stats?.total_runs || 0;
  const successRate = totalRuns > 0 ? (completedRuns / totalRuns) * 100 : 0;

  // Prepare chart data
  const statusData = analytics?.status_breakdown 
    ? Object.entries(analytics.status_breakdown).map(([status, count]) => ({
        name: status,
        value: typeof count === 'number' ? count : 0,
        color: statusColors[status] || colors.gray
      }))
    : [];

  const topUsersData = analytics?.active_users?.slice(0, 8).map((u: UserActivity) => ({
    name: truncateUserId(u.display_name || u.identity_id, 12),
    fullName: u.display_name || u.identity_id,
    runs: u.run_count,
    blueprints: u.blueprints_used,
    completed: u.status_breakdown?.COMPLETED || 0,
    failed: u.status_breakdown?.FAILED || 0,
  })) || [];

  // Stat card configuration for the overview section
  interface StatCardConfig {
    key: string;
    icon: ReactNode;
    title: string;
    value: string | number;
    subtext: string;
    iconColor: string;
    iconBgColor: string;
  }

  const statCards: StatCardConfig[] = [
    {
      key: 'total-runs',
      icon: <FaRocket className="w-4 h-4" />,
      title: 'Total Runs',
      value: analytics?.total_stats?.total_runs || 0,
      subtext: timeRange === 'all' ? 'All workflow executions' : 'In selected period',
      iconColor: colors.primary,
      iconBgColor: `${colors.primary}33`,
    },
    {
      key: 'total-users',
      icon: <FaUsers className="w-4 h-4" />,
      title: 'Total Users',
      value: analytics?.total_stats?.unique_users || 0,
      subtext: timeRange === 'all' ? 'Unique users' : 'Active users',
      iconColor: colors.info,
      iconBgColor: `${colors.info}33`,
    },
    {
      key: 'success-rate',
      icon: <FaCheckCircle className="w-4 h-4" />,
      title: 'Success Rate',
      value: `${successRate.toFixed(1)}%`,
      subtext: '↑ Completed runs',
      iconColor: colors.success,
      iconBgColor: `${colors.success}33`,
    },
    {
      key: 'workflows-in-use',
      icon: <FaCubes className="w-4 h-4" />,
      title: 'Workflows in Use',
      value: analytics?.total_stats?.blueprints_used || 0,
      subtext: 'Distinct blueprints executed',
      iconColor: colors.warning,
      iconBgColor: `${colors.warning}33`,
    },
  ];

  // Determine error details for display
  const axiosError = error as any;
  const errorStatusCode = axiosError?.response?.status;
  const errorMessage = axiosError?.message || 'Unknown error';
  const isAccessDeniedError = errorStatusCode === 403;

  // Render page content based on state
  const renderContent = () => {
    if (!hasAccess) {
      return (
        <main className="flex-1 overflow-y-auto bg-background-dark">
          <AccessDenied />
        </main>
      );
    }

    if (isLoading) {
      return <LoadingSkeleton />;
    }

    if (error) {
      return (
        <main className="flex-1 overflow-y-auto bg-background-dark">
          {isAccessDeniedError
            ? <AccessDenied />
            : <ErrorDisplay errorMessage={errorMessage} title="Failed to Load Analytics" onRetry={refetch} />}
        </main>
      );
    }

    return (
      <main className="flex-1 overflow-y-auto bg-background-dark p-6">
        {/* Header with Actions */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-heading font-bold">Workflow Analytics</h2>
            <p className="text-sm text-gray-400 mt-1">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </p>
          </div>
          <div className="flex gap-2">
            <Button 
              onClick={() => refetch()} 
              variant="outline"
              size="sm"
              disabled={isFetching}
              className="gap-2 border-gray-700 hover:bg-gray-800"
            >
              <FaSync className={isFetching ? "animate-spin" : ""} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Time Range Filter */}
        <div className="flex gap-2 mb-6">
          {[
            { value: 'today' as TimeRange, label: 'Today' },
            { value: '7days' as TimeRange, label: 'Last 7 Days' },
            { value: '30days' as TimeRange, label: 'Last 30 Days' },
            { value: 'all' as TimeRange, label: 'All Time' }
          ].map((range) => (
            <Button
              key={range.value}
              variant={timeRange === range.value ? 'default' : 'outline'}
              size="sm"
              onClick={() => setTimeRange(range.value)}
              className={timeRange === range.value ? 'bg-primary' : 'border-gray-700 hover:bg-gray-800'}
            >
              {range.label}
            </Button>
          ))}
        </div>

        {/* Overview Stats Cards */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6"
        >
          {statCards.map((card) => (
            <GlassPanel key={card.key} className="h-full">
              <StatCard
                icon={card.icon}
                title={card.title}
                value={card.value}
                subtext={card.subtext}
                isLoading={isLoading}
                error={error}
                iconColor={card.iconColor}
                iconBgColor={card.iconBgColor}
              />
            </GlassPanel>
          ))}
        </motion.div>

        {/* Tabs Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <Tabs defaultValue="overview" className="w-full">
            <TabsList className="mb-6 bg-background-card border border-gray-800">
              <TabsTrigger value="overview" className="data-[state=active]:bg-primary data-[state=active]:text-white">
                <FaChartLine className="mr-2" />
                Overview
              </TabsTrigger>
              <TabsTrigger value="users" className="data-[state=active]:bg-primary data-[state=active]:text-white">
                <FaUsers className="mr-2" />
                Users
              </TabsTrigger>
              <TabsTrigger value="blueprints" className="data-[state=active]:bg-primary data-[state=active]:text-white">
                <FaRocket className="mr-2" />
                Blueprints
              </TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="overview">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Status Breakdown */}
                <StatusBreakdownChart statusData={statusData} totalRuns={totalRuns} />

                {/* Top Active Users */}
                <TopUsersChart topUsersData={topUsersData} colors={colors} />

                {/* Top Blueprints Quick View */}
                <TopBlueprintsQuickView 
                  blueprints={analytics?.top_blueprints?.slice(0, 5) || []}
                  totalBlueprints={analytics?.top_blueprints?.length || 0}
                  colors={colors}
                />

                {/* Workflow Execution Chart */}
                <WorkflowExecutionChart 
                  timeSeriesData={analytics?.time_series || []} 
                  timeRange={timeRange}
                  colors={colors}
                />
              </div>
            </TabsContent>

            {/* Users Tab */}
            <TabsContent value="users">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <ActiveTodayTable 
                  users={analytics?.active_users || []}
                  page={activeTodayPage}
                  setPage={setActiveTodayPage}
                  itemsPerPage={itemsPerPage}
                  timeRange={timeRange}
                />
                <AllUsersTable 
                  users={analytics?.active_users || []}
                  page={allUsersPage}
                  setPage={setAllUsersPage}
                  itemsPerPage={itemsPerPage}
                />
              </div>
            </TabsContent>

            {/* Blueprints Tab */}
            <TabsContent value="blueprints">
              <BlueprintsTable blueprints={analytics?.top_blueprints || []} colors={colors} />
            </TabsContent>
          </Tabs>
        </motion.div>

        {/* Footer */}
        <div className="mt-6 text-center text-xs text-gray-500">
          Data generated at: {analytics?.generated_at ? new Date(analytics.generated_at).toLocaleString() : 'N/A'} • Auto-refreshes every 30 seconds
        </div>
      </main>
    );
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Workflow Analytics" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        {renderContent()}
        <StatusBar />
      </div>
    </div>
  );
}
