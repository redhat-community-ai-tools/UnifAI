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
  inputs: { user_prompt: string; [key: string]: any };
  source?: string;
  schedule: ScheduleDefinitionInput;
}

export interface UpdateScheduleInput {
  scheduleId: string;
  inputs?: { user_prompt?: string; [key: string]: any };
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
  inputs: { user_prompt: string; [key: string]: any };
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
  metadata: Record<string, any>;
}

/**
 * Map workspace hook fields to the "with_require_identity_authorization" decorator.
 * Team view: send teamId (userId from the hook is already the team UUID).
 * User view: omit — session cookie supplies the user identity.
 */
function workspaceScope(
  userId?: string,
  identityType?: string,
): { teamId?: string } {
  if (identityType === 'team' && userId) {
    return { teamId: userId };
  }
  return {};
}

function withWorkspaceScope<T extends Record<string, unknown>>(
  payload: T,
  userId?: string,
  identityType?: string,
): T & { teamId?: string } {
  return { ...payload, ...workspaceScope(userId, identityType) };
}

// ────────────────────────────────────────────────────────────────────────────────
// CRUD Operations
// ────────────────────────────────────────────────────────────────────────────────

export async function createSchedule(
  input: CreateScheduleInput,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.create',
    withWorkspaceScope({ ...input }, userId, identityType),
  );
  return data;
}

export async function updateSchedule(
  input: UpdateScheduleInput,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.update',
    withWorkspaceScope({ ...input }, userId, identityType),
  );
  return data;
}

export async function listSchedules(
  userId?: string,
  identityType?: string,
  blueprintId?: string,
): Promise<WorkflowScheduleResponse[]> {
  const params: Record<string, string> = {
    ...workspaceScope(userId, identityType),
  };
  if (blueprintId) params.blueprintId = blueprintId;
  const { data } = await axios.get('/schedules/schedule.list', { params });
  return data;
}

export async function getSchedule(
  scheduleId: string,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.get('/schedules/schedule.get', {
    params: {
      scheduleId,
      ...workspaceScope(userId, identityType),
    },
  });
  return data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Schedule Lifecycle
// ────────────────────────────────────────────────────────────────────────────────

export async function pauseSchedule(
  scheduleId: string,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.pause',
    withWorkspaceScope({ scheduleId }, userId, identityType),
  );
  return data;
}

export async function resumeSchedule(
  scheduleId: string,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.resume',
    withWorkspaceScope({ scheduleId }, userId, identityType),
  );
  return data;
}

export async function triggerSchedule(
  scheduleId: string,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post(
    '/schedules/schedule.trigger',
    withWorkspaceScope({ scheduleId }, userId, identityType),
  );
  return data;
}

export async function deleteSchedule(
  scheduleId: string,
  userId?: string,
  identityType?: string,
): Promise<{ deleted: boolean }> {
  const { data } = await axios.delete('/schedules/schedule.delete', {
    data: withWorkspaceScope({ scheduleId }, userId, identityType),
  });
  return data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Schedule Runs (session history for a workflow schedule)
// ────────────────────────────────────────────────────────────────────────────────

export async function getScheduleRuns(
  scheduleId: string,
  userId?: string,
  identityType?: string,
  limit?: number,
): Promise<ScheduleRunResponse[]> {
  const params: Record<string, string | number> = {
    scheduleId,
    ...workspaceScope(userId, identityType),
  };
  if (limit) params.limit = limit;
  const { data } = await axios.get('/schedules/schedule.runs', { params });
  return data;
}
