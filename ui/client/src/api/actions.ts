import axios from '../http/axiosAgentConfig';

export async function executeAction(
  actionUid: string,
  inputData: Record<string, any>,
) {
  const response = await axios.post('/actions/action.execute', {
    uid: actionUid,
    inputData,
  });
  return response.data;
}

export async function listActions(category: string, type: string): Promise<any[]> {
  const response = await axios.get('/actions/actions.list', {
    params: { category, type },
  });
  return response.data.actions || [];
}

/**
 * Generic dynamic endpoint call for hint-driven API operations
 * (validation hints, population hints, etc.) where the endpoint
 * and method are provided by the backend schema at runtime.
 */
export async function callDynamicEndpoint(
  endpoint: string,
  method: string,
  data: Record<string, any>,
): Promise<any> {
  const upperMethod = method.toUpperCase();
  if (upperMethod === 'GET') {
    const response = await axios.get(endpoint, { params: data });
    return response.data;
  }
  const response = await axios({
    method: upperMethod.toLowerCase(),
    url: endpoint,
    data,
  });
  return response.data;
}
