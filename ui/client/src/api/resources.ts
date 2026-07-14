import axios from '@/http/axiosAgentConfig';

export interface ResourceInstance {
  rid: string;
  user_id: string;
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
    `/resources/resource.get?resourceId=${resourceId}`,
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
  await axios.delete(`/resources/resource.delete?resourceId=${resourceId}`);
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

// --- Built-in resource endpoints ---

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
    `/resources/builtin.schema?resourceId=${resourceId}`,
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
