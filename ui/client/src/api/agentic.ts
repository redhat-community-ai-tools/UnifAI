import axios from '../http/axiosAgentConfig';
import { normalizeCategory } from '@/constants/resources';
import { listAllResources } from '@/api/resources';

export interface Session {
  session_id: string;
  blueprint_id: string;
  user_id: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ResourceStats {
  category: string;
  count: number;
  types: { [type: string]: number };
}

export interface AgenticStats {
  totalWorkflows: number;
  activeSessions: number;
  totalResources: number;
  categoriesInUse: number;
  blueprintSessionCounts?: Record<string, number>;
  resourcesByCategory: ResourceStats[];
}

// Fetch active sessions
export async function fetchActiveSessions(teamId?: string): Promise<string[]> {
  const query = new URLSearchParams();
  if (teamId) query.set('teamId', teamId);
  const qs = query.toString();
  const response = await axios.get(
    `/sessions/session.user.blueprints.get${qs ? `?${qs}` : ''}`
  );
  return response.data || [];
}

// Fetch session counts by blueprint_id
// Note: This data is available from the aggregated stats endpoint for better performance
export async function fetchBlueprintSessionCounts(teamId?: string): Promise<Record<string, number>> {
  const stats = await fetchAgenticStats(teamId);
  return stats.blueprintSessionCounts || {};
}

// These helpers want the caller's *complete* resource set (stats, building
// blocks, etc.) rather than a single UI-paginated page — delegate to
// `listAllResources` (see `api/resources.ts`) which owns the actual
// offset/has_more pagination loop, instead of duplicating it here.

// Fetch all resources for a user
export async function fetchAllResources(teamId?: string): Promise<any[]> {
  return listAllResources({ teamId });
}

// Fetch resources by category
export async function fetchResourcesByCategory(category: string, teamId?: string): Promise<any[]> {
  return listAllResources({ teamId, category });
}

// Fetch catalog elements (for inventory stats)
export async function fetchCatalogElements(): Promise<any> {
  const response = await axios.get('/catalog/elements.list.get');
  return response.data?.elements || {};
}

// Fetch resource categories
export async function fetchResourceCategories(): Promise<string[]> {
  const response = await axios.get('/catalog/categories.list.get');
  return response.data?.categories || [];
}

// Fetch agentic stats summary - uses aggregated backend endpoint for optimal performance
export async function fetchAgenticStats(teamId?: string): Promise<AgenticStats> {
  const query = new URLSearchParams();
  if (teamId) query.set('teamId', teamId);
  const qs = query.toString();
  const response = await axios.get(
    `/statistics/stats.get${qs ? `?${qs}` : ''}`
  );
  const data = response.data;
  
  // Normalize categories on frontend (backend returns raw categories)
  // Group by normalized category to merge duplicates (e.g., 'nodes' -> 'agents')
  const categoryMap = new Map<string, { count: number; types: { [type: string]: number } }>();
  
  for (const item of data.resourcesByCategory || []) {
    const normalizedCategory = normalizeCategory(item.category || 'UNKNOWN');
    const existing = categoryMap.get(normalizedCategory);
    
    if (existing) {
      existing.count += item.count || 0;
      for (const [type, count] of Object.entries(item.types || {})) {
        existing.types[type] = (existing.types[type] || 0) + (count as number);
      }
    } else {
      categoryMap.set(normalizedCategory, {
        count: item.count || 0,
        types: { ...(item.types || {}) }
      });
    }
  }
  
  const resourcesByCategory = Array.from(categoryMap.entries()).map(([category, data]) => ({
    category,
    count: data.count,
    types: data.types
  }));

  return {
    totalWorkflows: data.totalWorkflows || 0,
    activeSessions: data.activeSessions || 0,
    totalResources: data.totalResources || 0,
    categoriesInUse: resourcesByCategory.length,
    blueprintSessionCounts: data.blueprintSessionCounts || {},
    resourcesByCategory
  };
}


