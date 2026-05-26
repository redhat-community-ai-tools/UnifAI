import { api as identityApi } from '@/http/authClient';

export interface DirectoryUser {
  user_id: string;
  username: string;
  display_name: string;
  email: string;
  title: string;
}

export interface DirectoryGroup {
  group_id: string;
  name: string;
  description: string;
  members: string[];
}

export interface DirectorySearchResult {
  users: DirectoryUser[];
  groups: DirectoryGroup[];
}

function authHeaders(accessToken?: string | null): Record<string, string> {
  const h: Record<string, string> = {};
  if (accessToken) h['X-User-Token'] = accessToken;
  return h;
}

export async function getDirectoryStatus(): Promise<{ enabled: boolean }> {
  const { data } = await identityApi.get<{ enabled: boolean }>('/directory/directory.status');
  return data;
}

export async function searchDirectoryUsers(
  query: string,
  limit: number = 10,
  accessToken?: string | null,
): Promise<DirectoryUser[]> {
  const { data } = await identityApi.get<{ users: DirectoryUser[] }>(
    '/directory/directory.search_users',
    { params: { q: query, limit }, headers: authHeaders(accessToken) },
  );
  return data.users;
}

export async function searchDirectory(
  query: string,
  limit: number = 10,
  accessToken?: string | null,
): Promise<DirectorySearchResult> {
  const { data } = await identityApi.get<DirectorySearchResult>(
    '/directory/directory.search',
    { params: { q: query, limit }, headers: authHeaders(accessToken) },
  );
  return data;
}

export async function getDirectoryGroup(
  groupId: string,
  accessToken?: string | null,
): Promise<DirectoryGroup> {
  const { data } = await identityApi.get<DirectoryGroup>(
    '/directory/directory.get_group',
    { params: { groupId }, headers: authHeaders(accessToken) },
  );
  return data;
}
