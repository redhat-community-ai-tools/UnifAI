/**
 * Blueprint API Client
 *
 * Typed HTTP client for all blueprint CRUD + version-history endpoints.
 * Version-history methods were added in GENIE-1336.
 *
 * Uses the shared ``axiosAgentConfig`` Axios instance which:
 * - pre-configures the ``/api2`` base URL for Vite / Nginx proxy routing
 * - auto-injects the ``X-Authenticated-User`` header via interceptor
 *
 * This follows the same pattern as all other UI API modules
 * (sessions.ts, templates.ts, shares.ts, catalog.ts).
 *
 * Route names match the Flask blueprint endpoints exactly:
 *   /blueprint.save           → POST  (create)
 *   /blueprint.update         → PUT   (update with OCC)
 *   /blueprint.info.get       → GET   (read one)
 *   /remove.blueprint         → DELETE
 *   /available.blueprints.summary.get → GET (list)
 *   /blueprint.versions.list  → GET   (version list, GENIE-1336)
 *   /blueprint.version.get    → GET   (version detail, GENIE-1336)
 *   /blueprint.version.restore → POST (restore, GENIE-1336)
 */

import axios from "@/http/axiosAgentConfig";
import { isAxiosError } from "axios";

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

/**
 * Identity matches the backend ``Identity`` Pydantic model:
 * ``{"type": "user"|"team", "id": "<owner_id>"}``.
 */
export interface Identity {
  type: string;
  id: string;
}

// ---- Blueprint types ----

export interface BlueprintSummary {
  blueprint_id: string;
  identity: Identity;
  spec_dict: Record<string, unknown>;
  rid_refs: string[];
  metadata: Record<string, unknown>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface BlueprintDocument extends BlueprintSummary {
  // BlueprintDocument and BlueprintSummary currently share the same shape
  // because the list endpoint returns full model_dump() results.
}

export interface PaginatedBlueprintsResponse {
  items: BlueprintSummary[];
  total: number;
  skip: number;
  limit: number;
}

// ---- Version types (GENIE-1336) ----

export interface BlueprintVersionSummary {
  version: number;
  blueprint_id: string;
  created_by: string;
  created_at: string;
  change_summary: string | null;
}

export interface BlueprintVersionDetail extends BlueprintVersionSummary {
  spec_dict_snapshot: Record<string, unknown>;
}

export interface PaginatedVersionsResponse {
  items: BlueprintVersionSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ---------------------------------------------------------------------------
// Error class
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
// Internal request helper
// ---------------------------------------------------------------------------

/**
 * Thin wrapper around the shared Axios instance.
 *
 * - Sends ``method`` + ``path`` (relative to ``/api2``).
 * - Unwraps ``{ success, data }`` envelopes when the backend uses them.
 * - Maps Axios errors to ``BlueprintApiError`` for consistent upstream
 *   handling (the component layer uses ``instanceof BlueprintApiError``).
 */
async function _request<T>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  // Strip undefined values from query params so Axios doesn't serialise them.
  const cleanParams: Record<string, string | number | boolean> = {};
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        cleanParams[key] = value;
      }
    }
  }

  try {
    const response = await axios.request({
      method,
      url: path,
      data: body,
      params: Object.keys(cleanParams).length > 0 ? cleanParams : undefined,
    });

    const payload = response.data;

    // Support the { success, data } envelope used by all blueprint endpoints.
    if (
      payload !== null &&
      typeof payload === "object" &&
      "success" in payload &&
      "data" in payload
    ) {
      return (payload as { success: boolean; data: T }).data;
    }

    return payload as T;
  } catch (err: unknown) {
    if (isAxiosError(err)) {
      const status = err.response?.status ?? 0;
      const data = err.response?.data as Record<string, unknown> | undefined;
      const message =
        (data?.error as string) ??
        (data?.message as string) ??
        err.message ??
        "Unknown error";
      throw new BlueprintApiError(status, message, path);
    }
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Blueprint CRUD
// ---------------------------------------------------------------------------

/**
 * POST /blueprint.save
 *
 * Body: ``{identity: {type, id}, spec_dict: {...}, metadata?: {...}}``
 */
export async function saveBlueprint(
  identity: Identity,
  specDict: Record<string, unknown>,
  metadata?: Record<string, unknown>,
): Promise<{ blueprint_id: string }> {
  return _request("POST", "/blueprint.save", {
    identity,
    spec_dict: specDict,
    metadata: metadata ?? {},
  });
}

/**
 * PUT /blueprint.update
 *
 * Body: ``{blueprint_id, spec_dict, user_id?, change_summary?}``
 */
export async function updateBlueprint(
  blueprintId: string,
  specDict: Record<string, unknown>,
  userId?: string,
  changeSummary?: string,
): Promise<{ blueprint_id: string }> {
  return _request("PUT", "/blueprint.update", {
    blueprint_id: blueprintId,
    spec_dict: specDict,
    user_id: userId ?? "",
    change_summary: changeSummary,
  });
}

/**
 * GET /blueprint.info.get?blueprint_id=<id>
 */
export async function getBlueprintById(
  blueprintId: string,
): Promise<BlueprintDocument> {
  return _request("GET", "/blueprint.info.get", undefined, {
    blueprint_id: blueprintId,
  });
}

/**
 * GET /available.blueprints.summary.get
 *     ?identity_type=...&identity_id=...&skip=0&limit=20
 */
export async function listBlueprintSummaries(
  skip = 0,
  limit = 20,
  identityType?: string,
  identityId?: string,
): Promise<PaginatedBlueprintsResponse> {
  return _request("GET", "/available.blueprints.summary.get", undefined, {
    skip,
    limit,
    identity_type: identityType,
    identity_id: identityId,
  });
}

/**
 * DELETE /remove.blueprint?blueprint_id=<id>
 */
export async function deleteBlueprint(
  blueprintId: string,
): Promise<{ deleted: boolean }> {
  return _request("DELETE", "/remove.blueprint", undefined, {
    blueprint_id: blueprintId,
  });
}

// ---------------------------------------------------------------------------
// Version-history endpoints (GENIE-1336)
// ---------------------------------------------------------------------------

/**
 * GET /blueprint.versions.list
 *     ?blueprint_id=<id>&page=1&page_size=20
 *
 * Note: plural ``versions`` in the path.
 */
export async function listBlueprintVersions(
  blueprintId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedVersionsResponse> {
  return _request("GET", "/blueprint.versions.list", undefined, {
    blueprint_id: blueprintId,
    page,
    page_size: pageSize,
  });
}

/**
 * GET /blueprint.version.get?blueprint_id=<id>&version=<n>
 */
export async function getBlueprintVersion(
  blueprintId: string,
  versionNumber: number,
): Promise<BlueprintVersionDetail> {
  return _request("GET", "/blueprint.version.get", undefined, {
    blueprint_id: blueprintId,
    version: versionNumber,
  });
}

/**
 * POST /blueprint.version.restore
 *
 * Body: ``{blueprint_id, version: <n>, user_id?: "..."}``
 *
 * Note: backend reads ``body.get("version")``, NOT ``target_version``.
 */
export async function restoreBlueprintVersion(
  blueprintId: string,
  targetVersion: number,
  userId?: string,
): Promise<{ blueprint_id: string; restored_from_version: number; message: string }> {
  return _request("POST", "/blueprint.version.restore", {
    blueprint_id: blueprintId,
    version: targetVersion,
    user_id: userId ?? "",
  });
}
