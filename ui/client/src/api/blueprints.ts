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
 */

import axios from "@/http/axiosAgentConfig";
import { isAxiosError } from "axios";

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export interface Identity {
  owner_id: string;
  owner_type: string;
  display_name?: string;
}

// ---- Blueprint types ----

export interface BlueprintSummary {
  blueprint_id: string;
  name: string;
  description: string;
  identity: Identity;
  created_at: string;
  updated_at: string;
}

export interface BlueprintDocument extends BlueprintSummary {
  spec_dict: Record<string, unknown>;
  rid_refs: string[];
  metadata: Record<string, unknown>;
  version: number;
}

export interface PaginatedBlueprintsResponse {
  items: BlueprintSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
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

    // Support the { success, data } envelope used by some endpoints.
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

export async function updateBlueprint(
  blueprintId: string,
  specDict: Record<string, unknown>,
  userId?: string,
  changeSummary?: string,
): Promise<{ success: boolean }> {
  return _request("PUT", "/blueprint.update", {
    blueprint_id: blueprintId,
    spec_dict: specDict,
    user_id: userId ?? "",
    change_summary: changeSummary,
  });
}

export async function getBlueprintById(
  blueprintId: string,
): Promise<BlueprintDocument> {
  return _request("GET", `/blueprint.get`, undefined, {
    blueprint_id: blueprintId,
  });
}

export async function listBlueprintSummaries(
  page = 1,
  pageSize = 20,
  ownerId?: string,
  ownerType?: string,
): Promise<PaginatedBlueprintsResponse> {
  return _request("GET", "/blueprint.list", undefined, {
    page,
    page_size: pageSize,
    owner_id: ownerId,
    owner_type: ownerType,
  });
}

export async function deleteBlueprint(
  blueprintId: string,
): Promise<{ success: boolean }> {
  return _request("DELETE", `/blueprint.delete`, undefined, {
    blueprint_id: blueprintId,
  });
}

// ---------------------------------------------------------------------------
// Version-history endpoints (GENIE-1336)
// ---------------------------------------------------------------------------

export async function listBlueprintVersions(
  blueprintId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedVersionsResponse> {
  return _request("GET", "/blueprint.version.list", undefined, {
    blueprint_id: blueprintId,
    page,
    page_size: pageSize,
  });
}

export async function getBlueprintVersion(
  blueprintId: string,
  versionNumber: number,
): Promise<BlueprintVersionDetail> {
  return _request("GET", "/blueprint.version.get", undefined, {
    blueprint_id: blueprintId,
    version: versionNumber,
  });
}

export async function restoreBlueprintVersion(
  blueprintId: string,
  targetVersion: number,
  userId?: string,
): Promise<{ success: boolean }> {
  return _request("POST", "/blueprint.version.restore", {
    blueprint_id: blueprintId,
    target_version: targetVersion,
    user_id: userId ?? "",
  });
}
