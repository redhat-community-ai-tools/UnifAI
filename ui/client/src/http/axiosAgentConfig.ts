import axios from 'axios';

let _sessionId = '';

export function setSessionId(id: string) {
  _sessionId = id;
}

const axiosInstance = axios.create({
  baseURL: '/api2',
  timeout: 300000, // 300 seconds
});

axiosInstance.interceptors.request.use((config) => {
  if (_sessionId) {
    config.headers['X-Session-Id'] = _sessionId;
  }
  return config;
});

export default axiosInstance;