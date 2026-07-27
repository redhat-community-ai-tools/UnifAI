import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { FaFire } from "react-icons/fa";
import { AnalyticCard } from "./AnalyticCard";
import { Pagination } from "@/components/shared/Pagination";
import type { TimeRange } from "@/types/systemStats";

const STATUS_CONFIG: Array<{ key: string; label: string; color: string }> = [
  { key: "COMPLETED",  label: "Completed",  color: "#10B981" },
  { key: "FAILED",     label: "Failed",     color: "#F87171" },
  { key: "RUNNING",    label: "Running",    color: "#60A5FA" },
  { key: "PENDING",    label: "Pending",    color: "#FBBF24" },
  { key: "QUEUED",     label: "Queued",     color: "#A78BFA" },
  { key: "CANCELLED",  label: "Cancelled",  color: "#9CA3AF" },
  { key: "LOCKED",     label: "Locked",     color: "#F97316" },
  { key: "IN_USE",     label: "In Use",     color: "#2DD4BF" },
];

interface ActiveTodayTableProps {
  users: Array<{
    identity_id: string;
    identity_type: string;
    display_name: string;
    run_count: number;
    status_breakdown?: Record<string, number>;
  }>;
  page: number;
  setPage: (updater: (page: number) => number) => void;
  itemsPerPage: number;
  timeRange?: TimeRange;
}

function StatusBar({ breakdown }: { breakdown?: Record<string, number> }) {
  if (!breakdown) return null;

  const total = Object.values(breakdown).reduce((sum, v) => sum + v, 0);
  if (total === 0) return null;

  const segments = STATUS_CONFIG
    .filter(s => (breakdown[s.key] ?? 0) > 0)
    .map(s => ({ ...s, count: breakdown[s.key]! }));

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex flex-col gap-1 ml-auto cursor-default w-32">
            <div className="flex h-4 rounded-full overflow-hidden bg-muted">
              {segments.map(seg => (
                <div
                  key={seg.key}
                  style={{
                    width: `${(seg.count / total) * 100}%`,
                    backgroundColor: seg.color,
                  }}
                />
              ))}
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="left" className="max-w-xs">
          <div className="text-xs space-y-1">
            {segments.map(seg => (
              <div key={seg.key} className="flex items-center justify-between gap-4">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: seg.color }} />
                  {seg.label}
                </span>
                <span className="font-medium">{seg.count}</span>
              </div>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export function ActiveTodayTable({ users, page, setPage, itemsPerPage, timeRange = 'today' }: ActiveTodayTableProps) {
  const getTitle = () => {
    switch (timeRange) {
      case 'today':
        return 'Active Today';
      case '7days':
        return 'Active (Last 7 Days)';
      case '30days':
        return 'Active (Last 30 Days)';
      case 'all':
        return 'Active (All Time)';
      default:
        return 'Active Today';
    }
  };

  const getEmptyMessage = () => {
    switch (timeRange) {
      case 'today':
        return 'No active users today';
      case '7days':
        return 'No active users in the last 7 days';
      case '30days':
        return 'No active users in the last 30 days';
      case 'all':
        return 'No active users';
      default:
        return 'No active users';
    }
  };

  const pageCount = Math.ceil(users.length / itemsPerPage);

  return (
    <AnalyticCard
      title={getTitle()}
      icon={<FaFire className="text-warning" />}
    >
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Identity</TableHead>
              <TableHead className="text-right">Runs</TableHead>
              <TableHead className="text-right">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.length > 0 ? (
              users.slice(page * itemsPerPage, (page + 1) * itemsPerPage).map((user, idx) => (
                <TableRow key={idx} className="hover:bg-muted/50">
                  <TableCell className="font-medium text-sm truncate max-w-[200px]">
                    <span className="flex items-center gap-1.5">
                      {user.identity_type === 'team' && (
                        <span className="text-xs text-blue-400 font-normal">[team]</span>
                      )}
                      {user.display_name || user.identity_id}
                    </span>
                  </TableCell>
                  <TableCell className="text-right text-sm">{user.run_count}</TableCell>
                  <TableCell className="text-right">
                    <StatusBar breakdown={user.status_breakdown} />
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={3} className="text-center py-6 text-gray-400">
                  {getEmptyMessage()}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {users.length > itemsPerPage && (
        <Pagination
          pageIndex={page}
          pageCount={pageCount}
          pageSize={itemsPerPage}
          totalItems={users.length}
          onPreviousPage={() => setPage((p) => Math.max(0, p - 1))}
          onNextPage={() => setPage((p) => p + 1)}
          canPreviousPage={page > 0}
          canNextPage={page < pageCount - 1}
          itemName="users"
        />
      )}
    </AnalyticCard>
  );
}
