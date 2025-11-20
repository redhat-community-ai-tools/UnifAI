import axios from '../http/axiosAgentConfig';

export interface WorkflowBlueprint {
  blueprint_id: string;
  spec_dict: any;
  name?: string;
  created_at?: string;
  updated_at?: string;
}

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
  resourcesByCategory: ResourceStats[];
}

// Fetch available workflows/blueprints
export async function fetchWorkflows(userId?: string): Promise<WorkflowBlueprint[]> {
  const userIdParam = userId || 'default';
  const response = await axios.get(`/blueprints/available.blueprints.get?userId=${userIdParam}`);
  return response.data || [];
}

// Fetch active sessions
export async function fetchActiveSessions(userId?: string): Promise<string[]> {
  const userIdParam = userId || 'default';
  const response = await axios.get(`/sessions/session.user.blueprints.get?userId=${userIdParam}`);
  return response.data || [];
}

// Fetch session counts by blueprint_id
export async function fetchBlueprintSessionCounts(userId?: string): Promise<Record<string, number>> {
  const userIdParam = userId || 'default';
  const response = await axios.get(`/sessions/session.user.blueprint.counts.get?userId=${userIdParam}`);
  return response.data || {};
}

// Fetch all resources for a user
export async function fetchAllResources(userId?: string): Promise<any[]> {
  const userIdParam = userId || 'default';
  const response = await axios.get(`/resources/resources.list?userId=${userIdParam}`);
  return response.data?.resources || [];
}

// Fetch resources by category
export async function fetchResourcesByCategory(category: string, userId?: string): Promise<any[]> {
  const userIdParam = userId || 'default';
  const response = await axios.get(`/resources/resources.list?userId=${userIdParam}&category=${category}`);
  return response.data?.resources || [];
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

// Fetch agentic stats summary
export async function fetchAgenticStats(userId?: string): Promise<AgenticStats> {
  const userIdParam = userId || 'default';
  
  const [workflows, activeSessions, resources, catalog] = await Promise.all([
    fetchWorkflows(userIdParam).catch(() => []),
    fetchActiveSessions(userIdParam).catch(() => []),
    fetchAllResources(userIdParam).catch(() => []),
    fetchCatalogElements().catch(() => ({}))
  ]);

  // Group resources by category
  const resourcesByCategory: { [key: string]: ResourceStats } = {};
  
  if (Array.isArray(resources)) {
    resources.forEach((resource: any) => {
      let category = resource.category || 'UNKNOWN';
      // Map 'nodes' to 'agents' for consistency with UI
      if (category.toLowerCase() === 'nodes') {
        category = 'agents';
      }
      if (!resourcesByCategory[category]) {
        resourcesByCategory[category] = {
          category,
          count: 0,
          types: {}
        };
      }
      resourcesByCategory[category].count++;
      const type = resource.type || 'unknown';
      resourcesByCategory[category].types[type] = (resourcesByCategory[category].types[type] || 0) + 1;
    });
  }

  return {
    totalWorkflows: workflows.length,
    activeSessions: activeSessions.length,
    totalResources: resources.length,
    resourcesByCategory: Object.values(resourcesByCategory)
  };
}

