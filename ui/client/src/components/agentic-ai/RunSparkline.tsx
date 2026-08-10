import React from "react";
import { useLocation } from "wouter";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { type RunStats } from "@/api/schedules";
import { formatRelativeTime } from "@/utils/dateTimeUtils";

const STATUS_COLORS: Record<string, string> = {
  COMPLETED: "bg-emerald-400",
  FAILED: "bg-red-400",
  CANCELLED: "bg-gray-400",
  RUNNING: "bg-blue-400 animate-pulse",
};

function dotColor(status: string): string {
  return STATUS_COLORS[status] ?? "bg-gray-500";
}

interface RunSparklineProps {
  summary: RunStats | null | undefined;
  onExpand?: () => void;
}

export default function RunSparkline({ summary, onExpand }: RunSparklineProps) {
  const [, navigate] = useLocation();

  if (!summary || summary.total_runs === 0) {
    return <span className="text-gray-600 text-sm">No runs yet</span>;
  }

  const { recent_statuses, total_runs, last_run_at } = summary;
  const failCount = recent_statuses.filter((r) => r.status === "FAILED").length;

  return (
    <button
      onClick={onExpand}
      className="flex items-center gap-2 group text-left hover:bg-white/5 rounded px-1.5 py-1 -mx-1.5 transition-colors"
    >
      <div className="flex items-center gap-0.5">
        {recent_statuses.map((run, i) => (
          <SimpleTooltip
            key={run.session_id ?? i}
            content={
              <p>
                {run.status}{run.started_at ? ` · ${formatRelativeTime(run.started_at)}` : ""}
              </p>
            }
          >
            <span
              className={`inline-block w-2 h-2 rounded-full ${dotColor(run.status)} cursor-pointer`}
              onClick={(e) => {
                if (run.session_id) {
                  e.stopPropagation();
                  navigate(`/agentic-chats/${run.session_id}`);
                }
              }}
            />
          </SimpleTooltip>
        ))}
      </div>

      <span className="text-xs text-gray-500 group-hover:text-gray-300 transition-colors whitespace-nowrap">
        {total_runs} run{total_runs !== 1 ? "s" : ""}
        {failCount > 0 && (
          <span className="text-red-400 ml-1">
            ({failCount} failed)
          </span>
        )}
        {last_run_at && (
          <span className="ml-1 text-gray-600">
            · {formatRelativeTime(last_run_at)}
          </span>
        )}
      </span>
    </button>
  );
}
