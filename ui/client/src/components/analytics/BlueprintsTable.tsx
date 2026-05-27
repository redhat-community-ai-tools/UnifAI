import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { FaRocket, FaEye, FaChartBar } from "react-icons/fa";
import { useMemo } from "react";
import { generateColorPalette } from "@/lib/colorUtils";
import { AnalyticCard } from "./AnalyticCard";
import { formatDuration, getSuccessRateColor } from "./analyticsHelpers";
import { formatRelativeTimestamp } from "@/utils";
import type { BlueprintUsage } from "@/types/systemStats";

interface BlueprintsTableProps {
  blueprints: BlueprintUsage[];
  colors: Record<string, string>;
}

export function BlueprintsTable({ blueprints, colors }: BlueprintsTableProps) {
  const colorPalette = useMemo(() => {
    return generateColorPalette(colors.primary, blueprints?.length || 0);
  }, [colors.primary, blueprints?.length]);

  return (
    <AnalyticCard
      title="Most Used Blueprints"
      icon={<FaRocket style={{ color: colors.primary }} />}
    >
      <div className="overflow-x-auto">
        <TooltipProvider>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Blueprint Name</TableHead>
                <TableHead className="text-right">Total Runs</TableHead>
                <TableHead className="text-right">Avg Duration</TableHead>
                <TableHead className="text-right">Last Run</TableHead>
                <TableHead className="text-right">Success Rate</TableHead>
                <TableHead className="text-right">Users</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {blueprints.length > 0 ? (
                blueprints.map((bp, idx) => {
                  const color = colorPalette[idx % colorPalette.length];
                  return (
                    <TableRow key={idx} className="hover:bg-muted/50">
                      <TableCell className="font-medium text-sm max-w-[200px] truncate" title={bp.blueprint_name}>
                        {bp.blueprint_name}
                      </TableCell>
                      <TableCell className="text-right text-sm font-semibold" style={{ color }}>
                        {bp.run_count}
                      </TableCell>
                      <TableCell className="text-right text-sm text-gray-400">
                        {formatDuration(bp.avg_duration_seconds)}
                      </TableCell>
                      <TableCell className="text-right text-sm text-gray-400">
                        {bp.last_run_at ? formatRelativeTimestamp(bp.last_run_at) : "—"}
                      </TableCell>
                      <TableCell className="text-right text-sm">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div className="inline-flex items-center gap-1.5 cursor-default">
                              <span className={getSuccessRateColor(bp.success_rate ?? 0)}>
                                {(bp.success_rate ?? 0).toFixed(1)}%
                              </span>
                              <FaChartBar className="w-3 h-3 text-gray-500" />
                            </div>
                          </TooltipTrigger>
                          <TooltipContent side="left" className="max-w-xs">
                            <div className="text-xs space-y-1">
                              <p className="font-semibold mb-1.5">Execution Breakdown</p>
                              <div className="flex justify-between gap-4">
                                <span className="text-green-400">Completed</span>
                                <span className="font-medium">{bp.completed_runs ?? 0}</span>
                              </div>
                              <div className="flex justify-between gap-4">
                                <span className="text-red-400">Failed</span>
                                <span className="font-medium">{bp.failed_runs ?? 0}</span>
                              </div>
                              {(bp.in_progress_runs ?? 0) > 0 && (
                                <div className="flex justify-between gap-4">
                                  <span className="text-yellow-400">In Progress</span>
                                  <span className="font-medium">{bp.in_progress_runs}</span>
                                </div>
                              )}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TableCell>
                      <TableCell className="text-right text-sm">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div className="inline-flex items-center gap-1.5 cursor-default">
                              <span>{bp.unique_users}</span>
                              <FaEye className="w-3 h-3 text-gray-500" />
                            </div>
                          </TooltipTrigger>
                          <TooltipContent side="left" className="max-w-xs">
                            <div className="text-xs">
                              <p className="font-semibold mb-1">Identities who ran this workflow:</p>
                              <div className="max-h-32 overflow-y-auto">
                                {bp.user_list && bp.user_list.length > 0 ? (
                                  bp.user_list.map((entry, i) => {
                                    const [type, ...idParts] = entry.split(':');
                                    const id = idParts.join(':');
                                    return (
                                      <div key={i} className="text-gray-300 truncate flex items-center gap-1">
                                        {type === 'team' && <span className="text-blue-400">[team]</span>}
                                        <span>{id || entry}</span>
                                      </div>
                                    );
                                  })
                                ) : (
                                  <div className="text-gray-400">No identities found</div>
                                )}
                              </div>
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-6 text-gray-400">
                    No blueprint data available
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TooltipProvider>
      </div>
    </AnalyticCard>
  );
}
