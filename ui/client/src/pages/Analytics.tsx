import { useState, useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { fetchAnalyticsOverview } from "@/api/analytics";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  FaUsers, FaRocket, FaChartLine, FaCheckCircle, 
  FaClock, FaFire, FaSync, FaDownload
} from "react-icons/fa";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from "recharts";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import { AccessDenied } from "@/components/analytics/AccessDenied";
import { LoadingSkeleton } from "@/components/analytics/LoadingSkeleton";
import { ErrorDisplay } from "@/components/analytics/ErrorDisplay";
import { ActivityPeriodRow } from "@/components/analytics/ActivityPeriodRow";
import { filterAnalyticsByTimeRange, truncateUserId } from "@/utils/analyticsHelpers";

type TimeRange = 'today' | '7days' | '30days' | 'all';

export default function Analytics() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [timeRange, setTimeRange] = useState<TimeRange>('all');
  const [activeTodayPage, setActiveTodayPage] = useState(0);
  const [allUsersPage, setAllUsersPage] = useState(0);
  const itemsPerPage = 10;
  const { primaryHex } = useTheme();
  const { user } = useAuth();

  const hasAccess = user?.can_access_analytics || false;

  // Fetch analytics data
  const { data: analytics, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['analyticsOverview'],
    queryFn: fetchAnalyticsOverview,
    staleTime: 60000,
    gcTime: 300000,
    refetchInterval: 60000,
    refetchOnWindowFocus: false,
    enabled: hasAccess,
  });

  useEffect(() => {
    if (analytics) setLastUpdated(new Date());
  }, [analytics]);

  // Color configuration
  const colors = {
    primary: primaryHex || "#8B5CF6",
    success: "#10B981",
    warning: "#F59E0B",
    error: "#EF4444",
    info: "#3B82F6",
    gray: "#6B7280",
  };

  const statusColors: Record<string, string> = {
    COMPLETED: colors.success,
    FAILED: colors.error,
    RUNNING: colors.info,
    PENDING: colors.warning,
    CANCELLED: colors.gray,
  };

  // Filter data by time range
  const displayData = filterAnalyticsByTimeRange(analytics, timeRange);

  // Calculate metrics
  const completedRuns = displayData?.status_breakdown?.COMPLETED || 0;
  const totalRuns = displayData?.total_stats?.total_runs || 0;
  const successRate = totalRuns > 0 ? (completedRuns / totalRuns) * 100 : 0;

  // Prepare chart data
  const statusData = displayData?.status_breakdown 
    ? Object.entries(displayData.status_breakdown).map(([status, count]) => ({
        name: status,
        value: count,
        color: statusColors[status] || colors.gray
      }))
    : [];

  const topUsersData = displayData?.top_users?.slice(0, 8).map(u => ({
    name: truncateUserId(u.user_id, 12),
    fullName: u.user_id,
    runs: u.total_runs,
    blueprints: u.unique_blueprints,
    completed: u.status_breakdown?.COMPLETED || 0,
    failed: u.status_breakdown?.FAILED || 0,
  })) || [];

  // Export to CSV
  const handleExportCSV = () => {
    if (!analytics) return;

    const csvRows = [
      'Workflow Analytics Report',
      `Generated at: ${new Date().toLocaleString()}`,
      '',
      'OVERVIEW STATISTICS',
      'Metric,Value',
      `Total Runs,${analytics.total_stats.total_runs}`,
      `Unique Users,${analytics.total_stats.unique_users}`,
      `Average Runs per User,${analytics.total_stats.avg_runs_per_user.toFixed(2)}`,
      `Success Rate,${successRate.toFixed(1)}%`,
      `Active Today,${analytics.active_today.length}`,
      '',
      'STATUS BREAKDOWN',
      'Status,Count,Percentage',
      ...Object.entries(analytics.status_breakdown).map(([status, count]) => 
        `${status},${count},${((count / totalRuns) * 100).toFixed(1)}%`
      ),
      '',
      'TOP USERS',
      'User ID,Total Runs,Unique Blueprints,Completed,Failed',
      ...analytics.top_users.slice(0, 10).map(user => 
        `${user.user_id},${user.total_runs},${user.unique_blueprints},${user.status_breakdown.COMPLETED || 0},${user.status_breakdown.FAILED || 0}`
      ),
      '',
      'TOP BLUEPRINTS',
      'Blueprint Name,Total Runs,Unique Users,Avg Runs per User',
      ...analytics.top_blueprints.map(bp => 
        `"${bp.blueprint_name}",${bp.run_count},${bp.unique_users},${(bp.run_count / bp.unique_users).toFixed(1)}`
      ),
    ];

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `workflow-analytics-${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Render different states
  if (!hasAccess) {
    return (
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Analytics" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
          <main className="flex-1 overflow-y-auto bg-background-dark">
            <AccessDenied />
          </main>
          <StatusBar />
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Analytics" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
          <LoadingSkeleton />
          <StatusBar />
        </div>
      </div>
    );
  }

  if (error) {
    const errorMessage = (error as Error).message;
    const isAccessDenied = errorMessage.includes('Access denied') || errorMessage.includes('permission');
    
    return (
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Analytics" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
          <main className="flex-1 overflow-y-auto bg-background-dark">
            {isAccessDenied ? <AccessDenied /> : <ErrorDisplay errorMessage={errorMessage} onRetry={refetch} />}
          </main>
          <StatusBar />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Workflow Analytics" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        
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
                onClick={handleExportCSV} 
                variant="outline"
                size="sm"
                disabled={!analytics}
                className="gap-2 border-gray-700 hover:bg-gray-800"
              >
                <FaDownload />
                Export CSV
              </Button>
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
            <StatCard 
              icon={<FaRocket className="mr-3 h-5 w-5 opacity-70" style={{ color: colors.primary }} />}
              title="Total Runs"
              value={displayData?.total_stats.total_runs || 0}
              subtitle={timeRange === 'all' ? 'All workflow executions' : 'In selected period'}
            />
            <StatCard 
              icon={<FaUsers className="mr-3 h-5 w-5 opacity-70" style={{ color: colors.info }} />}
              title="Total Users"
              value={displayData?.total_stats.unique_users || 0}
              subtitle={timeRange === 'all' ? 'Unique users' : 'Active users'}
            />
            <StatCard 
              icon={<FaCheckCircle className="mr-3 h-5 w-5 opacity-70" style={{ color: colors.success }} />}
              title="Success Rate"
              value={`${successRate.toFixed(1)}%`}
              subtitle="↑ Completed runs"
              subtitleClass="text-success"
            />
            <StatCard 
              icon={<FaFire className="mr-3 h-5 w-5 opacity-70" style={{ color: colors.warning }} />}
              title="Active Today"
              value={analytics?.active_today?.length || 0}
              subtitle="Users active today"
            />
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
                  <StatusBreakdownChart statusData={statusData} totalRuns={totalRuns} colors={colors} />

                  {/* Top Active Users */}
                  <TopUsersChart topUsersData={topUsersData} colors={colors} />

                  {/* Activity Periods */}
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-lg font-heading">Activity Periods</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        <ActivityPeriodRow 
                          label="Last 7 Days" 
                          activeUsers={analytics?.active_7days?.length || 0}
                          totalRuns={analytics?.active_7days?.reduce((sum, u) => sum + u.recent_runs, 0) || 0}
                          color={colors.info}
                        />
                        <ActivityPeriodRow 
                          label="Last 30 Days" 
                          activeUsers={analytics?.active_30days?.length || 0}
                          totalRuns={analytics?.active_30days?.reduce((sum, u) => sum + u.recent_runs, 0) || 0}
                          color={colors.primary}
                        />
                        {analytics?.time_stats?.time_span_days && (
                          <div className="pt-3 border-t border-gray-700">
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-gray-400">Data Span:</span>
                              <span className="text-lg font-bold text-success">{analytics.time_stats.time_span_days} days</span>
                            </div>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Time Statistics */}
                  <TimeStatistics analytics={analytics} />
                </div>
              </TabsContent>

              {/* Users Tab */}
              <TabsContent value="users">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <ActiveTodayTable 
                    users={analytics?.active_today || []}
                    page={activeTodayPage}
                    setPage={setActiveTodayPage}
                    itemsPerPage={itemsPerPage}
                  />
                  <AllUsersTable 
                    users={analytics?.top_users || []}
                    page={allUsersPage}
                    setPage={setAllUsersPage}
                    itemsPerPage={itemsPerPage}
                  />
                </div>
              </TabsContent>

              {/* Blueprints Tab */}
              <TabsContent value="blueprints">
                <BlueprintsTable blueprints={analytics?.top_blueprints || []} />
              </TabsContent>
            </Tabs>
          </motion.div>

          {/* Footer */}
          <div className="mt-6 text-center text-xs text-gray-500">
            Data generated at: {analytics?.generated_at ? new Date(analytics.generated_at).toLocaleString() : 'N/A'} • Auto-refreshes every 60 seconds
          </div>
        </main>
        
        <StatusBar />
      </div>
    </div>
  );
}

// Stat Card Component
function StatCard({ icon, title, value, subtitle, subtitleClass = "text-gray-400" }: any) {
  return (
    <Card className="relative overflow-hidden rounded-2xl bg-background-card shadow-card hover:shadow-card-hover transition-all border-0">
      <CardContent className="p-6">
        <div className="space-y-2">
          <h3 className="text-lg font-semibold text-white flex items-center">
            {icon}
            {title}
          </h3>
          <div className="pt-2">
            <p className="text-3xl font-bold text-white">{value}</p>
            <p className={`text-xs mt-1 ${subtitleClass}`}>{subtitle}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Status Breakdown Chart Component
function StatusBreakdownChart({ statusData, totalRuns, colors }: any) {
  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-heading flex items-center gap-2">
          <FaCheckCircle className="text-success" />
          Status Breakdown
        </CardTitle>
      </CardHeader>
      <CardContent>
        {statusData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={statusData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                dataKey="value"
                label={false}
              >
                {statusData.map((entry: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Legend 
                verticalAlign="bottom" 
                height={36}
                formatter={(value: string, entry: any) => {
                  const count = entry.payload.value;
                  const percent = ((count / totalRuns) * 100).toFixed(0);
                  return <span className="text-sm">{value}: {count} ({percent}%)</span>;
                }}
              />
              <Tooltip 
                contentStyle={{ backgroundColor: '#374151', border: '1px solid #6B7280', borderRadius: '0.375rem' }}
                labelStyle={{ color: '#F9FAFB' }}
                formatter={(value: number, name: string) => [
                  `${value} runs (${((value / totalRuns) * 100).toFixed(1)}%)`,
                  name
                ]}
              />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400">
            <FaCheckCircle className="text-5xl mb-4 opacity-30" />
            <p className="text-sm">No workflow data available</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Top Users Chart Component
function TopUsersChart({ topUsersData, colors }: any) {
  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-heading flex items-center gap-2">
          <FaUsers style={{ color: colors.info }} />
          Top Active Users
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={topUsersData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis 
              dataKey="name" 
              stroke="#9CA3AF" 
              angle={-45} 
              textAnchor="end" 
              height={80}
              style={{ fontSize: '12px' }}
            />
            <YAxis stroke="#9CA3AF" style={{ fontSize: '12px' }} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#374151', border: '1px solid #6B7280', borderRadius: '0.375rem' }}
              labelStyle={{ color: '#F9FAFB' }}
              formatter={(value, name) => [value, name === 'runs' ? 'Total Runs' : 'Blueprints']}
            />
            <Bar dataKey="runs" fill={colors.primary} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// Time Statistics Component
function TimeStatistics({ analytics }: any) {
  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-heading flex items-center gap-2">
          <FaClock className="text-warning" />
          Time Statistics
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {analytics?.time_stats?.earliest_run && (
            <div className="p-3 bg-background-dark rounded-md">
              <p className="text-xs text-gray-500 mb-1">First Run</p>
              <p className="text-sm font-medium truncate">{analytics.time_stats.earliest_run.user_id}</p>
              <p className="text-xs text-gray-400 mt-1">
                {new Date(analytics.time_stats.earliest_run.timestamp).toLocaleString()}
              </p>
            </div>
          )}
          {analytics?.time_stats?.latest_run && (
            <div className="p-3 bg-background-dark rounded-md">
              <p className="text-xs text-gray-500 mb-1">Latest Run</p>
              <p className="text-sm font-medium truncate">{analytics.time_stats.latest_run.user_id}</p>
              <p className="text-xs text-gray-400 mt-1">
                {new Date(analytics.time_stats.latest_run.timestamp).toLocaleString()}
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// Active Today Table Component
function ActiveTodayTable({ users, page, setPage, itemsPerPage }: any) {
  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-heading flex items-center gap-2">
          <FaFire className="text-warning" />
          Active Today
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User ID</TableHead>
                <TableHead className="text-right">Runs</TableHead>
                <TableHead className="text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.length > 0 ? (
                users.slice(page * itemsPerPage, (page + 1) * itemsPerPage).map((user: any, idx: number) => (
                  <TableRow key={idx} className="hover:bg-muted/50">
                    <TableCell className="font-medium text-sm truncate max-w-[200px]">
                      {user.user_id}
                    </TableCell>
                    <TableCell className="text-right text-sm">{user.runs_today}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex gap-1 justify-end">
                        {user.status_breakdown.COMPLETED > 0 && (
                          <Badge variant="outline" className="border-success text-success text-xs">
                            ✓ {user.status_breakdown.COMPLETED}
                          </Badge>
                        )}
                        {user.status_breakdown.FAILED > 0 && (
                          <Badge variant="outline" className="border-error text-error text-xs">
                            ✗ {user.status_breakdown.FAILED}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={3} className="text-center py-6 text-gray-400">
                    No active users today
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
        {users.length > itemsPerPage && (
          <PaginationControls 
            currentPage={page}
            totalItems={users.length}
            itemsPerPage={itemsPerPage}
            onPageChange={setPage}
          />
        )}
      </CardContent>
    </Card>
  );
}

// All Users Table Component
function AllUsersTable({ users, page, setPage, itemsPerPage }: any) {
  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-heading">User Activity Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User ID</TableHead>
                <TableHead className="text-right">Runs</TableHead>
                <TableHead className="text-right">Blueprints</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.slice(page * itemsPerPage, (page + 1) * itemsPerPage).map((user: any, idx: number) => (
                <TableRow key={idx} className="hover:bg-muted/50">
                  <TableCell className="font-medium text-sm truncate max-w-[200px]">
                    {user.user_id}
                  </TableCell>
                  <TableCell className="text-right text-sm">{user.total_runs}</TableCell>
                  <TableCell className="text-right text-sm">{user.unique_blueprints}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {users.length > itemsPerPage && (
          <PaginationControls 
            currentPage={page}
            totalItems={users.length}
            itemsPerPage={itemsPerPage}
            onPageChange={setPage}
          />
        )}
      </CardContent>
    </Card>
  );
}

// Blueprints Table Component
function BlueprintsTable({ blueprints }: any) {
  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-heading">Most Used Blueprints</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Blueprint Name</TableHead>
                <TableHead className="text-right">Total Runs</TableHead>
                <TableHead className="text-right">Unique Users</TableHead>
                <TableHead className="text-right">Avg Runs/User</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {blueprints.length > 0 ? (
                blueprints.map((bp: any, idx: number) => (
                  <TableRow key={idx} className="hover:bg-muted/50">
                    <TableCell className="font-medium text-sm max-w-[300px] truncate">
                      {bp.blueprint_name}
                    </TableCell>
                    <TableCell className="text-right text-sm font-semibold text-primary">
                      {bp.run_count}
                    </TableCell>
                    <TableCell className="text-right text-sm">{bp.unique_users}</TableCell>
                    <TableCell className="text-right text-sm text-gray-400">
                      {(bp.run_count / bp.unique_users).toFixed(1)}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-6 text-gray-400">
                    No blueprint data available
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

// Pagination Controls Component
function PaginationControls({ currentPage, totalItems, itemsPerPage, onPageChange }: any) {
  return (
    <div className="flex justify-between items-center mt-4 px-2">
      <span className="text-sm text-gray-400">
        Showing {currentPage * itemsPerPage + 1}-{Math.min((currentPage + 1) * itemsPerPage, totalItems)} of {totalItems}
      </span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange((p: number) => Math.max(0, p - 1))}
          disabled={currentPage === 0}
          className="border-gray-700"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange((p: number) => p + 1)}
          disabled={(currentPage + 1) * itemsPerPage >= totalItems}
          className="border-gray-700"
        >
          Next
        </Button>
      </div>
    </div>
  );
}
