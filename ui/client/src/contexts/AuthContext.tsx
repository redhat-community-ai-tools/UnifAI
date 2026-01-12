import { api } from '@/http/authClient';
import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { loadAnalytics } from '@/components/shared/LoadAnalytics';

export interface User {
  username: string;
  email: string;
  name: string;
  sub: string;
  token_expires_at: number;
}

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => Promise<void>;
  checkAuthStatus: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Load analytics after authentication
  loadAnalytics(isAuthenticated, user);

  // Check authentication status
  const checkAuthStatus = async () => {
    try {
      const response = await api.get('/auth/user');
      if (response.data.authenticated && response.data.user) {
        setUser(response.data.user);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Initiate login by redirecting to backend auth endpoint
  const login = () => {
    // Capture the original URL (pathname + search params) to restore after authentication
    const originalUrl = window.location.pathname + window.location.search;
    
    // Encode the original URL in the OAuth state parameter (base64 encoded JSON)
    const stateData = { originalUrl: originalUrl || '/' };
    const encodedState = btoa(JSON.stringify(stateData));
    
    // Pass state to backend, which will forward it to Keycloak
    window.location.href = `${api.defaults.baseURL}/auth/login?state=${encodeURIComponent(encodedState)}`;
  };

  // Logout user
  const logout = async () => {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      // Redirect to login
      login();
    }
  };

  // Handle authentication callback from URL params
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const authStatus = urlParams.get('auth');
    const stateParam = urlParams.get('state');
    
    if (authStatus === 'success') {
      // Extract original URL from state parameter
      let originalUrl = '/';
      if (stateParam) {
        try {
          const decodedState = JSON.parse(atob(decodeURIComponent(stateParam)));
          originalUrl = decodedState.originalUrl || '/';
        } catch (error) {
          console.error('Failed to decode state parameter:', error);
        }
      }
      
      // Remove auth params from URL (normalize pathname to avoid protocol-relative URL issues)
      const cleanPath = window.location.pathname.replace(/^\/+/, '/') || '/';
      window.history.replaceState({}, document.title, cleanPath);
      
      // Check auth status after successful login
      checkAuthStatus().then(() => {
        // Restore the original URL after authentication is confirmed
        if (originalUrl && originalUrl !== '/') {
          window.location.replace(originalUrl);
        }
      });
    } else if (authStatus === 'error') {
      // On error, try to preserve the original URL from state and retry login
      if (stateParam) {
        try {
          const decodedState = JSON.parse(atob(decodeURIComponent(stateParam)));
          const originalUrl = decodedState.originalUrl || '/';
          console.log('Authentication failed, retrying with preserved URL:', originalUrl);
          
          // Re-encode state and retry login
          const stateData = { originalUrl };
          const encodedState = btoa(JSON.stringify(stateData));
          window.location.href = `${api.defaults.baseURL}/auth/login?state=${encodeURIComponent(encodedState)}`;
          return; // Don't set loading to false yet, we're redirecting
        } catch (error) {
          console.error('Failed to decode state parameter on error:', error);
        }
      }
      // Remove auth params from URL (normalize pathname to avoid protocol-relative URL issues)
      const cleanPath = window.location.pathname.replace(/^\/+/, '/') || '/';
      window.history.replaceState({}, document.title, cleanPath);
      setIsLoading(false);
      console.error('Authentication failed');
    } else {
      // Initial load - check if user is already authenticated
      checkAuthStatus();
    }
  }, []);
  
  // Set up token refresh and expiration checking
  useEffect(() => {
    if (!isAuthenticated || !user) return;

    const checkTokenExpiration = () => {
      const now = Date.now() / 1000; // Current time in seconds
      const expiresAt = user.token_expires_at;
      const timeUntilExpiry = expiresAt - now;

      // If token expires in less than 1 minutes, try to refresh
      if (timeUntilExpiry < 60) {
        refreshToken();
      }
    };

    const refreshToken = async () => {
      try {
        await api.post('/auth/refresh');
        // Recheck auth status to get updated token info
        await checkAuthStatus();
      } catch (error) {
        console.error('Token refresh failed:', error);
        // If refresh fails, redirect to login
        login();
      }
    };

    // Check token expiration every 10 minute
    const interval = setInterval(checkTokenExpiration, 600000);

    // Initial check
    checkTokenExpiration();

    return () => clearInterval(interval);
  }, [isAuthenticated, user]);

  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    checkAuthStatus,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
