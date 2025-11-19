import { QueryClient, QueryFunction } from "@tanstack/react-query";
import axios, { AxiosError } from 'axios';

interface APIErrorResponse {
  error?: string; // Mark `error` as optional since it may not always exist
}

export const api = axios.create({
  baseURL: '/api1',
  // baseURL: '/',
  timeout: 20000, // 20 seconds
  withCredentials: true, // Important: This ensures cookies are sent with requests
});

// Request interceptor to handle authentication
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

async function throwIfResNotOk(res: Response) {
  if (!res.ok) {
    const text = (await res.text()) || res.statusText;
    throw new Error(`${res.status}: ${text}`);
  }
}

export async function apiRequest(
  method: string,
  url: string,
  data?: unknown | undefined,
): Promise<Response> {
  const res = await fetch(url, {
    method,
    headers: data ? { "Content-Type": "application/json" } : {},
    body: data ? JSON.stringify(data) : undefined,
    credentials: "include",
  });

  await throwIfResNotOk(res);
  return res;
}

type UnauthorizedBehavior = "returnNull" | "throw";
export const getQueryFn: <T>(options: {
  on401: UnauthorizedBehavior;
}) => QueryFunction<T> =
  ({ on401: unauthorizedBehavior }) =>
  async ({ queryKey }) => {
    const res = await fetch(queryKey[0] as string, {
      credentials: "include",
    });

    if (unauthorizedBehavior === "returnNull" && res.status === 401) {
      return null;
    }

    await throwIfResNotOk(res);
    return await res.json();
  };

  
//Generic QueryFunction for React Query using Axios
export const axiosQueryFn: QueryFunction<any> = async ({ queryKey }) => {
  const [url, params] = queryKey as [string, Record<string, any>?];
  const response = await api.get(url, params ? { params } : undefined);
  return response.data;
};

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: axiosQueryFn,
      staleTime: 5 * 60_000,          // cache data for 5 minutes
      retry: 1,                       // retry once on failure
      refetchInterval: false,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});
