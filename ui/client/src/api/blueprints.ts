import axios from '@/http/axiosAgentConfig';
import { BlueprintValidationResult, BlueprintValidationRequest } from '@/types/validation';

// ────────────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────────────

export interface WorkflowBlueprint {
  blueprint_id: string;
  user_id?: string;
  spec_dict: any;
  name?: string;
  created_at?: string;
  updated_at?: string;
  rid_refs?: string[];
  metadata?: {
    usageScope?: "public" | "private";
    [key: string]: any;
  };
}

/**
 * Lightweight blueprint summary without spec_dict or rid_refs.
 * Used for listing blueprints without loading the full spec data.
 */
export interface BlueprintSummary {
  blueprint_id: string;
  user_id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  metadata: {
    usageScope?: "public" | "private";
    [key: string]: any;
  };
}

export interface BlueprintInfoResponse {
  blueprint_id: string;
  user_id: string;
  spec_dict: {
    name: string;
    [key: string]: any;
  };
  metadata: {
    usageScope?: "public" | "private";
    [key: string]: any;
  };
}

export interface SetMetadataResponse {
  status: string;
}

export interface DeleteBlueprintResponse {
  status: string;
}

export interface SaveBlueprintResponse {
  status: string;
  blueprint_id: string;
}

// ────────────────────────────────────────────────────────────────────────────────
// Blueprint CRUD Operations
// ────────────────────────────────────────────────────────────────────────────────

/**
 * Fetch available blueprints for a user
 */
export async function fetchBlueprints(teamId?: string): Promise<WorkflowBlueprint[]> {
  const query = new URLSearchParams();
  if (teamId) query.set('teamId', teamId);
  const qs = query.toString();
  const response = await axios.get(
    `/blueprints/available.blueprints.get${qs ? `?${qs}` : ''}`
  );
  return response.data || [];
}

/**
 * Fetch lightweight blueprint summaries (name, description, metadata only - no spec_dict).
 * Use this for listing blueprints when the full spec is not needed.
 */
export async function fetchBlueprintSummaries(teamId?: string): Promise<BlueprintSummary[]> {
  const query = new URLSearchParams();
  if (teamId) query.set('teamId', teamId);
  const qs = query.toString();
  const response = await axios.get<BlueprintSummary[]>(
    `/blueprints/available.blueprints.summary.get${qs ? `?${qs}` : ''}`
  );
  return response.data || [];
}

/**
 * Paginated response for resolved blueprints list
 */
export interface ResolvedBlueprintsResponse {
  items: WorkflowBlueprint[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * Fetch resolved blueprints (with all references resolved) - paginated list
 */
export async function fetchResolvedBlueprints(teamId?: string): Promise<WorkflowBlueprint[]> {
  const query = new URLSearchParams();
  if (teamId) query.set('teamId', teamId);
  const qs = query.toString();
  const response = await axios.get<ResolvedBlueprintsResponse>(
    `/blueprints/available.blueprints.resolved.get${qs ? `?${qs}` : ''}`
  );
  return response.data?.items || [];
}

/**
 * Fetch a single resolved blueprint by ID (with all references resolved).
 */
export async function fetchResolvedBlueprint(
  blueprintId: string,
  teamId?: string,
): Promise<WorkflowBlueprint | null> {
  const params = new URLSearchParams({ blueprintId });
  if (teamId) params.set('teamId', teamId);
  const response = await axios.get<WorkflowBlueprint>(
    `/blueprints/available.blueprints.resolved.get?${params.toString()}`
  );
  // Single blueprint mode returns flat document object (not wrapped in items)
  return response.data || null;
}

/**
 * Get blueprint information including metadata
 */
export async function getBlueprintInfo(blueprintId: string): Promise<BlueprintInfoResponse> {
  const { data } = await axios.get<BlueprintInfoResponse>('/blueprints/blueprint.info.get', {
    params: { blueprintId },
  });
  return data;
}

/**
 * Delete a blueprint by ID
 */
export async function deleteBlueprint(blueprintId: string): Promise<DeleteBlueprintResponse> {
  const { data } = await axios.delete<DeleteBlueprintResponse>('/blueprints/remove.blueprint', {
    params: { blueprintId },
  });
  return data;
}

/** Delete multiple blueprints (sequential API calls; fails fast on first error). */
export async function deleteBlueprintsByIds(blueprintIds: string[]): Promise<void> {
  for (const id of blueprintIds) {
    await deleteBlueprint(id);
  }
}

/**
 * Save a new blueprint
 */
export async function saveBlueprint(
  blueprintRaw: string,
  teamId?: string,
): Promise<SaveBlueprintResponse> {
  const body: Record<string, any> = { blueprintRaw };
  if (teamId) body.teamId = teamId;
  const { data } = await axios.post<SaveBlueprintResponse>('/blueprints/blueprint.save', body);
  return data;
}

/**
 * Update an existing blueprint in-place (keeps the same ID)
 */
export async function updateBlueprint(
  blueprintId: string,
  blueprintRaw: string,
  teamId?: string,
): Promise<SaveBlueprintResponse> {
  const body: Record<string, any> = { blueprintId, blueprintRaw };
  if (teamId) body.teamId = teamId;
  const { data } = await axios.put<SaveBlueprintResponse>('/blueprints/blueprint.update', body);
  return data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Blueprint Metadata & Sharing
// ────────────────────────────────────────────────────────────────────────────────

/**
 * Set metadata for a blueprint (including sharing settings)
 */
export async function setBlueprintMetadata(
  blueprintId: string,
  metadata: { usageScope?: "public" | "private"; [key: string]: any },
  userId: string
): Promise<SetMetadataResponse> {
  const { data } = await axios.put<SetMetadataResponse>('/blueprints/blueprint.metadata.set', {
    blueprintId,
    metadata,
    userId,
  });
  return data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Blueprint Validation
// ────────────────────────────────────────────────────────────────────────────────

/**
 * Validate a saved blueprint and all its elements
 */
export async function validateBlueprint(request: BlueprintValidationRequest): Promise<BlueprintValidationResult> {
  const body: Record<string, any> = {
    blueprintId: request.blueprintId,
    timeoutSeconds: request.timeoutSeconds ?? 10.0,
  };
  if (request.teamId) body.teamId = request.teamId;
  const response = await axios.post('/blueprints/blueprint.validate', body);
  return response.data;
}

/**
 * Validate a blueprint draft before saving
 */
export async function validateDraft(
  draft: string,
  timeoutSeconds: number = 10.0
): Promise<BlueprintValidationResult> {
  const response = await axios.post('/blueprints/draft.validate', {
    draft,
    timeoutSeconds,
  });
  return response.data;
}

/**
 * Get the JSON schema for blueprint drafts
 */
export async function getBlueprintDraftSchema(): Promise<any> {
  const response = await axios.get('/blueprints/blueprint.draft.schema.get');
  return response.data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Prompt Shortcuts
// ────────────────────────────────────────────────────────────────────────────────

export interface PromptShortcutInput {
  id?: string;
  text: string;
}

export interface PromptShortcut {
  id: string;
  text: string;
}

/**
 * Set prompt shortcuts for a blueprint (replaces all existing shortcuts)
 */
export async function setPromptShortcuts(
  blueprintId: string,
  prompts: PromptShortcutInput[],
  teamId?: string,
): Promise<{ prompts: PromptShortcut[] }> {
  const body: Record<string, any> = { blueprintId, prompts };
  if (teamId) body.teamId = teamId;
  const { data } = await axios.put('/blueprints/blueprint.prompt-shortcuts.set', body);
  return data;
}

/**
 * Get prompt shortcuts for a blueprint
 */
export async function getPromptShortcuts(
  blueprintId: string,
  teamId?: string,
): Promise<{ prompts: PromptShortcut[] }> {
  const params: Record<string, string> = { blueprintId };
  if (teamId) params.teamId = teamId;
  const { data } = await axios.get('/blueprints/blueprint.prompt-shortcuts.get', { params });
  return data;
}
