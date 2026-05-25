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
export async function fetchBlueprints(userId?: string, identityType?: string): Promise<WorkflowBlueprint[]> {
  const userIdParam = userId || 'default';
  const idType = identityType || 'user';
  const response = await axios.get(
    `/blueprints/available.blueprints.get?userId=${userIdParam}&identityType=${idType}`
  );
  return response.data || [];
}

/**
 * Fetch lightweight blueprint summaries (name, description, metadata only - no spec_dict).
 * Use this for listing blueprints when the full spec is not needed.
 */
export async function fetchBlueprintSummaries(userId?: string, identityType?: string): Promise<BlueprintSummary[]> {
  const userIdParam = userId || 'default';
  const idType = identityType || 'user';
  const response = await axios.get<BlueprintSummary[]>(
    `/blueprints/available.blueprints.summary.get?userId=${userIdParam}&identityType=${idType}`
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
export async function fetchResolvedBlueprints(userId?: string, identityType?: string): Promise<WorkflowBlueprint[]> {
  const userIdParam = userId || 'default';
  const idType = identityType || 'user';
  const response = await axios.get<ResolvedBlueprintsResponse>(
    `/blueprints/available.blueprints.resolved.get?userId=${userIdParam}&identityType=${idType}`
  );
  return response.data?.items || [];
}

/**
 * Fetch a single resolved blueprint by ID (with all references resolved).
 * For team workspace, pass the team id as `userId`, `identityType: "team"`, and
 * optional `displayName` (team name) so auth matches `require_identity_authorization`.
 */
export async function fetchResolvedBlueprint(
  blueprintId: string,
  userId?: string,
  identityType?: string,
  displayName?: string,
): Promise<WorkflowBlueprint | null> {
  const userIdParam = userId || 'default';
  const idType = identityType || 'user';
  const params = new URLSearchParams({
    userId: userIdParam,
    blueprintId,
    identityType: idType,
  });
  if (displayName) {
    params.set('displayName', displayName);
  }
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

/**
 * Save a new blueprint
 */
export async function saveBlueprint(
  blueprintRaw: string,
  userId: string,
  displayName: string,
  identityType?: string,
): Promise<SaveBlueprintResponse> {
  const { data } = await axios.post<SaveBlueprintResponse>('/blueprints/blueprint.save', {
    blueprintRaw,
    userId,
    displayName,
    identityType: identityType || 'user',
  });
  return data;
}

/**
 * Update an existing blueprint in-place (keeps the same ID)
 */
export async function updateBlueprint(
  blueprintId: string,
  blueprintRaw: string,
): Promise<SaveBlueprintResponse> {
  const { data } = await axios.put<SaveBlueprintResponse>('/blueprints/blueprint.update', {
    blueprintId,
    blueprintRaw,
  });
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
  const response = await axios.post('/blueprints/blueprint.validate', {
    blueprintId: request.blueprintId,
    userId: request.userId,
    timeoutSeconds: request.timeoutSeconds ?? 10.0,
  });
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
