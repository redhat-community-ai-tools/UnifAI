import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Lock, LogIn, CheckCircle, Loader2, XCircle, Globe } from 'lucide-react';
import { getProviderIcon } from '@/components/shared/providerIcons';
import { executeAction } from '@/api/actions';
import { useAuth } from "@/contexts/AuthContext";

interface AuthOption {
  rid: string;
  name: string;
  type: string;
  config?: {
    server_identifier?: string;
    display_name?: string;
    [key: string]: any;
  };
}

interface AuthSelectorProps {
  fieldName: string;
  value: any;
  refOptions: AuthOption[];
  actionUid: string;
  onInputChange: (field: string, value: any) => void;
  isRequired?: boolean;
  description?: string;
}

type AuthState = 'idle' | 'checking' | 'authenticated' | 'requires_consent' | 'error';

interface OptionAuthState {
  status: AuthState;
  authUrl: string | null;
  message: string;
  serverIdentifier: string;
}


export const AuthSelector: React.FC<AuthSelectorProps> = ({
  fieldName,
  value,
  refOptions,
  actionUid,
  onInputChange,
  isRequired = false,
  description,
}) => {
  const { user } = useAuth();
  const userId = user?.username || "";

  const [authStates, setAuthStates] = useState<Record<string, OptionAuthState>>({});
  const popupRef = useRef<Window | null>(null);
  const activeOptionRef = useRef<string | null>(null);

  const updateAuthState = (rid: string, update: Partial<OptionAuthState>) => {
    setAuthStates(prev => ({
      ...prev,
      [rid]: { ...prev[rid], ...update },
    }));
  };

  const checkAuthStatus = useCallback(async (option: AuthOption) => {
    const serverIdentifier = option.config?.server_identifier;
    if (!serverIdentifier || !userId) return;

    updateAuthState(option.rid, {
      status: 'checking',
      authUrl: null,
      message: '',
      serverIdentifier,
    });

    try {
      const data = await executeAction(
        actionUid,
        { server_identifier: serverIdentifier },
      );

      if (data.status === 'authenticated') {
        updateAuthState(option.rid, { status: 'authenticated', message: 'Authenticated' });
        if (value === option.rid) {
          onInputChange('server_identifier', serverIdentifier);
        }
      } else if (data.status === 'requires_consent' || data.status === 'expired') {
        updateAuthState(option.rid, {
          status: 'requires_consent',
          authUrl: data.authorization_url || null,
          message: data.message || 'Sign in required',
        });
      } else {
        updateAuthState(option.rid, {
          status: 'error',
          message: data.message || 'Authentication not available',
        });
      }
    } catch {
      updateAuthState(option.rid, {
        status: 'error',
        message: 'Failed to check auth status',
      });
    }
  }, [userId, value, onInputChange]);

  const handleCardClick = useCallback((option: AuthOption) => {
    const state = authStates[option.rid];

    onInputChange(fieldName, option.rid);
    if (option.config?.server_identifier) {
      onInputChange('server_identifier', option.config.server_identifier);
    }

    if (state?.status === 'requires_consent' && state.authUrl) {
      activeOptionRef.current = option.rid;
      popupRef.current = window.open(
        state.authUrl, 'oauth_signin', 'width=600,height=700,scrollbars=yes',
      );
    } else if (!state || state.status === 'idle') {
      checkAuthStatus(option);
    }
  }, [authStates, fieldName, onInputChange, checkAuthStatus]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === 'credentials_callback') {
        if (popupRef.current) {
          popupRef.current.close();
          popupRef.current = null;
        }

        const rid = activeOptionRef.current;
        if (!rid) return;

        if (event.data.success) {
          const option = refOptions.find(o => o.rid === rid);
          if (option) checkAuthStatus(option);
        } else {
          updateAuthState(rid, {
            status: 'error',
            message: event.data.error || 'Authentication failed',
          });
        }
        activeOptionRef.current = null;
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [refOptions, checkAuthStatus]);

  useEffect(() => {
    if (refOptions.length > 0 && userId) {
      refOptions.forEach(option => {
        if (!authStates[option.rid]) checkAuthStatus(option);
      });
    }
  }, [refOptions, userId]);

  return (
    <div key={fieldName} className="space-y-3">
      <div className="p-2">
        <p className="text-center text-sm text-gray-300 mb-4">Sign in with</p>

        <div className="space-y-2 max-w-sm mx-auto">
          {refOptions.map((option) => {
            const state = authStates[option.rid];
            const isSelected = value === option.rid;
            const isAuthenticated = state?.status === 'authenticated';
            const isChecking = state?.status === 'checking';
            const needsConsent = state?.status === 'requires_consent';
            const displayName = option.config?.display_name || option.name;

            return (
              <button
                key={option.rid}
                type="button"
                onClick={() => handleCardClick(option)}
                disabled={isChecking}
                className={`w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-md border text-sm font-medium transition-all ${
                  isAuthenticated
                    ? 'border-green-500/50 bg-green-500/10 text-green-400'
                    : isSelected
                      ? 'border-blue-500 bg-blue-500/10 text-white'
                      : 'border-gray-600 bg-background hover:bg-gray-800 hover:border-gray-400 text-gray-200'
                }`}
              >
                {isChecking ? (
                  <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
                ) : isAuthenticated ? (
                  <CheckCircle className="h-5 w-5 text-green-400" />
                ) : (
                  getProviderIcon(option.type)
                )}

                <span>{displayName}</span>

                {isAuthenticated && (
                  <Badge variant="outline" className="ml-auto text-[10px] border-green-500/50 text-green-400">
                    connected
                  </Badge>
                )}
                {needsConsent && !isAuthenticated && (
                  <LogIn className="h-4 w-4 ml-auto text-blue-400" />
                )}
              </button>
            );
          })}

          {refOptions.length === 0 && (
            <div className="text-center py-4">
              <Globe className="h-8 w-8 text-gray-600 mx-auto mb-2" />
              <p className="text-xs text-gray-500">
                No auth elements available.<br />
                Create one in the Auths category first.
              </p>
            </div>
          )}
        </div>

        {refOptions.some(o => authStates[o.rid]?.status === 'error') && (
          <div className="mt-3 flex items-center justify-center gap-1 text-xs text-red-400">
            <XCircle className="h-3 w-3" />
            <span>Some auth providers are not configured</span>
          </div>
        )}
      </div>
    </div>
  );
};
