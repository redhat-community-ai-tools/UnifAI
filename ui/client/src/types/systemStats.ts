/**
 * System Statistics type definitions
 * 
 * Type definitions for system-wide statistics data structures.
 * All data is scoped to the requested time range by the backend.
 */

export type TimeRange = 'today' | '7days' | '30days' | 'all';

export interface TotalStats {
  total_runs: number;
  unique_users: number;
  blueprints_used: number;
}

export interface StatusBreakdown {
  [status: string]: number;
}

export interface UserActivity {
  identity_id: string;
  identity_type: string;
  display_name: string;
  run_count: number;
  blueprints_used: number;
  status_breakdown: StatusBreakdown;
}

export interface BlueprintUsage {
  blueprint_id: string;
  blueprint_name: string;
  run_count: number;
  unique_users: number;
  avg_duration_seconds?: number;
  last_run_at?: string;
  success_rate: number;
  completed_runs: number;
  failed_runs: number;
  active_runs: number;
  user_list: string[];
}

export interface TimeSeriesData {
  period: string;
  count: number;
}

export interface SystemStatsResponse {
  total_stats: TotalStats;
  status_breakdown: StatusBreakdown;
  active_users: UserActivity[];
  top_blueprints: BlueprintUsage[];
  time_series?: TimeSeriesData[];
  generated_at: string;
}

