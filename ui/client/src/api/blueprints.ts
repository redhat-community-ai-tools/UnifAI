/**
 * Blueprint API Client
 *
 * Typed HTTP client for all blueprint endpoints.
 * Version-history methods were added in GENIE-1336.
 *
 * All functions throw a {@link BlueprintApiError} (extending `Error`) when the
 * server returns a non-2xx response so callers can distinguish API failures
 * from network errors.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Identity {
  type: "user" | "team";
  id: string;
}

/** Lightweight blueprint listing item. */
export interface BlueprintSummary {
  blueprint_id: string;
  identity: Identity;
  name: string;
  description: string;
  created_at: string; // ISO-8601
  updated_at: string; // ISO-8601
  metadata: Record<string, unknown>;
  version: number;
}

/** Full blueprint document as returned by read endpoints. */
export interface BlueprintDocument {
  blueprint_id: string;
  identity: Identity;
  created_at: string;
  updated_at: string;
  spec_dict: Record<string, unknown>;
  rid_refs: string[];
  metadata: Record<string, unknown>;
  version: number;
}

/** Summary row in the version-history list (no spec_dict_snapshot). */
export interface BlueprintVersionSummary {
  version: number;
  blueprint_id: string;
  created_by: string;
  created_at: string; // ISO-8601
  change_summary: string | null;
}

/** Full version detail including the spec snapshot (single-version fetch). */
export interface BlueprintVersionDetail extends BlueprintVersionSummary {
  spec_dict_snapshot: Record<string, unknown>;
}

/** Paginated response wrapper for version lists. */
export interface PaginatedVersionsResponse {
  items: BlueprintVersionSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** Paginated response wrapper for blueprint lists. */
export interface PaginatedBlueprintsResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class BlueprintApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly endpoint: string,
  ) {
    super(`[${status}] ${endpoint}: ${message}`);
    this.name = "BlueprintApiError";
  }
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Base URL for all blueprint API calls.  Override via environment variable. */
const BASE_URL =
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "";

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

type ApiEnvelope<T> = { success: true; data: T } | { success: false; error: string };

async function _request<T>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);

  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const init: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  const response = await fetch(url.toString(), init);
  const envelope: ApiEnvelope<T> = await response.json();

  if (!response.ok || !envelope.success) {
    const message = (envelope as { success: false; error: string }).error ?? "Unknown error";
    throw new BlueprintApiError(response.status, message, path);
  }

  return (envelope as { success: true; data: T }).data;
}

// ---------------------------------------------------------------------------
// Blueprint CRUD
// ---------------------------------------------------------------------------

/** Save a new blueprint. Returns the generated `blueprint_id`. */
export async function saveBlueprint(
  identity: Identity,
  specDict: Record<string, unknown>,
  metadata?: Record<string, unknown>,
): Promise<string> {
  const data = await _request<{ blueprint_id: string }>("POST", "/blueprint.save", {
    identity,
    spec_dict: specDict,
    metadata: metadata ?? {},
  });
  return data.blueprint_id;
}

/**
 * Update an existing blueprint's spec.
 *
 * Returns 409 (ConcurrentModificationError) if another writer raced ahead.
 * In that case the caller should re-fetch the blueprint and retry.
 */
export async function updateBlueprint(
  blueprintId: string,
  specDict: Record<string, unknown>,
  changeSummary?: string,
): Promise<void> {
  await _request("PUT", "/blueprint.update", {
    blueprint_id: blueprintId,
    spec_dict: specDict,
    change_summary: changeSummary ?? null,
  });
}

/** Return the full `BlueprintDocument` for the given ID. */
export async function getBlueprintById(blueprintId: string): Promise<BlueprintDocument> {
  return _request<BlueprintDocument>("GET", "/blueprint.info.get", undefined, {
    blueprint_id: blueprintId,
  });
}

/** Return a paginated list of lightweight `BlueprintSummary` objects. */
export async function listBlueprintSummaries(
  identity?: Identity,
  skip = 0,
  limit = 20,
): Promise<PaginatedBlueprintsResponse<BlueprintSummary>> {
  return _request<PaginatedBlueprintsResponse<BlueprintSummary>>(
    "GET",
    "/available.blueprints.summary.get",
    undefined,
    {
      identity_type: identity?.type,
      identity_id: identity?.id,
      skip,
      limit,
    },
  );
}

/** Delete a blueprint by ID. */
export async function deleteBlueprint(blueprintId: string): Promise<void> {
  await _request("DELETE", "/remove.blueprint", undefined, {
    blueprint_id: blueprintId,
  });
}

// ---------------------------------------------------------------------------
// Version-history API  (GENIE-1336)
// ---------------------------------------------------------------------------

/**
 * List version summaries for a blueprint, sorted newest-first.
 *
 * @param blueprintId - Target blueprint.
 * @param page - 1-based page number (default 1).
 * @param pageSize - Items per page (1–100, default 20).
 *
 * @throws BlueprintApiError on 404 (blueprint not found) or 501 (feature
 *   not configured on the server).
 */
export async function listBlueprintVersions(
  blueprintId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedVersionsResponse> {
  return _request<PaginatedVersionsResponse>(
    "GET",
    "/blueprint.versions.list",
    undefined,
    {
      blueprint_id: blueprintId,
      page,
      page_size: pageSize,
    },
  );
}

/**
 * Load the full detail of a specific blueprint version, including its
 * `spec_dict_snapshot`.
 *
 * @param blueprintId - Parent blueprint.
 * @param version - Version number (≥ 1).
 *
 * @throws BlueprintApiError on 404 if the version does not exist.
 */
export async function getBlueprintVersion(
  blueprintId: string,
  version: number,
): Promise<BlueprintVersionDetail> {
  return _request<BlueprintVersionDetail>(
    "GET",
    "/blueprint.version.get",
    undefined,
    {
      blueprint_id: blueprintId,
      version,
    },
  );
}

/**
 * Restore a blueprint to the `spec_dict` captured at `targetVersion`.
 *
 * The current live state is snapshotted before the restore so no history
 * is lost.  The restore itself is reversible via another call to this
 * function.
 *
 * @param blueprintId - Target blueprint.
 * @param targetVersion - The version to restore to.
 *
 * @throws BlueprintApiError on:
 *   - 404 — blueprint or version not found.
 *   - 409 — concurrent modification conflict (re-fetch and retry).
 *   - 501 — versioning feature not configured on the server.
 */
export async function restoreBlueprintVersion(
  blueprintId: string,
  targetVersion: number,
): Promise<{ blueprint_id: string; restored_from_version: number; message: string }> {
  return _request<{ blueprint_id: string; restored_from_version: number; message: string }>(
    "POST",
    "/blueprint.version.restore",
    {
      blueprint_id: blueprintId,
      version: targetVersion,
    },
  );
}
