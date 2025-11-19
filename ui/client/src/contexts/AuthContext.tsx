import { api } from '@/http/authClient';
import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';

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
    window.location.href = `${api.defaults.baseURL}/auth/login`;
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
    
    if (authStatus === 'success') {
      // Remove auth params from URL
      window.history.replaceState({}, document.title, window.location.pathname);
      // Check auth status after successful login
      checkAuthStatus();
    } else if (authStatus === 'error') {
      // Remove auth params from URL
      window.history.replaceState({}, document.title, window.location.pathname);
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