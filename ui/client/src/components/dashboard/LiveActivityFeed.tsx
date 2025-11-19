import { Card, CardContent } from "@/components/ui/card";
import { Activity, FileText, MessageSquare, Bug, AlertTriangle, Loader2, Slack as SlackIcon } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "@/contexts/ThemeContext";
import { fetchRecentActivities } from "@/api/activity";

type RangeKey = 'today' | 'week' | 'month';

interface LiveActivityFeedProps {
  defaultRange?: RangeKey;
  fullHeight?: boolean;
  contentHeight?: number; // fixed content height (px) for matching other cards
  compact?: boolean; // reduce paddings/gaps for tighter layout
}

export function LiveActivityFeed({ defaultRange = 'month', fullHeight = false, contentHeight, compact = false }: LiveActivityFeedProps) {
  const { primaryHex } = useTheme();
  const [range, setRange] = useState<RangeKey>(defaultRange);
  const sinceHours = useMemo(() => {
    switch (range) {
      case 'today':
        return 24;
      case 'week':
        return 24 * 7;
      case 'month':
        return 24 * 30;
      default:
        return 24;
    }
  }, [range]);

  const { data: activities = [], isLoading } = useQuery({
    queryKey: ['recentActivities', { sources: ['slack','document'], sinceHours }],
    queryFn: () => fetchRecentActivities({ sources: ['slack','document'], sinceHours }),
    refetchInterval: 10000,
    refetchOnWindowFocus: true,
  });
  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'document':
        return <FileText className="text-white text-sm" />;
      case 'slack':
        return <SlackIcon className="text-white text-sm" />;
      case 'jira':
        return <Bug className="text-white text-sm" />;
      default:
        return <AlertTriangle className="text-white text-sm" />;
    }
  };

  // Minimal colors: just color the icon background
  const getActivityColor = (type: string) => {
    if (type === 'slack') {
      return primaryHex || '#A60000';
    }
    if (type === 'document') {
      return 'hsl(var(--secondary))';
    }
    return '#4B5563';
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Done':
      case 'complete':
        return { color: 'badge-slack-green', label: 'Completed' };
      case 'processing':
        return { color: 'badge-slack-blue', label: 'Processing' };
      case 'error':
        return { color: 'badge-slack-red', label: 'Error' };
      default:
        return { color: 'badge-slack-purple', label: status };
    }
  };

  const cleanTitle = (raw: string) => {
    if (!raw) return raw;
    // Remove the trailing or standalone word 'completed'
    return raw.replace(/\bcompleted\b/gi, '').replace(/\s+/g, ' ').trim();
  };

  const getTimeAgo = (timestamp: string | Date) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diffInSeconds < 60) return `${diffInSeconds}s ago`;
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
    return `${Math.floor(diffInSeconds / 86400)}d ago`;
  };

  return (
    <Card className={`rounded-xl border-0 overflow-hidden ${fullHeight ? 'h-full flex flex-col' : ''}`}>
      <div className={`${compact ? 'p-4' : 'p-6'} border-b border-border-gray`}>
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-semibold text-white flex items-center">
            <Activity className="text-primary mr-3 h-6 w-6" />
            Recent Activity Feed
            <div className="ml-3 flex items-center">
              <div className="w-2 h-2 bg-secondary rounded-full animate-pulse mr-2"></div>
              <span className="text-secondary text-sm font-medium">Real-time</span>
            </div>
          </h3>
          {/* Segmented toggle */}
          <div className="hidden sm:flex items-center bg-background-card border border-border rounded-lg overflow-hidden text-sm">
            <button
              onClick={() => setRange('today')}
              className={`px-3 py-1 transition-colors ${range === 'today' ? 'bg-primary/40' : 'text-gray-400 hover:text-white'}`}
              aria-pressed={range === 'today'}
            >
              Today
            </button>
            <div className="w-px h-4 bg-border" />
            <button
              onClick={() => setRange('week')}  
              className={`px-3 py-1 transition-colors ${range === 'week' ? 'bg-primary/40' : 'text-gray-400 hover:text-white'}`}
              aria-pressed={range === 'week'}
            >
              Last week
            </button>
            <div className="w-px h-4 bg-border" />
            <button
              onClick={() => setRange('month')}
              className={`px-3 py-1 transition-colors ${range === 'month' ? 'bg-primary/40' : 'text-gray-400 hover:text-white'}`}
              aria-pressed={range === 'month'}
            >
              Last month
            </button>
          </div>
        </div>
        {/* Mobile toggle below title */}
        <div className="sm:hidden mt-4 flex items-center gap-2 text-xs">
          <button
            className={`px-2 py-1 rounded border ${range === 'today' ? 'border-secondary text-secondary' : 'border-border-gray text-gray-400'}`}
            onClick={() => setRange('today')}
          >
            Today
          </button>
          <button
            className={`px-2 py-1 rounded border ${range === 'week' ? 'border-secondary text-secondary' : 'border-border-gray text-gray-400'}`}
            onClick={() => setRange('week')}
          >
            Last week
          </button>
          <button
            className={`px-2 py-1 rounded border ${range === 'month' ? 'border-secondary text-secondary' : 'border-border-gray text-gray-400'}`}
            onClick={() => setRange('month')}
          >
            Last month
          </button>
        </div>
      </div>
      
      <CardContent className={`${compact ? 'p-4' : 'p-6'} ${fullHeight ? 'flex-1 overflow-hidden' : contentHeight ? 'overflow-hidden' : ''}`} style={contentHeight && !fullHeight ? { height: contentHeight } : undefined}>
        {isLoading ? (
          <div className={`flex items-center justify-center ${fullHeight ? 'h-full' : contentHeight ? 'h-full' : (compact ? 'h-28' : 'h-40')}`}>
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : activities.length === 0 ? (
          <div className={`text-center text-gray-400 ${fullHeight || contentHeight ? 'h-full flex items-center justify-center' : (compact ? 'py-4' : 'py-8')}`}>
            No recent activity to display
          </div>
        ) : (
          <motion.div layout className={`grid grid-cols-1 md:grid-cols-2 ${fullHeight || contentHeight ? 'h-full' : (compact ? 'max-h-64' : 'max-h-80')} overflow-y-auto overflow-x-hidden no-scrollbar [&>div]:border-b [&>div]:border-gray-800/80 md:[&>div:nth-child(odd)]:border-r md:[&>div:nth-child(odd)]:border-gray-800/80`}>
            <AnimatePresence mode="popLayout">
            {activities.map((item) => {
              const statusBadge = getStatusBadge((item as any).status);
              const borderColor = (item as any).status === 'error' ? 'border-red-900' : 'border-gray-700';
              
              return (
                <motion.div
                  layout
                  key={(item as any).id as string}
                  initial={{ opacity: 0, y: 12, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -12, scale: 0.98 }}
                  transition={{ type: "spring", stiffness: 380, damping: 26, mass: 0.8 }}
                  className={`w-full min-w-0 h-full ${compact ? 'p-3' : 'p-4'} flex flex-col justify-center`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0`} style={{ backgroundColor: getActivityColor((item as any).type) }}>
                        {getActivityIcon((item as any).type)}
                      </div>
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-white font-semibold text-base truncate">
                          {cleanTitle((item as any).title)}
                        </span>
                        <span className={`px-2 py-0.5 ${statusBadge.color} text-sm rounded whitespace-nowrap`}>
                          {statusBadge.label}
                        </span>
                        <span className="px-2 py-0.5 bg-gray-800 text-gray-300 text-xs rounded capitalize whitespace-nowrap">
                          {(item as any).type}
                        </span>
                      </div>
                    </div>
                    <span className="text-gray-400 text-sm ml-3 whitespace-nowrap shrink-0">
                      {getTimeAgo((item as any).timestamp)}
                    </span>
                  </div>
                </motion.div>
              );
            })}
            </AnimatePresence>
          </motion.div>
        )}
      </CardContent>
    </Card>
  );
}


