import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { FaFire } from "react-icons/fa";
import { AnalyticCard } from "./AnalyticCard";
import { Pagination } from "@/components/shared/Pagination";
import type { TimeRange } from "@/types/systemStats";

interface ActiveTodayTableProps {
  users: Array<{
    user_id: string;
    run_count: number;
    status_breakdown?: {
      COMPLETED?: number;
      FAILED?: number;
      PENDING?: number;
    };
  }>;
  page: number;
  setPage: (updater: (page: number) => number) => void;
  itemsPerPage: number;
  timeRange?: TimeRange;
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
              <TableHead>User ID</TableHead>
              <TableHead className="text-right">Runs</TableHead>
              <TableHead className="text-right">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.length > 0 ? (
              users.slice(page * itemsPerPage, (page + 1) * itemsPerPage).map((user, idx) => (
                <TableRow key={idx} className="hover:bg-muted/50">
                  <TableCell className="font-medium text-sm truncate max-w-[200px]">
                    {user.user_id}
                  </TableCell>
                  <TableCell className="text-right text-sm">{user.run_count}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex gap-1 justify-end">
                      {user.status_breakdown?.COMPLETED && user.status_breakdown.COMPLETED > 0 && (
                        <Badge variant="outline" className="border-success text-success text-xs">
                          ✓ {user.status_breakdown.COMPLETED}
                        </Badge>
                      )}
                      {user.status_breakdown?.FAILED && user.status_breakdown.FAILED > 0 && (
                        <Badge variant="outline" className="border-error text-error text-xs">
                          ✗ {user.status_breakdown.FAILED}
                        </Badge>
                      )}
                      {user.status_breakdown?.PENDING && user.status_breakdown.PENDING > 0 && (
                        <Badge variant="outline" className="border-yellow-500 text-yellow-500 text-xs">
                          ◷ {user.status_breakdown.PENDING}
                        </Badge>
                      )}
                    </div>
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
