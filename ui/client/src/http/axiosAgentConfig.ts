import axios from 'axios';

let _authenticatedUser = '';

export function setAuthenticatedUser(username: string) {
  _authenticatedUser = username;
}

const axiosInstance = axios.create({
  baseURL: '/api2',
  timeout: 300000, // 300 seconds
});

axiosInstance.interceptors.request.use((config) => {
  if (_authenticatedUser) {
    config.headers['X-Authenticated-User'] = _authenticatedUser;
  }
  return config;
});

export default axiosInstance;