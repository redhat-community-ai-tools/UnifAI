import React, { useState, useCallback, useMemo, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import {
  Play,
  Pause,
  Pencil,
  Trash2,
  Eye,
  RotateCw,
  Clock,
  Plus,
} from "lucide-react";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import StatusPill from "@/components/shared/StatusPill";
import { StatusTone } from "@/lib/statusTones";
import { DataTable, DataTableColumn } from "@/components/shared/DataTable";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";
import { useToast } from "@/hooks/use-toast";
import {
  listSchedules,
  pauseSchedule,
  resumeSchedule,
  deleteSchedule,
  triggerSchedule,
  type WorkflowScheduleResponse,
  type ScheduleDefinitionInput,
} from "@/api/schedules";
import { fetchResolvedBlueprint } from "@/api/blueprints";
import SchedulePromptModal from "@/components/agentic-ai/SchedulePromptModal";
import GraphDisplay from "@/components/agentic-ai/graphs/GraphDisplay";
import RunSparkline from "@/components/agentic-ai/RunSparkline";
import RunHistoryPanel from "@/components/agentic-ai/RunHistoryPanel";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { AddFlowModal } from "@/components/shared/SessionModals";
import type { FlowObject } from "@/components/agentic-ai/graphs/interfaces";
import { useScheduledBlueprintCounts } from "@/hooks/use-scheduled-blueprints";
import { formatDateTime, cronTimeToLocal } from "@/utils/dateTimeUtils";
import { DAY_CRON_NAMES } from "@/constants/dateConstants";

const MAX_ACTIVE_SCHEDULES_PER_WORKFLOW = 10;

// ---------------------------------------------------------------------------
// Schedule label derivation – times are converted to the user's local timezone
// ---------------------------------------------------------------------------

function describeSchedule(schedule: ScheduleDefinitionInput): string {
  if (schedule.remaining_actions === 1 && schedule.start_at) {
    return formatDateTime(schedule.start_at);
  }

  if (schedule.interval) {
    const m = schedule.interval.match(/^PT(\d+)([MH])$/);
    if (m) {
      const v = parseInt(m[1], 10);
      const u = m[2];
      if (u === "M") {
        if (v === 15) return "Every 15 minutes";
        return v === 1 ? "Every minute" : `Every ${v} minutes`;
      }
      if (u === "H") {
        if (v === 1) return "Hourly";
        if (v % 24 === 0) {
          const d = v / 24;
          if (d % 7 === 0) {
            const w = d / 7;
            return w === 1 ? "Weekly" : `Every ${w} weeks`;
          }
          return d === 1 ? "Daily" : `Every ${d} days`;
        }
        return `Every ${v} hours`;
      }
    }
  }

  if (schedule.cron_expression) {
    const tz = schedule.timezone || "UTC";
    const parts = schedule.cron_expression.split(" ");
    if (parts.length === 5) {
      const [min, hour, dom, , dow] = parts;
      const localTime = cronTimeToLocal(parseInt(hour, 10), parseInt(min, 10), tz);
      if (dom === "*" && dow === "*") return `Daily at ${localTime}`;
      if (dom === "*" && dow !== "*") {
        const dayTokens = dow.split(",");
        const labels = dayTokens.map((t) => {
          const num = parseInt(t, 10);
          if (!isNaN(num)) return DAY_CRON_NAMES[num]?.slice(0, 3) ?? t;
          return t.slice(0, 3);
        });
        if (labels.length === 1) return `Weekly on ${labels[0]} at ${localTime}`;
        return `Weekly on ${labels.join(", ")} at ${localTime}`;
      }
      if (dom !== "*" && dow === "*") return `Monthly on the ${dom} at ${localTime}`;
    }
    return schedule.cron_expression;
  }

  return "Custom";
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

enum ScheduleStatus {
  Active = "active",
  Paused = "paused",
  Completed = "completed",
}

const SCHEDULE_STATUS_TONE: Record<ScheduleStatus, StatusTone> = {
  [ScheduleStatus.Active]: "success",
  [ScheduleStatus.Paused]: "warning",
  [ScheduleStatus.Completed]: "neutral",
};

function StatusBadge({ status }: { status: ScheduleStatus }) {
  return (
    <StatusPill tone={SCHEDULE_STATUS_TONE[status]}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </StatusPill>
  );
}

// ---------------------------------------------------------------------------
// Prompt cell — single-line truncated preview; full text in expanded row
// ---------------------------------------------------------------------------

function PromptCell({ text }: { text: string }) {
  return (
    <span className="text-gray-300 text-sm truncate block max-w-[10rem]" title={text}>
      {text}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Extracted actions cell
// ---------------------------------------------------------------------------

interface ActionsCellProps {
  prompt: WorkflowScheduleResponse;
  expandedPromptId: string | null;
  onToggleExpand: (id: string) => void;
  onTrigger: (id: string) => void;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onEdit: (prompt: WorkflowScheduleResponse) => void;
  onDelete: (id: string) => void;
}

function ActionsCell({
  prompt,
  expandedPromptId,
  onToggleExpand,
  onTrigger,
  onPause,
  onResume,
  onEdit,
  onDelete,
}: ActionsCellProps) {
  const status = prompt.schedule_status as ScheduleStatus;
  const isExpanded = expandedPromptId === prompt.id;
  const name = prompt.blueprint_name ?? prompt.blueprint_id;

  return (
    <div className="flex items-center gap-1 justify-end">
      <SimpleTooltip content={<p>View details</p>}>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-gray-400 hover:text-white"
          onClick={() => onToggleExpand(prompt.id)}
          aria-label={`${isExpanded ? "Collapse" : "Expand"} details for ${name}`}
        >
          <Eye className={`w-3.5 h-3.5 ${isExpanded ? "text-primary" : ""}`} />
        </Button>
      </SimpleTooltip>

      {status === ScheduleStatus.Active && (
        <SimpleTooltip content={<p>Run now</p>}>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-gray-400 hover:text-emerald-400"
            onClick={() => onTrigger(prompt.id)}
            aria-label={`Trigger immediate run for ${name}`}
          >
            <Play className="w-3.5 h-3.5" />
          </Button>
        </SimpleTooltip>
      )}

      {status === ScheduleStatus.Active && (
        <SimpleTooltip content={<p>Pause</p>}>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-gray-400 hover:text-amber-400"
            onClick={() => onPause(prompt.id)}
            aria-label={`Pause schedule for ${name}`}
          >
            <Pause className="w-3.5 h-3.5" />
          </Button>
        </SimpleTooltip>
      )}

      {status === ScheduleStatus.Paused && (
        <SimpleTooltip content={<p>Resume</p>}>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-gray-400 hover:text-emerald-400"
            onClick={() => onResume(prompt.id)}
            aria-label={`Resume schedule for ${name}`}
          >
            <Play className="w-3.5 h-3.5" />
          </Button>
        </SimpleTooltip>
      )}

      <SimpleTooltip content={<p>Edit</p>}>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-gray-400 hover:text-white"
          onClick={() => onEdit(prompt)}
          aria-label={`Edit schedule for ${name}`}
        >
          <Pencil className="w-3.5 h-3.5" />
        </Button>
      </SimpleTooltip>

      <SimpleTooltip content={<p>Delete</p>}>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-gray-400 hover:text-red-400"
          onClick={() => onDelete(prompt.id)}
          aria-label={`Delete schedule for ${name}`}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </SimpleTooltip>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const QUERY_KEY_PREFIX = "scheduled-prompts" as const;

export default function ScheduledWorkflows() {
  const { teamId, userId } = useWorkspaceIdentity();
  const { toast } = useToast();
  const qc = useQueryClient();

  // Edit / create modal state
  const [editPrompt, setEditPrompt] = useState<WorkflowScheduleResponse | null>(null);
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [selectedBlueprint, setSelectedBlueprint] = useState<{ id: string; name: string } | null>(null);

  // Workflow picker state (AddFlowModal)
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedFlowForPicker, setSelectedFlowForPicker] = useState<FlowObject | null>(null);
  const scheduleCounts = useScheduledBlueprintCounts(teamId);
  const isPickerFlowAtLimit = selectedFlowForPicker
    ? (scheduleCounts.get(selectedFlowForPicker.id) ?? 0) >= MAX_ACTIVE_SCHEDULES_PER_WORKFLOW
    : false;

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const [expandedPromptId, setExpandedPromptId] = useState<string | null>(null);


  const scopeKey = teamId ?? userId;
  const queryKey = useMemo(
    () => [QUERY_KEY_PREFIX, scopeKey] as const,
    [scopeKey],
  );

  const { data: prompts = [], isLoading, isError, refetch } = useQuery<WorkflowScheduleResponse[]>({
    queryKey,
    queryFn: () => listSchedules(teamId),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const expandedPrompt = useMemo(
    () => prompts.find((p) => p.id === expandedPromptId) ?? null,
    [prompts, expandedPromptId],
  );

  const {
    data: resolvedSpec,
    isError: isResolvedSpecError,
    refetch: refetchResolvedSpec,
  } = useQuery({
    queryKey: ["resolved-blueprint", scopeKey, expandedPrompt?.blueprint_id],
    queryFn: () => fetchResolvedBlueprint(expandedPrompt!.blueprint_id, teamId),
    enabled: !!expandedPrompt,
    staleTime: 5 * 60_000,
  });

  const invalidate = useCallback(
    () => qc.invalidateQueries({ queryKey }),
    [qc, queryKey],
  );

  // Invalidate run history when the list poll detects a new run
  const expandedTotalRuns = expandedPrompt?.run_stats?.total_runs;
  useEffect(() => {
    if (expandedPromptId && expandedTotalRuns != null) {
      qc.invalidateQueries({ queryKey: ["prompt-runs", expandedPromptId] });
    }
  }, [expandedTotalRuns, expandedPromptId, qc]);

  // ---- Optimistic helper ----

  const optimisticUpdate = useCallback(
    (id: string, patch: Partial<WorkflowScheduleResponse>) => {
      qc.setQueryData<WorkflowScheduleResponse[]>(queryKey, (old) =>
        old?.map((p) => (p.id === id ? { ...p, ...patch } : p)),
      );
    },
    [qc, queryKey],
  );

  // ---- Actions with optimistic updates ----

  const handleTrigger = useCallback(
    async (id: string) => {
      try {
        await triggerSchedule(id, teamId);
        toast({ title: "Triggered", description: "Schedule run started" });
        invalidate();
      } catch {
        toast({ title: "Error", description: "Failed to trigger schedule", variant: "destructive" });
      }
    },
    [teamId, toast, invalidate],
  );

  const handlePause = useCallback(
    async (id: string) => {
      optimisticUpdate(id, { schedule_status: ScheduleStatus.Paused });
      try {
        await pauseSchedule(id, teamId);
        toast({ title: "Paused", description: "Schedule paused" });
        invalidate();
      } catch {
        toast({ title: "Error", description: "Failed to pause schedule", variant: "destructive" });
        invalidate();
      }
    },
    [teamId, toast, invalidate, optimisticUpdate],
  );

  const handleResume = useCallback(
    async (id: string) => {
      optimisticUpdate(id, { schedule_status: ScheduleStatus.Active });
      try {
        await resumeSchedule(id, teamId);
        toast({ title: "Resumed", description: "Schedule resumed" });
        invalidate();
      } catch {
        toast({ title: "Error", description: "Failed to resume schedule", variant: "destructive" });
        invalidate();
      }
    },
    [teamId, toast, invalidate, optimisticUpdate],
  );

  const handleDeleteConfirmed = useCallback(
    async () => {
      if (!deleteTarget) return;
      optimisticUpdate(deleteTarget, { schedule_status: ScheduleStatus.Completed });
      try {
        await deleteSchedule(deleteTarget, teamId);
        toast({ title: "Deleted", description: "Scheduled prompt removed" });
        invalidate();
      } catch {
        toast({ title: "Error", description: "Failed to delete schedule", variant: "destructive" });
        invalidate();
      } finally {
        setDeleteTarget(null);
      }
    },
    [deleteTarget, teamId, toast, invalidate, optimisticUpdate],
  );

  const handleEdit = useCallback((prompt: WorkflowScheduleResponse) => {
    setEditPrompt(prompt);
    setSelectedBlueprint({ id: prompt.blueprint_id, name: prompt.blueprint_name ?? prompt.blueprint_id });
    setScheduleModalOpen(true);
  }, []);

  const handleCreate = useCallback(() => {
    setPickerOpen(true);
  }, []);

  const handleFlowConfirm = useCallback(() => {
    if (!selectedFlowForPicker) return;
    setPickerOpen(false);
    setEditPrompt(null);
    setSelectedBlueprint({ id: selectedFlowForPicker.id, name: selectedFlowForPicker.name });
    setSelectedFlowForPicker(null);
    setScheduleModalOpen(true);
  }, [selectedFlowForPicker]);

  const handleFlowCancel = useCallback(() => {
    setPickerOpen(false);
    setSelectedFlowForPicker(null);
  }, []);

  const handleToggleExpand = useCallback((id: string) => {
    setExpandedPromptId((prev) => (prev === id ? null : id));
  }, []);

  const closeScheduleModal = useCallback((saved?: boolean) => {
    setScheduleModalOpen(false);
    setEditPrompt(null);
    setSelectedBlueprint(null);
    if (saved) invalidate();
  }, [invalidate]);

  // ---- DataTable column definitions ----

  const columns: DataTableColumn<WorkflowScheduleResponse>[] = useMemo(() => [
    {
      accessorFn: (row) => row.blueprint_name ?? row.blueprint_id,
      id: "workflow",
      header: "Workflow",
      cell: ({ getValue }) => (
        <span className="font-medium text-white">{getValue() as string}</span>
      ),
      meta: { align: "left" as const, filterType: "text" as const },
    },
    {
      accessorKey: "inputs.user_prompt",
      header: "Prompt",
      cell: ({ row }) => <PromptCell text={row.original.inputs.user_prompt} />,
      meta: { align: "left" as const, filterType: "text" as const },
    },
    {
      accessorFn: (row) => describeSchedule(row.schedule),
      id: "schedule",
      header: "Schedule",
      cell: ({ row }) => {
        const schedule = row.original.schedule;
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        return (
          <div className="leading-tight">
            <div className="text-sm">{describeSchedule(schedule)}</div>
            <div className="text-xs text-gray-500">{tz}</div>
            {schedule.interval && schedule.start_at && schedule.remaining_actions !== 1 && (
              <div className="text-xs text-gray-500">From {formatDateTime(schedule.start_at)}</div>
            )}
          </div>
        );
      },
      meta: { align: "left" as const },
      enableColumnFilter: false,
    },
    {
      accessorKey: "schedule_status",
      header: "Status",
      cell: ({ getValue }) => (
        <StatusBadge status={getValue() as ScheduleStatus} />
      ),
      meta: {
        align: "center" as const,
        filterType: "select" as const,
        filterOptions: Object.values(ScheduleStatus),
      },
    },
    {
      id: "runs",
      header: "Runs",
      enableColumnFilter: false,
      enableSorting: false,
      cell: ({ row }) => (
        <RunSparkline
          summary={row.original.run_stats}
          onExpand={() => handleToggleExpand(row.original.id)}
        />
      ),
      meta: { align: "left" as const },
    },
    {
      id: "actions",
      header: "",
      enableSorting: false,
      enableColumnFilter: false,
      cell: ({ row }) => (
        <ActionsCell
          prompt={row.original}
          expandedPromptId={expandedPromptId}
          onToggleExpand={handleToggleExpand}
          onTrigger={handleTrigger}
          onPause={handlePause}
          onResume={handleResume}
          onEdit={handleEdit}
          onDelete={setDeleteTarget}
        />
      ),
      meta: { align: "right" as const },
    },
  ], [handleTrigger, handlePause, handleResume, handleEdit, handleToggleExpand, expandedPromptId]);

  return (
    <>
      <Header title="Scheduled Workflows" onToggleSidebar={() => {}} />
      <main className="flex-1 overflow-y-auto bg-background-dark">
        <div className="flex-1 overflow-auto px-6 pb-6">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {/* Top toolbar */}
            <div className="flex items-center justify-between mt-6 mb-4">
              <div />
              <div className="flex items-center gap-3">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={invalidate}
                  className="text-gray-400 hover:text-white"
                  aria-label="Refresh scheduled workflows"
                >
                  <RotateCw className="w-4 h-4" />
                </Button>
                <Button onClick={handleCreate} aria-label="Create a new schedule">
                  <Plus className="w-4 h-4 mr-2" />
                  Create Schedule
                </Button>
              </div>
            </div>

            {isError ? (
              <div className="flex flex-col items-center justify-center py-20 text-gray-500">
                <Clock className="w-6 h-6 mb-3 text-red-400" />
                <p className="mb-2">Failed to load scheduled workflows</p>
                <Button variant="outline" size="sm" onClick={() => refetch()}>
                  <RotateCw className="w-3.5 h-3.5 mr-1.5" /> Retry
                </Button>
              </div>
            ) : isLoading ? (
              <div className="flex flex-col items-center justify-center py-20 text-gray-500">
                <Clock className="w-6 h-6 mb-3 animate-spin" />
                Loading scheduled workflows…
              </div>
            ) : (
              <DataTable
                columns={columns}
                data={prompts}
                enableGlobalFilter={false}
                enableColumnFilters={true}
                enablePagination={true}
                enableRowSelection={false}
                getRowId={(row) => row.id}
                initialState={{
                  pagination: { pageIndex: 0, pageSize: 15 },
                }}
                expendedRow={expandedPrompt}
                renderExpandedRow={(prompt) => (
                  <div className="py-4 space-y-4">
                    {/* Full prompt text */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Prompt</h4>
                        {prompt.schedule.start_at && (
                          <span className="text-xs text-gray-500">
                            Start: {formatDateTime(prompt.schedule.start_at)}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-300 whitespace-pre-wrap">{prompt.inputs.user_prompt}</p>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      <div>
                        <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Run History</h4>
                        <RunHistoryPanel
                          promptId={prompt.id}
                          teamId={teamId}
                        />
                      </div>
                      <div>
                        <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Workflow Graph</h4>
                        <div className="rounded-lg border border-gray-800 overflow-hidden" style={{ height: 300 }}>
                          {isResolvedSpecError ? (
                            <div className="flex flex-col items-center justify-center h-full text-gray-500">
                              <p className="text-sm mb-2">Failed to load workflow graph</p>
                              <Button variant="outline" size="sm" onClick={() => refetchResolvedSpec()}>
                                <RotateCw className="w-3.5 h-3.5 mr-1.5" /> Retry
                              </Button>
                            </div>
                          ) : (
                            <GraphDisplay
                              blueprintId={prompt.blueprint_id}
                              specDict={resolvedSpec?.spec_dict}
                              height="100%"
                              showBackground={false}
                              interactive={false}
                              centerInView
                            />
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              />
            )}
          </motion.div>
        </div>
      </main>
      <StatusBar />

      {/* Workflow picker for create flow */}
      <AddFlowModal
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        selectedFlow={selectedFlowForPicker}
        onFlowSelect={setSelectedFlowForPicker}
        isCreating={false}
        onConfirm={handleFlowConfirm}
        onCancel={handleFlowCancel}
        title="Select Workflow for Schedule"
        confirmLabel="Select"
        confirmDisabled={isPickerFlowAtLimit}
        confirmDisabledReason="This workflow has reached the maximum of 10 active schedules."
      />

      {/* Schedule prompt modal (create + edit) */}
      {scheduleModalOpen && selectedBlueprint && (
        <SchedulePromptModal
          isOpen={scheduleModalOpen}
          onClose={closeScheduleModal}
          blueprintId={selectedBlueprint.id}
          blueprintName={selectedBlueprint.name}
          teamId={teamId}
          editPrompt={editPrompt}
        />
      )}

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Scheduled Workflow"
        message="Are you sure you want to delete this scheduled workflow? This action cannot be undone."
        confirmLabel="Yes, Delete"
        cancelLabel="Cancel"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirmed}
      />
    </>
  );
}
