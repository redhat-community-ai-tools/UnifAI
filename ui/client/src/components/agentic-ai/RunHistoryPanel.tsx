import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { ExternalLink, Loader2 } from "lucide-react";
import { getPromptRuns, PromptRunResponse } from "@/api/prompts";
import { formatTime } from "@/utils/dateTimeUtils";
import StatusPill from "@/components/shared/StatusPill";
import { StatusTone } from "@/lib/statusTones";

const RUN_STATUS_TONE: Record<string, StatusTone> = {
  COMPLETED: "success",
  FAILED: "danger",
  RUNNING: "info",
};

function runStatusTone(status: string): StatusTone {
  return RUN_STATUS_TONE[status] ?? "neutral";
}

interface RunHistoryPanelProps {
  promptId: string;
  userId: string;
  identityType: string;
}

export default function RunHistoryPanel({ promptId, userId, identityType }: RunHistoryPanelProps) {
  const [, navigate] = useLocation();

  const { data: runs = [], isLoading, isError } = useQuery<PromptRunResponse[]>({
    queryKey: ["prompt-runs", promptId, userId, identityType],
    queryFn: () => getPromptRuns(promptId, userId, identityType, 8),
    staleTime: 5_000,
    refetchInterval: 10_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-500">
        <Loader2 className="w-4 h-4 animate-spin mr-2" />
        Loading run history…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-center py-8 text-red-400 text-sm">
        Failed to load run history.
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        No runs recorded yet.
      </div>
    );
  }

  return (
    <div className="py-3">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-500 text-xs uppercase tracking-wider">
            <th className="text-left pb-2 font-medium">Time</th>
            <th className="text-left pb-2 font-medium">Status</th>
            <th className="text-right pb-2 font-medium">Session</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {runs.map((run) => (
            <tr key={run.session_id} className="hover:bg-white/5 transition-colors">
              <td className="py-2 text-gray-300">
                {formatTime(run.started_at)}
              </td>
              <td className="py-2">
                <StatusPill tone={runStatusTone(run.status)}>{run.status}</StatusPill>
              </td>
              <td className="py-2 text-right">
                <button
                  onClick={() => navigate(`/agentic-chats/${run.session_id}`)}
                  className="inline-flex items-center gap-1 text-primary hover:underline text-xs"
                >
                  <ExternalLink className="w-3 h-3" />
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
