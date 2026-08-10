import axios from '@/http/axiosAgentConfig';

// ────────────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────────────

export interface ScheduleDefinitionInput {
  interval?: string;
  cron_expression?: string;
  overlap_policy?: string;
  timezone?: string;
  start_at?: string;
  end_at?: string | null;
  remaining_actions?: number | null;
}

export interface CreateScheduleInput {
  blueprintId: string;
  inputs: { user_prompt: string } & Record<string, unknown>;
  source?: string;
  schedule: ScheduleDefinitionInput;
}

export interface UpdateScheduleInput {
  scheduleId: string;
  inputs?: { user_prompt?: string } & Record<string, unknown>;
  schedule?: ScheduleDefinitionInput;
}

export interface RunStatusEntry {
  session_id: string;
  status: string;
  started_at?: string;
}

export interface RunStats {
  total_runs: number;
  last_run_at?: string | null;
  recent_statuses: RunStatusEntry[];
}

export interface WorkflowScheduleResponse {
  id: string;
  blueprint_id: string;
  blueprint_name?: string;
  identity: { type: string; id: string; display_name: string };
  inputs: { user_prompt: string } & Record<string, unknown>;
  source: string;
  schedule: ScheduleDefinitionInput;
  schedule_status: string;
  engine_handle?: string;
  completed_at?: string;
  run_stats: RunStats;
}

export interface ScheduleRunResponse {
  session_id: string;
  status: string;
  started_at: string;
  metadata: Record<string, unknown>;
}

function withTeamScope<T extends Record<string, unknown>>(
  payload: T,
  teamId?: string,
): T & { teamId?: string } {
  if (teamId) return { ...payload, teamId };
  return payload;
}

// ────────────────────────────────────────────────────────────────────────────────
// CRUD Operations
// ────────────────────────────────────────────────────────────────────────────────

export async function createSchedule(
  input: CreateScheduleInput,
  teamId?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.create',
    withTeamScope({ ...input }, teamId),
  );
  return data;
}

export async function updateSchedule(
  input: UpdateScheduleInput,
  teamId?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.update',
    withTeamScope({ ...input }, teamId),
  );
  return data;
}

export async function listSchedules(
  teamId?: string,
  blueprintId?: string,
): Promise<WorkflowScheduleResponse[]> {
  const params: Record<string, string> = {};
  if (teamId) params.teamId = teamId;
  if (blueprintId) params.blueprintId = blueprintId;
  const { data } = await axios.get('/schedules/schedule.list', { params });
  return data;
}

export async function getSchedule(
  scheduleId: string,
  teamId?: string,
): Promise<WorkflowScheduleResponse> {
  const params: Record<string, string> = { scheduleId };
  if (teamId) params.teamId = teamId;
  const { data } = await axios.get('/schedules/schedule.get', { params });
  return data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Schedule Lifecycle
// ────────────────────────────────────────────────────────────────────────────────

export async function pauseSchedule(
  scheduleId: string,
  teamId?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.pause',
    withTeamScope({ scheduleId }, teamId),
  );
  return data;
}

export async function resumeSchedule(
  scheduleId: string,
  teamId?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.resume',
    withTeamScope({ scheduleId }, teamId),
  );
  return data;
}

export async function triggerSchedule(
  scheduleId: string,
  teamId?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.trigger',
    withTeamScope({ scheduleId }, teamId),
  );
  return data;
}

export async function deleteSchedule(
  scheduleId: string,
  teamId?: string,
): Promise<{ deleted: boolean }> {
  const { data } = await axios.delete('/schedules/schedule.delete', {
    data: withTeamScope({ scheduleId }, teamId),
  });
  return data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Schedule Runs (session history for a workflow schedule)
// ────────────────────────────────────────────────────────────────────────────────

export async function getScheduleRuns(
  scheduleId: string,
  teamId?: string,
  limit?: number,
): Promise<ScheduleRunResponse[]> {
  const params: Record<string, string | number> = { scheduleId };
  if (teamId) params.teamId = teamId;
  if (limit) params.limit = limit;
  const { data } = await axios.get('/schedules/schedule.runs', { params });
  return data;
}
