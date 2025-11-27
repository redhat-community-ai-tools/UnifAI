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
import { Skeleton } from "@/components/ui/skeleton";
import { 
  FaUsers, FaRocket, FaChartLine, FaCheckCircle, 
  FaExclamationCircle, FaClock, FaSpinner, FaFire, FaLock, FaSync, FaDownload
} from "react-icons/fa";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from "recharts";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import { useLocation } from "wouter";

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
  const [, setLocation] = useLocation();

  // Check if user has access (permission set by backend)
  const hasAccess = user?.can_access_analytics || false;

  // Fetch analytics data (only if user has access)
  const { data: analytics, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['analyticsOverview'],
    queryFn: fetchAnalyticsOverview,
    staleTime: 60000, // Consider data fresh for 1 minute
    gcTime: 300000, // Keep in cache for 5 minutes (previously cacheTime)
    refetchInterval: 60000, // Refresh every 60 seconds (reduced frequency)
    refetchOnWindowFocus: false, // Don't refetch on every window focus
    enabled: hasAccess, // Only fetch if user has access
  });

  // Update last updated timestamp when data changes
  useEffect(() => {
    if (analytics) {
      setLastUpdated(new Date());
    }
  }, [analytics]);

  const handleRefresh = () => {
    refetch();
  };

  // Color palette
  const colors = {
    primary: primaryHex || "#8B5CF6",
    success: "#10B981",
    warning: "#F59E0B",
    error: "#EF4444",
    info: "#3B82F6",
    gray: "#6B7280",
  };

  // Status colors mapping
  const statusColors: Record<string, string> = {
    COMPLETED: colors.success,
    FAILED: colors.error,
    RUNNING: colors.info,
    PENDING: colors.warning,
    CANCELLED: colors.gray,
  };

  // Filter data based on time range (must be defined before using it)
  const getFilteredData = () => {
    if (!analytics) return null;
    
    // For 'all', return original data
    if (timeRange === 'all') return analytics;
    
    // For time-based filters, use the appropriate data
    const filteredData = { ...analytics };
    
    if (timeRange === 'today') {
      // Use only today's data
      const todayUsers = analytics.active_today || [];
      filteredData.top_users = todayUsers.map(u => ({
        user_id: u.user_id,
        total_runs: u.runs_today || 0,
        unique_blueprints: 0,
        status_breakdown: u.status_breakdown
      }));
      
      // Recalculate stats for today
      const todayTotalRuns = todayUsers.reduce((sum, u) => sum + (u.runs_today || 0), 0);
      filteredData.total_stats = {
        total_runs: todayTotalRuns,
        unique_users: todayUsers.length,
        avg_runs_per_user: todayUsers.length > 0 ? todayTotalRuns / todayUsers.length : 0
      };
      
      // Recalculate status breakdown for today
      const todayStatusBreakdown: Record<string, number> = {};
      todayUsers.forEach(u => {
        Object.entries(u.status_breakdown || {}).forEach(([status, count]) => {
          todayStatusBreakdown[status] = (todayStatusBreakdown[status] || 0) + count;
        });
      });
      filteredData.status_breakdown = todayStatusBreakdown;
      
    } else if (timeRange === '7days') {
      // Use 7-day data
      const users7days = analytics.active_7days || [];
      filteredData.top_users = users7days.map(u => ({
        user_id: u.user_id,
        total_runs: u.recent_runs,
        unique_blueprints: 0,
        status_breakdown: u.status_breakdown || {}
      }));
      
      const totalRuns7days = users7days.reduce((sum, u) => sum + u.recent_runs, 0);
      filteredData.total_stats = {
        total_runs: totalRuns7days,
        unique_users: users7days.length,
        avg_runs_per_user: users7days.length > 0 ? totalRuns7days / users7days.length : 0
      };
      
      // Recalculate status breakdown for 7 days (if available)
      // Note: The backend doesn't provide status breakdown per time period
      // So for now we'll keep the all-time breakdown, or calculate from active users if available
      const statusBreakdown7days: Record<string, number> = {};
      users7days.forEach(u => {
        Object.entries(u.status_breakdown || {}).forEach(([status, count]) => {
          statusBreakdown7days[status] = (statusBreakdown7days[status] || 0) + count;
        });
      });
      if (Object.keys(statusBreakdown7days).length > 0) {
        filteredData.status_breakdown = statusBreakdown7days;
      }
      
    } else if (timeRange === '30days') {
      // Use 30-day data
      const users30days = analytics.active_30days || [];
      filteredData.top_users = users30days.map(u => ({
        user_id: u.user_id,
        total_runs: u.recent_runs,
        unique_blueprints: 0,
        status_breakdown: u.status_breakdown || {}
      }));
      
      const totalRuns30days = users30days.reduce((sum, u) => sum + u.recent_runs, 0);
      filteredData.total_stats = {
        total_runs: totalRuns30days,
        unique_users: users30days.length,
        avg_runs_per_user: users30days.length > 0 ? totalRuns30days / users30days.length : 0
      };
      
      // Recalculate status breakdown for 30 days
      const statusBreakdown30days: Record<string, number> = {};
      users30days.forEach(u => {
        Object.entries(u.status_breakdown || {}).forEach(([status, count]) => {
          statusBreakdown30days[status] = (statusBreakdown30days[status] || 0) + count;
        });
      });
      if (Object.keys(statusBreakdown30days).length > 0) {
        filteredData.status_breakdown = statusBreakdown30days;
      }
    }
    
    return filteredData;
  };

  const displayData = getFilteredData();

  // Calculate success rate
  const completedRuns = displayData?.status_breakdown?.COMPLETED || 0;
  const totalRuns = displayData?.total_stats.total_runs || 0;
  const successRate = totalRuns > 0 ? (completedRuns / totalRuns) * 100 : 0;

  // Prepare chart data using filtered/displayed data
  const statusData = displayData?.status_breakdown 
    ? Object.entries(displayData.status_breakdown).map(([status, count]) => ({
        name: status,
        value: count,
        color: statusColors[status] || colors.gray
      }))
    : [];

  const topUsersData = displayData?.top_users?.slice(0, 8).map(u => ({
    name: u.user_id.length > 12 ? u.user_id.substring(0, 12) + '...' : u.user_id,
    fullName: u.user_id,
    runs: u.total_runs,
    blueprints: u.unique_blueprints,
    completed: u.status_breakdown?.COMPLETED || 0,
    failed: u.status_breakdown?.FAILED || 0,
  })) || [];

  // Export to CSV function
  const handleExportCSV = () => {
    if (!analytics) return;

    // Prepare CSV data
    const csvRows = [];
    
    // Header
    csvRows.push('Workflow Analytics Report');
    csvRows.push(`Generated at: ${new Date().toLocaleString()}`);
    csvRows.push('');
    
    // Total Stats
    csvRows.push('OVERVIEW STATISTICS');
    csvRows.push('Metric,Value');
    csvRows.push(`Total Runs,${analytics.total_stats.total_runs}`);
    csvRows.push(`Unique Users,${analytics.total_stats.unique_users}`);
    csvRows.push(`Average Runs per User,${analytics.total_stats.avg_runs_per_user.toFixed(2)}`);
    csvRows.push(`Success Rate,${successRate.toFixed(1)}%`);
    csvRows.push(`Active Today,${analytics.active_today.length}`);
    csvRows.push('');
    
    // Status Breakdown
    csvRows.push('STATUS BREAKDOWN');
    csvRows.push('Status,Count,Percentage');
    Object.entries(analytics.status_breakdown).forEach(([status, count]) => {
      const percent = ((count / totalRuns) * 100).toFixed(1);
      csvRows.push(`${status},${count},${percent}%`);
    });
    csvRows.push('');
    
    // Top Users
    csvRows.push('TOP USERS');
    csvRows.push('User ID,Total Runs,Unique Blueprints,Completed,Failed');
    analytics.top_users.slice(0, 10).forEach(user => {
      csvRows.push(`${user.user_id},${user.total_runs},${user.unique_blueprints},${user.status_breakdown.COMPLETED || 0},${user.status_breakdown.FAILED || 0}`);
    });
    csvRows.push('');
    
    // Top Blueprints
    csvRows.push('TOP BLUEPRINTS');
    csvRows.push('Blueprint Name,Total Runs,Unique Users,Avg Runs per User');
    analytics.top_blueprints.forEach(bp => {
      csvRows.push(`"${bp.blueprint_name}",${bp.run_count},${bp.unique_users},${(bp.run_count / bp.unique_users).toFixed(1)}`);
    });
    
    // Create CSV string
    const csvContent = csvRows.join('\n');
    
    // Create download link
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `workflow-analytics-${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Access Denied Screen
  if (!hasAccess) {
    return (
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Analytics" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
          <main className="flex-1 overflow-y-auto bg-background-dark">
            <div className="p-6 flex items-center justify-center h-full">
              <Card className="bg-background-card shadow-card border-gray-800 p-8 max-w-md">
                <div className="text-center">
                  <div className="mx-auto w-16 h-16 rounded-full bg-warning bg-opacity-20 flex items-center justify-center mb-4">
                    <FaLock className="text-4xl text-warning" />
                  </div>
                  <h3 className="text-xl font-heading font-semibold mb-2">Access Restricted</h3>
                  <p className="text-sm text-gray-400 mb-6">
                    You don't have permission to access Analytics. Please contact your administrator if you need access.
                  </p>
                  <Button 
                    onClick={() => setLocation('/agentic-ai')} 
                    className="bg-primary hover:bg-opacity-80"
                  >
                    Go to Home
                  </Button>
                </div>
              </Card>
            </div>
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
          <main className="flex-1 overflow-y-auto bg-background-dark p-6">
            {/* Header Skeleton */}
            <div className="flex justify-between items-center mb-6">
              <div>
                <Skeleton className="h-8 w-48 mb-2" />
                <Skeleton className="h-4 w-32" />
              </div>
              <div className="flex gap-2">
                <Skeleton className="h-9 w-32" />
                <Skeleton className="h-9 w-24" />
              </div>
            </div>

            {/* Time Range Skeleton */}
            <div className="flex gap-2 mb-6">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-9 w-28" />
              ))}
            </div>

            {/* Stats Cards Skeleton */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-6">
              {[...Array(5)].map((_, i) => (
                <Card key={i} className="bg-background-card border-0">
                  <CardContent className="p-5">
                    <Skeleton className="h-4 w-20 mb-2" />
                    <Skeleton className="h-8 w-16 mb-4" />
                    <Skeleton className="h-3 w-24" />
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Charts Skeleton */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {[...Array(2)].map((_, i) => (
                <Card key={i} className="bg-background-card border-gray-800">
                  <CardHeader>
                    <Skeleton className="h-6 w-40" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-64 w-full" />
                  </CardContent>
                </Card>
              ))}
            </div>
          </main>
          <StatusBar />
        </div>
      </div>
    );
  }

  if (error) {
    // Check if this is an access denied error (403) or authentication error (401)
    const errorMessage = (error as Error).message;
    const isAccessDenied = errorMessage.includes('Access denied') || errorMessage.includes('permission');
    
    if (isAccessDenied) {
      // Show access restricted UI instead of error
      return (
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden">
            <Header title="Analytics" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
            <main className="flex-1 overflow-y-auto bg-background-dark">
              <div className="p-6 flex items-center justify-center h-full">
                <Card className="bg-background-card shadow-card border-gray-800 p-8 max-w-md">
                  <div className="text-center">
                    <div className="mx-auto w-16 h-16 rounded-full bg-warning bg-opacity-20 flex items-center justify-center mb-4">
                      <FaLock className="text-4xl text-warning" />
                    </div>
                    <h3 className="text-xl font-heading font-semibold mb-2">Access Restricted</h3>
                    <p className="text-sm text-gray-400 mb-6">
                      You don't have permission to access Analytics. Please contact your administrator if you need access.
                    </p>
                    <Button 
                      onClick={() => setLocation('/agentic-ai')} 
                      className="bg-primary hover:bg-opacity-80"
                    >
                      Go to Home
                    </Button>
                  </div>
                </Card>
              </div>
            </main>
            <StatusBar />
          </div>
        </div>
      );
    }
    
    // For other errors, show retry UI
    return (
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Analytics" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
          <main className="flex-1 overflow-y-auto bg-background-dark">
            <div className="p-6 flex items-center justify-center h-full">
              <Card className="bg-background-card shadow-card border-gray-800 p-6 max-w-md">
                <div className="text-center">
                  <FaExclamationCircle className="text-4xl text-error mx-auto mb-4" />
                  <h3 className="text-lg font-heading font-semibold mb-2">Failed to Load Analytics</h3>
                  <p className="text-sm text-gray-400 mb-4">{errorMessage}</p>
                  <button 
                    onClick={() => refetch()} 
                    className="px-4 py-2 bg-primary hover:bg-opacity-80 rounded-md text-sm font-medium transition-colors"
                  >
                    Retry
                  </button>
                </div>
              </Card>
            </div>
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
          {/* Header with Refresh */}
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
                onClick={handleRefresh} 
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
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-6"
          >
            <Card className="relative overflow-hidden rounded-2xl bg-background-card shadow-card hover:shadow-card-hover transition-all border-0">
              <CardContent className="p-6">
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold text-white flex items-center">
                    <FaRocket className="mr-3 h-5 w-5 opacity-70" style={{ color: colors.primary }} />
                    Total Runs
                  </h3>
                  <div className="pt-2">
                    <p className="text-3xl font-bold text-white">{displayData?.total_stats.total_runs || 0}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {timeRange === 'all' ? 'All workflow executions' : `In selected period`}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="relative overflow-hidden rounded-2xl bg-background-card shadow-card hover:shadow-card-hover transition-all border-0">
              <CardContent className="p-6">
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold text-white flex items-center">
                    <FaUsers className="mr-3 h-5 w-5 opacity-70" style={{ color: colors.info }} />
                    Total Users
                  </h3>
                  <div className="pt-2">
                    <p className="text-3xl font-bold text-white">{displayData?.total_stats.unique_users || 0}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {timeRange === 'all' ? 'Unique users' : 'Active users'}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="relative overflow-hidden rounded-2xl bg-background-card shadow-card hover:shadow-card-hover transition-all border-0">
              <CardContent className="p-6">
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold text-white flex items-center">
                    <FaChartLine className="mr-3 h-5 w-5 opacity-70" style={{ color: colors.success }} />
                    Avg Runs/User
                  </h3>
                  <div className="pt-2">
                    <p className="text-3xl font-bold text-white">{displayData?.total_stats.avg_runs_per_user?.toFixed(1) || '0'}</p>
                    <p className="text-xs text-gray-400 mt-1">Average per user</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="relative overflow-hidden rounded-2xl bg-background-card shadow-card hover:shadow-card-hover transition-all border-0">
              <CardContent className="p-6">
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold text-white flex items-center">
                    <FaCheckCircle className="mr-3 h-5 w-5 opacity-70" style={{ color: colors.success }} />
                    Success Rate
                  </h3>
                  <div className="pt-2">
                    <p className="text-3xl font-bold text-white">{successRate.toFixed(1)}%</p>
                    <p className="text-xs text-success mt-1">↑ Completed runs</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="relative overflow-hidden rounded-2xl bg-background-card shadow-card hover:shadow-card-hover transition-all border-0">
              <CardContent className="p-6">
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold text-white flex items-center">
                    <FaFire className="mr-3 h-5 w-5 opacity-70" style={{ color: colors.warning }} />
                    Active Today
                  </h3>
                  <div className="pt-2">
                    <p className="text-3xl font-bold text-white">{analytics?.active_today?.length || 0}</p>
                    <p className="text-xs text-gray-400 mt-1">Users active today</p>
                  </div>
                </div>
              </CardContent>
            </Card>
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
                  {/* Status Breakdown Pie Chart */}
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
                              fill="#8884d8"
                              dataKey="value"
                              label={false}
                            >
                              {statusData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                              ))}
                            </Pie>
                            <Legend 
                              verticalAlign="bottom" 
                              height={36}
                              formatter={(value: string, entry: any) => {
                                const count = entry.payload.value;
                                const percent = ((count / totalRuns) * 100).toFixed(0);
                                return (
                                  <span className="text-sm">
                                    {value}: {count} ({percent}%)
                                  </span>
                                );
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

                  {/* Top Active Users Chart */}
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

                  {/* Activity Period Stats */}
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
                </div>
              </TabsContent>

              {/* Users Tab */}
              <TabsContent value="users">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Active Today */}
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
                            {analytics?.active_today && analytics.active_today.length > 0 ? (
                              analytics.active_today
                                .slice(activeTodayPage * itemsPerPage, (activeTodayPage + 1) * itemsPerPage)
                                .map((user, idx) => (
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
                      {analytics?.active_today && analytics.active_today.length > itemsPerPage && (
                        <div className="flex justify-between items-center mt-4 px-2">
                          <span className="text-sm text-gray-400">
                            Showing {activeTodayPage * itemsPerPage + 1}-{Math.min((activeTodayPage + 1) * itemsPerPage, analytics.active_today.length)} of {analytics.active_today.length}
                          </span>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setActiveTodayPage(p => Math.max(0, p - 1))}
                              disabled={activeTodayPage === 0}
                              className="border-gray-700"
                            >
                              Previous
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setActiveTodayPage(p => p + 1)}
                              disabled={(activeTodayPage + 1) * itemsPerPage >= analytics.active_today.length}
                              className="border-gray-700"
                            >
                              Next
                            </Button>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* All Users Activity */}
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
                            {analytics?.top_users
                              ?.slice(allUsersPage * itemsPerPage, (allUsersPage + 1) * itemsPerPage)
                              .map((user, idx) => (
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
                      {analytics?.top_users && analytics.top_users.length > itemsPerPage && (
                        <div className="flex justify-between items-center mt-4 px-2">
                          <span className="text-sm text-gray-400">
                            Showing {allUsersPage * itemsPerPage + 1}-{Math.min((allUsersPage + 1) * itemsPerPage, analytics.top_users.length)} of {analytics.top_users.length}
                          </span>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setAllUsersPage(p => Math.max(0, p - 1))}
                              disabled={allUsersPage === 0}
                              className="border-gray-700"
                            >
                              Previous
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setAllUsersPage(p => p + 1)}
                              disabled={(allUsersPage + 1) * itemsPerPage >= analytics.top_users.length}
                              className="border-gray-700"
                            >
                              Next
                            </Button>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              {/* Blueprints Tab */}
              <TabsContent value="blueprints">
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
                          {analytics?.top_blueprints && analytics.top_blueprints.length > 0 ? (
                            analytics.top_blueprints.map((bp, idx) => (
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
              </TabsContent>
            </Tabs>
          </motion.div>

          {/* Footer Info */}
          <div className="mt-6 text-center text-xs text-gray-500">
            Data generated at: {analytics?.generated_at ? new Date(analytics.generated_at).toLocaleString() : 'N/A'} • Auto-refreshes every 60 seconds
          </div>
        </main>
        
        <StatusBar />
      </div>
    </div>
  );
}

// Activity Period Row Component
interface ActivityPeriodRowProps {
  label: string;
  activeUsers: number;
  totalRuns: number;
  color: string;
}

function ActivityPeriodRow({ label, activeUsers, totalRuns, color }: ActivityPeriodRowProps) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-400">{label}</span>
        <span className="text-xs text-gray-500">{activeUsers} users • {totalRuns} runs</span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="p-2 bg-background-dark rounded-md text-center">
          <div className="text-xs text-gray-500 mb-1">Users</div>
          <div className="text-lg font-bold" style={{ color }}>{activeUsers}</div>
        </div>
        <div className="p-2 bg-background-dark rounded-md text-center">
          <div className="text-xs text-gray-500 mb-1">Runs</div>
          <div className="text-lg font-bold" style={{ color }}>{totalRuns}</div>
        </div>
      </div>
    </div>
  );
}
