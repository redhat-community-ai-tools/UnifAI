// import { QueryClient, QueryFunction } from "@tanstack/react-query";
import axios, { AxiosError } from 'axios';

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
  
  // Response interceptor to handle authentication errors
  api.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      console.error("API Error:", error);
  
      // Handle authentication errors
      if (error.response?.status === 401) {
        // Check if we're not already on an auth-related endpoint
        const isAuthEndpoint = error.config?.url?.includes('/auth');
        
        if (!isAuthEndpoint) {
          // Redirect to login for non-auth endpoints
          window.location.href = `${api.defaults.baseURL}/auth/login`;
          return Promise.reject(new Error("Authentication required"));
        }
      }
  
      // Default error message
      let errorMsg = "Failed to fetch data. Please try again.";
  
      // Cast error.response.data to our custom type
      const errorData = error.response?.data as APIErrorResponse;
  
      if (errorData?.error) {
        errorMsg = errorData.error;
      }
  
      return Promise.reject(new Error(errorMsg)); // Reject with cleaned-up error message
    }
  );