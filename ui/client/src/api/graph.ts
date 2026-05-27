import axios from '@/http/axiosAgentConfig';

export interface GraphValidationResponse {
  validation_result: {
    is_valid: boolean;
    [key: string]: any;
  };
  fix_suggestions: any[];
}

export async function validateGraphYaml(yamlString: string): Promise<GraphValidationResponse> {
  const response = await axios.post<GraphValidationResponse>(
    '/graph/validation/all.validate',
    yamlString,
    {
      headers: {
        'Content-Type': 'text/plain',
      },
    },
  );
  return response.data;
}
