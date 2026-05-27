/**
 * System-wide Statistics API client
 * 
 * NOTE: Uses axios from @/http/axiosAgentConfig which points to /api2 (Multi-Agent Service).
 * Statistics endpoints are in multi-agent/api/flask/endpoints/statistics.py.
 */

import axios from '@/http/axiosAgentConfig';
import type { SystemStatsResponse, TimeRange } from '@/types/systemStats';

/**
 * Fetch comprehensive system-wide statistics (workflows, users, blueprints)
 * 
 * This single endpoint returns all system stats needed for the admin dashboard,
 * scoped to the requested time range:
 * - Total stats (runs, users, avg runs per user)
 * - Status breakdown
 * - Active users with run counts and status breakdown
 * - Top blueprints
 * - Time series activity data
 * 
 * Requires admin access.
 */
export async function fetchSystemWideStats(timeRange: TimeRange = 'all'): Promise<SystemStatsResponse> {
  const params: Record<string, string> = { time_range: timeRange };
  const response = await axios.get<SystemStatsResponse>('/statistics/stats.system.get', { params });
  return response.data;
}

