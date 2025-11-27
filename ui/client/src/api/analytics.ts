/**
 * Analytics API client for workflow statistics
 */

import { api } from '@/http/queryClient';

export interface TotalStats {
  total_runs: number;
  unique_users: number;
  avg_runs_per_user: number;
}

export interface StatusBreakdown {
  [status: string]: number;
}

export interface StatusBreakdownMap {
  [status: string]: number;
}

export interface UserActivity {
  user_id: string;
  total_runs: number;
  unique_blueprints: number;
  status_breakdown: StatusBreakdownMap;
}

export interface ActiveUser {
  user_id: string;
  recent_runs: number;
  runs_today?: number;
  last_run_id: string;
  status_breakdown: StatusBreakdownMap;
}

export interface TimeStats {
  earliest_run: {
    run_id: string;
    user_id: string;
    timestamp: string;
  } | null;
  latest_run: {
    run_id: string;
    user_id: string;
    timestamp: string;
  } | null;
  time_span_days: number | null;
}

export interface BlueprintUsage {
  blueprint_id: string;
  blueprint_name: string;
  run_count: number;
  unique_users: number;
}

export interface HourlyActivity {
  hour: string;
  count: number;
}

export interface AnalyticsOverview {
  total_stats: TotalStats;
  status_breakdown: StatusBreakdown;
  time_stats: TimeStats;
  active_today: ActiveUser[];
  active_7days: ActiveUser[];
  active_30days: ActiveUser[];
  top_users: UserActivity[];
  top_blueprints: BlueprintUsage[];
  generated_at: string;
}

/**
 * Fetch comprehensive analytics overview
 */
export async function fetchAnalyticsOverview(): Promise<AnalyticsOverview> {
  const response = await api.get<AnalyticsOverview>('analytics/overview');
  return response.data;
}

/**
 * Fetch active users for a specific time period
 */
export async function fetchActiveUsers(days: number = 7): Promise<{ active_users: ActiveUser[], count: number, days: number }> {
  const response = await api.get<{ active_users: ActiveUser[], count: number, days: number }>(
    'analytics/users/active',
    { params: { days } }
  );
  return response.data;
}

/**
 * Fetch user activity breakdown
 */
export async function fetchUserActivity(limit: number = 15): Promise<{ user_activity: UserActivity[], count: number }> {
  const response = await api.get<{ user_activity: UserActivity[], count: number }>(
    'analytics/users/activity',
    { params: { limit } }
  );
  return response.data;
}

/**
 * Fetch blueprint usage statistics
 */
export async function fetchBlueprintUsage(limit: number = 10): Promise<{ blueprint_usage: BlueprintUsage[], count: number }> {
  const response = await api.get<{ blueprint_usage: BlueprintUsage[], count: number }>(
    'analytics/blueprints/usage',
    { params: { limit } }
  );
  return response.data;
}

/**
 * Fetch hourly activity distribution
 */
export async function fetchHourlyActivity(days: number = 7): Promise<{ hourly_activity: HourlyActivity[], days: number }> {
  const response = await api.get<{ hourly_activity: HourlyActivity[], days: number }>(
    'analytics/activity/hourly',
    { params: { days } }
  );
  return response.data;
}

