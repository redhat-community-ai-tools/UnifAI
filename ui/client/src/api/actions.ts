import axios from '../http/axiosAgentConfig';

export async function executeAction(
  actionUid: string,
  inputData: Record<string, any>,
  userId: string,
) {
  const response = await axios.post('/actions/action.execute', {
    uid: actionUid,
    inputData,
    userId,
  });
  return response.data;
}
