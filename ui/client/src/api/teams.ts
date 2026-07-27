import { api as identityApi } from '@/http/authClient';
import agentApi from '@/http/axiosAgentConfig';

export type TeamMemberType = 'user' | 'group';

export interface TeamMember {
  type: TeamMemberType;
  id: string;
  display_name: string;
  group_members?: string[];
}

/**
 * Return the effective member count for a team.  Prefers the
 * Identity-computed ``effective_member_count`` when available, otherwise
 * falls back to a client-side calculation from ``group_members``.
 */
export function getEffectiveMemberCount(
  members: TeamMember[],
  identityCount?: number,
): number {
  if (typeof identityCount === 'number') return identityCount;
  const userIds = new Set<string>();
  for (const m of members) {
    if (m.type === 'user') {
      userIds.add(m.id);
    } else if (m.type === 'group' && m.group_members) {
      for (const uid of m.group_members) {
        userIds.add(uid);
      }
    }
  }
  return userIds.size;
}

export interface Team {
  team_id: string;
  name: string;
  created_by: string;
  members: TeamMember[];
  created_at: string;
  updated_at: string;
  effective_member_count?: number;
}

export interface TeamsListResponse {
  teams: Team[];
}

export async function createTeam(
  name: string,
  createdBy: string,
  members: TeamMember[]
): Promise<Team> {
  const { data } = await identityApi.post<Team>('/teams/team.create', {
    name,
    createdBy,
    members,
  });
  return data;
}

export async function listUserTeams(
  userId: string,
  groupIds?: string[],
): Promise<Team[]> {
  const params: Record<string, string> = { userId };
  if (groupIds !== undefined) {
    params.groupIds = groupIds.join(',');
  }
  const { data } = await identityApi.get<TeamsListResponse>('/teams/teams.list', {
    params,
  });
  return data.teams;
}

export async function getTeam(teamId: string): Promise<Team> {
  const { data } = await identityApi.get<Team>('/teams/team.get', {
    params: { teamId },
  });
  return data;
}

export async function updateTeam(
  teamId: string,
  updates: { name?: string; members?: TeamMember[] }
): Promise<Team> {
  const { data } = await identityApi.put<Team>('/teams/team.update', {
    teamId,
    ...updates,
  });
  return data;
}

/**
 * Delete the team record first, then clean up multi-agent data.
 *
 * Order matters: if the team delete (auth-guarded, may fail) is done first,
 * a failure leaves all data intact.  If we cleaned up workspace data first
 * and the team delete then failed, the user would see an empty team with
 * all resources/blueprints/sessions already gone and no way to recover.
 *
 * If cleanup fails after the team is already deleted, the orphaned agent
 * data is invisible (no team to access it through) and can be swept by a
 * background job.
 */
export async function deleteTeam(teamId: string, requestedBy: string): Promise<void> {
  await identityApi.delete('/teams/team.delete', {
    params: { teamId, requestedBy },
  });

  try {
    await agentApi.delete('/workspace/workspace.cleanup', {
      data: { identityType: 'team', identityId: teamId },
    });
  } catch (err) {
    console.error(
      `Team ${teamId} deleted but workspace cleanup failed. Orphaned agent data may remain.`,
      err,
    );
  }
}
