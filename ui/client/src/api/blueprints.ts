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

// ────────────────────────────────────────────────────────────────────────────────
// Blueprint Version History — GENIE-1336
// ────────────────────────────────────────────────────────────────────────────────

/**
 * Lightweight summary of a single blueprint version.
 * Returned by the list endpoint — does NOT include the full spec snapshot.
 */
export interface VersionSummary {
  /** Monotonically incrementing version counter (1-based). */
  version: number;
  /** User ID of the author who created this version. */
  created_by: string;
  /** ISO-8601 timestamp when this version snapshot was created. */
  created_at: string;
  /** Optional human-readable description of the change. Null when absent. */
  change_summary: string | null;
}

/**
 * Full version detail including the complete spec snapshot.
 * Returned by the single-version-get endpoint.
 */
export interface VersionDetail extends VersionSummary {
  /** Parent blueprint identifier. */
  blueprint_id: string;
  /** Complete spec_dict as it was at this version. */
  spec_dict_snapshot: Record<string, unknown>;
}

/**
 * Paginated list of version summaries returned by `listBlueprintVersions`.
 */
export interface VersionListResponse {
  /** Version summaries for the current page (newest first). */
  items: VersionSummary[];
  /** Total number of versions across all pages. */
  total: number;
  /** 1-based current page number. */
  page: number;
  /** Items per page. */
  page_size: number;
  /** Total number of pages. */
  total_pages: number;
}

/**
 * Fetch a paginated list of version summaries for a blueprint.
 *
 * Summaries are sorted newest-first and do not include the full spec snapshot.
 * Call `loadBlueprintVersion` to retrieve the complete snapshot for a
 * specific version.
 *
 * @param blueprintId - Target blueprint ID.
 * @param page        - 1-based page number (defaults to 1).
 * @param pageSize    - Items per page, 1–100 (defaults to 20).
 */
export async function listBlueprintVersions(
  blueprintId: string,
  page: number = 1,
  pageSize: number = 20,
): Promise<VersionListResponse> {
  const { data } = await axios.get<VersionListResponse>(
    '/blueprints/blueprint.versions.list',
    { params: { blueprintId, page, pageSize } },
  );
  return data;
}

/**
 * Fetch a specific historic version with the full `spec_dict_snapshot`.
 *
 * @param blueprintId   - Target blueprint ID.
 * @param versionNumber - The exact version number to retrieve.
 * @throws AxiosError (404) when the blueprint or version does not exist.
 */
export async function loadBlueprintVersion(
  blueprintId: string,
  versionNumber: number,
): Promise<VersionDetail> {
  const { data } = await axios.get<VersionDetail>(
    '/blueprints/blueprint.version.get',
    { params: { blueprintId, version: versionNumber } },
  );
  return data;
}

/**
 * Restore a blueprint to a historic version snapshot.
 *
 * The server snapshots the current live state before applying the restore,
 * so no history is lost.  The restored content becomes the new live version
 * with an incremented version counter.
 *
 * @param blueprintId   - Target blueprint ID.
 * @param versionNumber - Historic version number to restore.
 * @throws AxiosError (404) when the blueprint or version does not exist.
 * @throws AxiosError (409) on concurrent modification — ask the user to retry.
 */
export async function restoreBlueprintVersion(
  blueprintId: string,
  versionNumber: number,
): Promise<{ status: string; blueprint_id: string; restored_to_version: number }> {
  const { data } = await axios.post('/blueprints/blueprint.version.restore', {
    blueprintId,
    version: versionNumber,
  });
  return data;
}
