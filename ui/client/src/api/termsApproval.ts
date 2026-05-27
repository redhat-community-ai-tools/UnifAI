import { api } from '@/http/queryClient';

export interface UserApprovalStatus {
  approved: boolean;
  username: string;
}

export interface ApproveUserResponse {
  status: string;
  message: string;
  username: string;
  approved: boolean;
}

/**
 * Check if the current user has approved the AI transparency notice.
 * Backend resolves user from the session cookie.
 */
export async function checkUserApproval(): Promise<UserApprovalStatus> {
  const response = await api.get<UserApprovalStatus>(
    'terms_approval/user.approval.status.get',
  );
  return response.data;
}

/**
 * Record the current user's approval of the AI transparency notice.
 * Backend resolves user from the session cookie.
 */
export async function approveUser(): Promise<ApproveUserResponse> {
  const response = await api.post<ApproveUserResponse>(
    'terms_approval/user.approval.record.post',
    {}
  );
  return response.data;
}

