// import { QueryClient, QueryFunction } from "@tanstack/react-query";
import axios, { AxiosError } from 'axios';

interface APIErrorResponse {
  error?: string; // Mark `error` as optional since it may not always exist
}

export const api = axios.create({
    baseURL: '/api3',
    // baseURL: '/',
    timeout: 20000, // 20 seconds
    withCredentials: true, // Important: This ensures cookies are sent with requests
  });

  api.interceptors.request.use(
    (config) => {
      // Ensure credentials are always sent
      config.withCredentials = true;
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );
  
  api.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      console.error("API Error:", error);

      if (error.response?.status === 401) {
        const isAuthEndpoint = error.config?.url?.includes('/auth');
        
        if (!isAuthEndpoint) {
          // Capture the original URL to restore after authentication
          const originalUrl = window.location.pathname + window.location.search;
          const stateData = { originalUrl: originalUrl || '/' };
          const encodedState = btoa(JSON.stringify(stateData));
          window.location.href = `${api.defaults.baseURL}/auth/login?state=${encodeURIComponent(encodedState)}`;
          return Promise.reject(new Error("Authentication required"));
        }
      }

      let errorMsg = "Failed to fetch data. Please try again.";
      const errorData = error.response?.data as APIErrorResponse;
  
      if (errorData?.error) {
        errorMsg = errorData.error;
      }
  
      return Promise.reject(new Error(errorMsg));
    }
  );