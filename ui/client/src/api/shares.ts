import axios from '@/http/axiosAgentConfig';

export interface ShareInvite {
  share_id: string;
  sender_user_id: string;
  recipient_user_id: string;
  item_kind: 'resource' | 'blueprint';
  item_id: string;
  item_name: string;
  message?: string;
  status: 'pending' | 'accepted' | 'declined' | 'canceled';
  created_at: string;
  expires_at: string;
  ttl_days: number;
  is_expired: boolean;
  accepted_at?: string;
  declined_at?: string;
  result_mapping?: Record<string, string>;
}

export interface ShareResult {
  share_id: string;
  new_item_id: string;
  rid_mapping: Record<string, string>;
  created_resources: number;
  name_conflicts: Record<string, string>;
}

export interface SharesListResponse {
  invites: ShareInvite[];
  count: number;
}

export interface CreateShareRequest {
  recipientUserId: string;
  itemKind: 'resource' | 'blueprint';
  itemId: string;
  message?: string;
  ttlDays?: number;
  senderUserId?: string;
}

export interface CreateShareResponse {
  status: string;
  share_id: string;
}

export interface AcceptShareRequest {
  shareId: string;
  recipientUserId?: string;
}

export interface AcceptShareResponse {
  status: string;
  result: ShareResult;
}

export interface DeclineShareRequest {
  shareId: string;
  recipientUserId?: string;
}

export interface DeclineShareResponse {
  status: string;
}

// Create a share invitation
export async function createShare(request: CreateShareRequest): Promise<CreateShareResponse> {
  const { data } = await axios.post<CreateShareResponse>('/shares/share.create', request);
  return data;
}

// List share invitations
export async function listShares(
  direction: 'received' | 'sent',
  userId?: string,
  status?: 'pending' | 'accepted' | 'declined' | 'canceled',
  skip: number = 0,
  limit: number = 100
): Promise<SharesListResponse> {
  const params: any = {
    direction,
    skip,
    limit,
  };

  if (userId) {
    params.userId = userId;
  }

  if (status) {
    params.status = status;
  }

  const { data } = await axios.get<SharesListResponse>('/shares/shares.list', { params });
  return data;
}

// Accept a share invitation
export async function acceptShare(request: AcceptShareRequest): Promise<AcceptShareResponse> {
  const { data } = await axios.post<AcceptShareResponse>('/shares/share.accept', request);
  return data;
}

// Decline a share invitation
export async function declineShare(request: DeclineShareRequest): Promise<DeclineShareResponse> {
  const { data } = await axios.post<DeclineShareResponse>('/shares/share.decline', request);
  return data;
}

// Get share details
export async function getShare(shareId: string, userId?: string): Promise<ShareInvite> {
  const params: any = { shareId };
  if (userId) {
    params.userId = userId;
  }

  const { data } = await axios.get<ShareInvite>('/shares/share.get', { params });
  return data;
}
