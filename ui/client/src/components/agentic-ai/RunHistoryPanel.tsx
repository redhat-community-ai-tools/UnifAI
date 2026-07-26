import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { ExternalLink, Loader2 } from "lucide-react";
import { getPromptRuns, PromptRunResponse } from "@/api/prompts";
import { parseUtcDate } from "@/utils/dateUtils";

const STATUS_BADGE: Record<string, string> = {
  COMPLETED: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  FAILED: "bg-red-500/15 text-red-400 border-red-500/30",
  RUNNING: "bg-blue-500/15 text-blue-400 border-blue-500/30",
};

function badgeClass(status: string): string {
  return STATUS_BADGE[status] ?? "bg-gray-500/15 text-gray-400 border-gray-500/30";
}

function formatTime(iso: string): string {
  const d = parseUtcDate(iso);
  const now = new Date();
  const isToday =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (isToday) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" }) +
    " " +
    d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

interface RunHistoryPanelProps {
  promptId: string;
  userId: string;
  identityType: string;
}

export default function RunHistoryPanel({ promptId, userId, identityType }: RunHistoryPanelProps) {
  const [, navigate] = useLocation();

  const { data: runs = [], isLoading } = useQuery<PromptRunResponse[]>({
    queryKey: ["prompt-runs", promptId],
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
                <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border ${badgeClass(run.status)}`}>
                  {run.status}
                </span>
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
