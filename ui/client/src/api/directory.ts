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

export async function getDirectoryStatus(): Promise<{ enabled: boolean }> {
  const { data } = await identityApi.get<{ enabled: boolean }>('/directory/directory.status');
  return data;
}

export async function searchDirectoryUsers(
  query: string,
  limit: number = 10,
): Promise<DirectoryUser[]> {
  const { data } = await identityApi.get<{ users: DirectoryUser[] }>(
    '/directory/directory.search_users',
    { params: { q: query, limit } },
  );
  return data.users;
}

export async function searchDirectory(
  query: string,
  limit: number = 10,
): Promise<DirectorySearchResult> {
  const { data } = await identityApi.get<DirectorySearchResult>(
    '/directory/directory.search',
    { params: { q: query, limit } },
  );
  return data;
}

export async function getDirectoryGroup(
  groupId: string,
): Promise<DirectoryGroup> {
  const { data } = await identityApi.get<DirectoryGroup>(
    '/directory/directory.get_group',
    { params: { groupId } },
  );
  return data;
}
