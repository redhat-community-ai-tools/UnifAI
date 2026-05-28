import axios from '@/http/axiosAgentConfig';
import type { ElementValidationResult } from '@/types/validation';

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

export interface ListResourcesParams {
  category?: string;
  type?: string;
  teamId?: string | null;
  limit?: string;
}

export async function listResources(params: ListResourcesParams): Promise<ResourcesListResponse> {
  const query = new URLSearchParams();
  if (params.category) query.set('category', params.category);
  if (params.type) query.set('type', params.type);
  if (params.teamId) query.set('teamId', params.teamId);
  if (params.limit) query.set('limit', params.limit);
  const response = await axios.get<ResourcesListResponse>(
    `/resources/resources.list?${query.toString()}`,
  );
  return response.data;
}

export async function getResource(resourceId: string): Promise<ResourceInstance> {
  const response = await axios.get<ResourceInstance>(
    `/resources/resource.get?resourceId=${resourceId}`,
  );
  return response.data;
}

export async function getResourceSchema(): Promise<any> {
  const response = await axios.get('/resources/resource.schema');
  return response.data;
}

export interface SaveResourcePayload {
  category: string;
  type: string;
  config: any;
  name?: string;
  teamId?: string | null;
  [key: string]: any;
}

export async function saveResource(payload: SaveResourcePayload): Promise<any> {
  const response = await axios.post('/resources/resource.save', payload);
  return response.data;
}

export interface UpdateResourcePayload {
  resourceId: string;
  config: any;
  name: string;
}

export async function updateResource(payload: UpdateResourcePayload): Promise<any> {
  const response = await axios.put('/resources/resource.update', payload);
  return response.data;
}

export async function deleteResource(resourceId: string): Promise<void> {
  await axios.delete(`/resources/resource.delete?resourceId=${resourceId}`);
}

export async function validateResource(resourceId: string): Promise<ElementValidationResult> {
  const response = await axios.post<ElementValidationResult>(
    '/resources/resource.validate',
    { resourceId },
  );
  return response.data;
}
