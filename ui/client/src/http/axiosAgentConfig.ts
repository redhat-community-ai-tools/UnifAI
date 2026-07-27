import axios from 'axios';

const axiosInstance = axios.create({
  baseURL: '/api2',
  timeout: 300000, // 300 seconds
  withCredentials: true,
});

export default axiosInstance;