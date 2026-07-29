import { api } from '@/http/authClient';

export interface ApiToken {
  name: string;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
}

export interface CreateTokenResponse {
  token: string;
  name: string;
  expires_at: string;
  expires_in: number;
}

export async function createToken(name: string): Promise<CreateTokenResponse> {
  const response = await api.post('/tokens/create', { name });
  return response.data;
}

export async function listTokens(): Promise<ApiToken[]> {
  const response = await api.get('/tokens/list');
  return response.data.tokens;
}

export async function revokeToken(name: string): Promise<void> {
  await api.post('/tokens/revoke', { name });
}
