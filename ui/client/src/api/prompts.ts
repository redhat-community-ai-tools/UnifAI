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
  end_at?: string;
  remaining_actions?: number;
}

export interface CreatePromptInput {
  blueprintId: string;
  text: string;
  inputs?: Record<string, any>;
  source?: string;
  schedule: ScheduleDefinitionInput;
}

export interface UpdatePromptInput {
  promptId: string;
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

export interface ScheduledPromptResponse {
  id: string;
  blueprint_id: string;
  blueprint_name?: string;
  identity: { type: string; id: string; display_name: string };
  text: string;
  inputs: Record<string, any>;
  source: string;
  schedule: ScheduleDefinitionInput;
  schedule_status: string;
  temporal_schedule_id?: string;
  completed_at?: string;
  run_stats: RunStats;
}

export interface PromptRunResponse {
  session_id: string;
  status: string;
  started_at: string;
  metadata: Record<string, any>;
}

// ────────────────────────────────────────────────────────────────────────────────
// CRUD Operations
// ────────────────────────────────────────────────────────────────────────────────

export async function createScheduledPrompt(
  input: CreatePromptInput,
  userId?: string,
  identityType?: string,
): Promise<ScheduledPromptResponse> {
  const { data } = await axios.post('/prompts/prompt.create', {
    ...input,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function updateScheduledPrompt(
  input: UpdatePromptInput,
  userId?: string,
  identityType?: string,
): Promise<ScheduledPromptResponse> {
  const { data } = await axios.post('/prompts/prompt.update', {
    ...input,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function listScheduledPrompts(
  userId?: string,
  identityType?: string,
  blueprintId?: string,
): Promise<ScheduledPromptResponse[]> {
  const params: Record<string, string> = {
    userId: userId || 'default',
    identityType: identityType || 'user',
  };
  if (blueprintId) params.blueprintId = blueprintId;
  const { data } = await axios.get('/prompts/prompt.list', { params });
  return data;
}

export async function getScheduledPrompt(
  promptId: string,
  userId?: string,
  identityType?: string,
): Promise<ScheduledPromptResponse> {
  const { data } = await axios.get('/prompts/prompt.get', {
    params: {
      promptId,
      userId: userId || 'default',
      identityType: identityType || 'user',
    },
  });
  return data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Schedule Lifecycle
// ────────────────────────────────────────────────────────────────────────────────

export async function pausePromptSchedule(
  promptId: string,
  userId?: string,
  identityType?: string,
): Promise<ScheduledPromptResponse> {
  const { data } = await axios.post('/prompts/prompt.schedule.pause', {
    promptId,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function resumePromptSchedule(
  promptId: string,
  userId?: string,
  identityType?: string,
): Promise<ScheduledPromptResponse> {
  const { data } = await axios.post('/prompts/prompt.schedule.resume', {
    promptId,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function triggerPromptSchedule(
  promptId: string,
  userId?: string,
  identityType?: string,
): Promise<ScheduledPromptResponse> {
  const { data } = await axios.post('/prompts/prompt.schedule.trigger', {
    promptId,
    userId: userId || 'default',
    identityType: identityType || 'user',
  });
  return data;
}

export async function deleteScheduledPrompt(
  promptId: string,
  userId?: string,
  identityType?: string,
): Promise<{ deleted: boolean }> {
  const { data } = await axios.delete('/prompts/prompt.delete', {
    data: {
      promptId,
      userId: userId || 'default',
      identityType: identityType || 'user',
    },
  });
  return data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Prompt Runs (session history for a scheduled prompt)
// ────────────────────────────────────────────────────────────────────────────────

export async function getPromptRuns(
  promptId: string,
  userId?: string,
  identityType?: string,
  limit?: number,
): Promise<PromptRunResponse[]> {
  const params: Record<string, string | number> = {
    promptId,
    userId: userId || 'default',
    identityType: identityType || 'user',
  };
  if (limit) params.limit = limit;
  const { data } = await axios.get('/prompts/prompt.runs', { params });
  return data;
}
