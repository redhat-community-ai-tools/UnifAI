import axios from '@/http/axiosAgentConfig';
import { ElementSchema } from '@/types/workspace';

export interface ResourceIdentity {
  type: 'user' | 'team' | 'system';
  id: string;
  display_name: string;
}

export interface ResourceInstance {
  rid: string;
  identity: ResourceIdentity;
  category: string;
  type: string;
  name: string;
  version: number;
  cfg_dict: any;
  nested_refs: string[];
  contributed_by?: string;
  created: string;
  updated: string;
  ownership?: 'builtin' | 'custom';
  visibility?: 'draft' | 'public';
  user_configured?: boolean;
  /**
   * Present when toggling/promoting to "available to all" cascaded to
   * aggregated elements (LLMs, providers, tools, etc.) that weren't
   * already public built-ins — they were made available to all too.
   */
  cascaded_resources?: ResourceDependencySummary[];
}

/** Minimal info about a related resource surfaced on cascade/blocked responses. */
export interface ResourceDependencySummary {
  rid: string;
  name: string;
  category: string;
}

export interface ResourcesListResponse {
  resources: ResourceInstance[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

export interface BuiltinsListResponse {
  resources: ResourceInstance[];
}

export async function listResources(params: {
  teamId?: string;
  category?: string;
  type?: string;
  ownership?: string;
  limit?: number;
  offset?: number;
}): Promise<ResourcesListResponse> {
  const query = new URLSearchParams();
  if (params.teamId) query.set('teamId', params.teamId);
  if (params.category) query.set('category', params.category);
  if (params.type) query.set('type', params.type);
  if (params.ownership) query.set('ownership', params.ownership);
  if (params.limit != null) query.set('limit', String(params.limit));
  if (params.offset != null) query.set('offset', String(params.offset));

  const { data } = await axios.get<ResourcesListResponse>(
    `/resources/resources.list?${query.toString()}`,
  );
  return data;
}

/**
 * Fetch a caller's *complete* resource set for the given filters — pages
 * through with `offset`/`has_more` (server caps `limit` at 1000/request)
 * instead of assuming everything fits in one page. Use this whenever the
 * caller needs "all resources matching X" (dropdown/$ref sources, building
 * blocks, name lookups, etc.) rather than a UI-paginated list.
 */
export async function listAllResources(params: {
  teamId?: string;
  category?: string;
  type?: string;
  ownership?: string;
}): Promise<ResourceInstance[]> {
  const PAGE_SIZE = 1000;
  // Not a business limit on how many resources a caller can have — pagination
  // is driven entirely by `has_more` below. This only exists as a circuit
  // breaker for a genuinely broken backend that never reports
  // `has_more: false`, so a pagination bug degrades into a clear error
  // instead of an infinite loop that hangs the tab.
  const MAX_ITERATIONS = 100_000; // 100M resources — never expected in practice
  const resources: ResourceInstance[] = [];
  let offset = 0;
  let hasMore = true;
  let iterations = 0;

  while (hasMore) {
    if (++iterations > MAX_ITERATIONS) {
      throw new Error(
        `listAllResources: aborted after ${iterations - 1} pages without the server ` +
        `reporting has_more=false — this indicates a pagination bug, not a large result set.`
      );
    }
    const page = await listResources({ ...params, limit: PAGE_SIZE, offset });
    resources.push(...page.resources);
    hasMore = !!page.pagination?.has_more && page.resources.length > 0;
    if (hasMore) offset += page.resources.length;
  }

  return resources;
}

export async function getResource(resourceId: string): Promise<ResourceInstance> {
  const { data } = await axios.get<ResourceInstance>(
    `/resources/resource.get?resourceId=${encodeURIComponent(resourceId)}`,
  );
  return data;
}

export async function createResource(payload: {
  teamId?: string;
  category: string;
  type: string;
  name: string;
  config: Record<string, any>;
}): Promise<ResourceInstance> {
  const { data } = await axios.post<ResourceInstance>('/resources/resource.save', payload);
  return data;
}

export async function updateResource(payload: {
  resourceId: string;
  config: Record<string, any>;
  name?: string;
}): Promise<ResourceInstance> {
  const { data } = await axios.put<ResourceInstance>('/resources/resource.update', payload);
  return data;
}

export async function deleteResource(resourceId: string): Promise<void> {
  await axios.delete(`/resources/resource.delete?resourceId=${encodeURIComponent(resourceId)}`);
}

export async function getResourceSchema(): Promise<any> {
  const { data } = await axios.get('/resources/resource.schema');
  return data;
}

export async function validateResources(payload: {
  resourceIds: string[];
  userId?: string;
  timeoutSeconds?: number;
  maxWorkers?: number;
}): Promise<any[]> {
  const { data } = await axios.post('/resources/resources.validate', payload);
  return data;
}

export async function uploadResourceFile(
  file: File,
  format: string = "pem",
): Promise<{ content: string; filename: string; size_bytes: number; format_valid: boolean }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("format", format);

  const response = await axios.post("/resources/resource.upload-file", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

// --- Built-in resource endpoints ---

export async function getBuiltinUserConfig(params: {
  resourceId: string;
  teamId?: string;
}): Promise<Record<string, any> | null> {
  const query = new URLSearchParams();
  query.set('resourceId', params.resourceId);
  if (params.teamId) query.set('teamId', params.teamId);
  const { data } = await axios.get<{ config: Record<string, any> | null }>(
    `/resources/builtin.user-config?${query.toString()}`,
  );
  return data.config;
}

export async function listBuiltins(params?: {
  category?: string;
  type?: string;
}): Promise<BuiltinsListResponse> {
  const query = new URLSearchParams();
  if (params?.category) query.set('category', params.category);
  if (params?.type) query.set('type', params.type);
  const qs = query.toString();
  const { data } = await axios.get<BuiltinsListResponse>(
    `/resources/builtins.list${qs ? `?${qs}` : ''}`,
  );
  return data;
}

export async function getBuiltinSchema(resourceId: string): Promise<any> {
  const { data } = await axios.get(
    `/resources/builtin.schema?resourceId=${encodeURIComponent(resourceId)}`,
  );
  return data;
}

export async function getElementSpec(category: string, type: string): Promise<ElementSchema> {
  const { data } = await axios.get<ElementSchema>(
    `/catalog/element.spec.get?category=${encodeURIComponent(category)}&type=${encodeURIComponent(type)}`,
  );
  return data;
}

export async function configureBuiltin(payload: {
  resourceId: string;
  teamId?: string;
  config: Record<string, any>;
}): Promise<ResourceInstance> {
  const { data } = await axios.patch<ResourceInstance>(
    '/resources/builtin.configure',
    payload,
  );
  return data;
}

export async function createBuiltin(payload: {
  teamId?: string;
  category: string;
  type: string;
  name: string;
  config: Record<string, any>;
  availableToAll?: boolean;
}): Promise<ResourceInstance> {
  const { data } = await axios.post<ResourceInstance>(
    '/resources/builtin.create',
    payload,
  );
  return data;
}

export async function updateBuiltin(payload: {
  resourceId: string;
  config?: Record<string, any>;
  name?: string;
  availableToAll?: boolean;
}): Promise<ResourceInstance> {
  const { data } = await axios.put<ResourceInstance>(
    '/resources/builtin.update',
    payload,
  );
  return data;
}

export async function toggleBuiltinVisibility(payload: {
  resourceId: string;
  availableToAll: boolean;
}): Promise<ResourceInstance> {
  const { data } = await axios.patch<ResourceInstance>(
    '/resources/builtin.toggle',
    payload,
  );
  return data;
}

/**
 * Preview which resources would be newly made available to all if
 * `resourceId` were promoted/toggled on — read-only, does not mutate
 * anything. Lets the UI confirm the cascade with the admin *before* the
 * mutation, instead of only disclaiming it after the fact.
 */
export async function previewBuiltinCascade(
  resourceId: string,
): Promise<ResourceDependencySummary[]> {
  const { data } = await axios.get<{ cascaded_resources: ResourceDependencySummary[] }>(
    `/resources/builtin.cascade-preview?resourceId=${encodeURIComponent(resourceId)}`,
  );
  return data.cascaded_resources || [];
}

// --- Admin edit lock endpoints (built-in resources) ---

export interface BuiltinEditLockHolder {
  userId: string;
  displayName: string;
}

export type BuiltinEditLockResolved = BuiltinEditLockHolder | null | "unknown";

export async function acquireBuiltinEditLock(entityId: string): Promise<
  { acquired: true } | { acquired: false; lockedBy: BuiltinEditLockHolder }
> {
  try {
    const { data } = await axios.post<{
      acquired: boolean;
      lockedBy?: BuiltinEditLockHolder;
    }>("/resources/builtin.edit_lock.acquire", { entityId });
    if (data.acquired) return { acquired: true };
    return {
      acquired: false,
      lockedBy: data.lockedBy ?? { userId: "?", displayName: "Another admin" },
    };
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (status === 501) return { acquired: true };
    throw e;
  }
}

export async function releaseBuiltinEditLock(entityId: string): Promise<void> {
  try {
    await axios.post("/resources/builtin.edit_lock.release", { entityId });
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (status === 501) return;
    throw e;
  }
}

export async function heartbeatBuiltinEditLock(entityId: string): Promise<void> {
  try {
    await axios.post("/resources/builtin.edit_lock.heartbeat", { entityId });
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (status === 501) return;
    throw e;
  }
}

export async function fetchBuiltinEditLockStatuses(
  entityIds: string[],
): Promise<Record<string, BuiltinEditLockResolved>> {
  if (entityIds.length === 0) return {};
  const unknownMap = (): Record<string, BuiltinEditLockResolved> =>
    Object.fromEntries(entityIds.map((id) => [id, "unknown" as const]));
  try {
    const { data } = await axios.post<{
      locks: Record<string, BuiltinEditLockHolder | null>;
    }>("/resources/builtin.edit_lock.statuses", { entityIds });
    return (data.locks ?? {}) as Record<string, BuiltinEditLockResolved>;
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    if (status === 501) return {};
    return unknownMap();
  }
}
