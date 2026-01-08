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
 * Check if a user has approved the AI transparency notice
 */
export async function checkUserApproval(username: string): Promise<UserApprovalStatus> {
  const response = await api.get<UserApprovalStatus>(
    'terms_approval/user.approval.status.get',
    {
      params: {
        username
      }
    }
  );
  return response.data;
}

/**
 * Record a user's approval of the AI transparency notice
 */
export async function approveUser(username: string): Promise<ApproveUserResponse> {
  const response = await api.post<ApproveUserResponse>(
    'terms_approval/user.approval.record.post',
    { username }
  );
  return response.data;
}

