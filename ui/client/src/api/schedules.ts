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
  text: string;
  inputs?: Record<string, any>;
  source?: string;
  schedule: ScheduleDefinitionInput;
}

export interface UpdateScheduleInput {
  scheduleId: string;
  text?: string;
  inputs?: Record<string, any>;
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

export interface Prompt {
  text: string;
}

export interface WorkflowScheduleResponse {
  id: string;
  prompt: Prompt;
  blueprint_id: string;
  blueprint_name?: string;
  identity: { type: string; id: string; display_name: string };
  inputs: Record<string, any>;
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

// ────────────────────────────────────────────────────────────────────────────────
// CRUD Operations
// ────────────────────────────────────────────────────────────────────────────────

export async function createSchedule(
  input: CreateScheduleInput,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post('/schedules/schedule.create', {
    ...input,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function updateSchedule(
  input: UpdateScheduleInput,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post('/schedules/schedule.update', {
    ...input,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function listSchedules(
  userId?: string,
  identityType?: string,
  blueprintId?: string,
): Promise<WorkflowScheduleResponse[]> {
  const params: Record<string, string> = {
    userId: userId || 'default',
    identityType: identityType || 'user',
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
      userId: userId || 'default',
      identityType: identityType || 'user',
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
  const { data } = await axios.post('/schedules/schedule.pause', {
    scheduleId,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function resumeSchedule(
  scheduleId: string,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post('/schedules/schedule.resume', {
    scheduleId,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function triggerSchedule(
  scheduleId: string,
  userId?: string,
  identityType?: string,
): Promise<WorkflowScheduleResponse> {
  const { data } = await axios.post('/schedules/schedule.trigger', {
    scheduleId,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function deleteSchedule(
  scheduleId: string,
  userId?: string,
  identityType?: string,
): Promise<{ deleted: boolean }> {
  const { data } = await axios.delete('/schedules/schedule.delete', {
    data: {
      scheduleId,
      userId: userId || 'default',
      identityType: identityType || 'user',
    },
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
    userId: userId || 'default',
    identityType: identityType || 'user',
  };
  if (limit) params.limit = limit;
  const { data } = await axios.get('/schedules/schedule.runs', { params });
  return data;
}
