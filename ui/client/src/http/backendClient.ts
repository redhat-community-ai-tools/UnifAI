import axios from 'axios';

/**
 * Axios instance for the platform backend (admin config, etc.). Team and
 * directory APIs live on Identity (`/api3`), not here.
 * Proxied via /api4 -> http://127.0.0.1:8005/api
 */
export const backendApi = axios.create({
  baseURL: '/api4',
  timeout: 20000,
  withCredentials: true,
});

backendApi.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('Backend API Error:', error);

    let errorMsg = 'Failed to fetch data. Please try again.';
    const errorData = error.response?.data as { error?: string };
    if (errorData?.error) {
      errorMsg = errorData.error;
    }

    return Promise.reject(new Error(errorMsg));
  },
);

export default backendApi;
