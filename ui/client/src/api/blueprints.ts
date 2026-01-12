import axios from '@/http/axiosAgentConfig';
import { BlueprintValidationResult, BlueprintValidationRequest } from '@/types/validation';

// ────────────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────────────

export interface WorkflowBlueprint {
  blueprint_id: string;
  spec_dict: any;
  name?: string;
  created_at?: string;
  updated_at?: string;
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
export async function fetchBlueprints(userId?: string): Promise<WorkflowBlueprint[]> {
  const userIdParam = userId || 'default';
  const response = await axios.get(`/blueprints/available.blueprints.get?userId=${userIdParam}`);
  return response.data || [];
}

/**
 * Fetch resolved blueprints (with all references resolved)
 */
export async function fetchResolvedBlueprints(userId?: string): Promise<WorkflowBlueprint[]> {
  const userIdParam = userId || 'default';
  const response = await axios.get(`/blueprints/available.blueprints.resolved.get?userId=${userIdParam}`);
  return response.data || [];
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
  userId: string
): Promise<SaveBlueprintResponse> {
  const { data } = await axios.post<SaveBlueprintResponse>('/blueprints/blueprint.save', {
    blueprintRaw,
    userId,
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
