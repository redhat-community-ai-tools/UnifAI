import axios from '@/http/axiosAgentConfig';

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
  userId: string;
  identityType: string;
  category?: string;
  type?: string;
  ownership?: string;
  limit?: number;
  offset?: number;
}): Promise<ResourcesListResponse> {
  const query = new URLSearchParams();
  query.set('userId', params.userId);
  query.set('identityType', params.identityType);
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

export async function getResource(resourceId: string): Promise<ResourceInstance> {
  const { data } = await axios.get<ResourceInstance>(
    `/resources/resource.get?resourceId=${encodeURIComponent(resourceId)}`,
  );
  return data;
}

export async function createResource(payload: {
  userId: string;
  identityType: string;
  displayName?: string;
  category: string;
  type: string;
  name: string;
  config: Record<string, any>;
}): Promise<ResourceInstance> {
  const { config, ...rest } = payload;
  const { data } = await axios.post<ResourceInstance>('/resources/resource.save', {
    ...rest,
    config,
  });
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

export async function validateResource(payload: {
  resourceId: string;
  userId?: string;
  timeoutSeconds?: number;
}): Promise<any> {
  const { data } = await axios.post('/resources/resource.validate', payload);
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
  userId: string;
  identityType: string;
}): Promise<Record<string, any> | null> {
  const query = new URLSearchParams();
  query.set('resourceId', params.resourceId);
  query.set('userId', params.userId);
  query.set('identityType', params.identityType);
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

export async function configureBuiltin(payload: {
  resourceId: string;
  userId: string;
  identityType: string;
  config: Record<string, any>;
}): Promise<ResourceInstance> {
  const { data } = await axios.patch<ResourceInstance>(
    '/resources/builtin.configure',
    payload,
  );
  return data;
}

export async function createBuiltin(payload: {
  userId: string;
  identityType: string;
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

export async function promoteResource(resourceId: string): Promise<ResourceInstance> {
  const { data } = await axios.patch<ResourceInstance>(
    '/resources/resource.promote',
    { resourceId },
  );
  return data;
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
