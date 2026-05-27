/**
 * AuthFieldRenderer — renders a field with an AuthHint as a Sign In / auth
 * status component instead of a normal text input.
 *
 * Driven entirely by the backend:
 *   1. The field schema contains ``hints.auth`` with ``action_uid`` and
 *      ``dependencies``.
 *   2. This component calls the action, checks the response status, and
 *      renders the appropriate UI (Sign In button, green checkmark, error).
 *   3. OAuth popup + postMessage callback are handled here.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Lock, LogIn, Loader2 } from 'lucide-react';
import { executeAction } from '@/api/actions';
import { useAuth } from "@/contexts/AuthContext";

interface AuthFieldRendererProps {
  fieldName: string;
  fieldSchema: any;
  formData: any;
  elementActions: any[];
  onValidationChange: (fieldName: string, isValid: boolean) => void;
  onInputChange?: (field: string, value: any) => void;
}

type AuthStatus = 'idle' | 'checking' | 'authenticated' | 'requires_consent' | 'expired' | 'not_configured' | 'error';

export const AuthFieldRenderer: React.FC<AuthFieldRendererProps> = ({
  fieldName,
  fieldSchema,
  formData,
  elementActions,
  onValidationChange,
  onInputChange,
}) => {
  const { user } = useAuth();
  const userId = user?.username || "";

  const authHint = fieldSchema?.hints?.auth;
  const actionUid = authHint?.action_uid;
  const dependencies = authHint?.dependencies || {};

  const [status, setStatus] = useState<AuthStatus>('idle');
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const popupRef = useRef<Window | null>(null);
  const lastCheckedKeyRef = useRef<string | null>(null);

  const dependencyKey = JSON.stringify(
    Object.keys(dependencies).reduce((acc: Record<string, any>, configField) => {
      acc[configField] = formData[configField];
      return acc;
    }, {})
  );

  const checkAuth = useCallback(async () => {
    if (!actionUid || !userId) return;

    const inputData: Record<string, any> = { user_id: userId };
    Object.entries(dependencies).forEach(([configField, actionField]) => {
      const val = formData[configField];
      if (val !== undefined) {
        inputData[actionField as string] = val;
      }
    });

    const hasRequiredDeps = Object.keys(dependencies).every(
      (configField) => formData[configField] && formData[configField] !== '',
    );
    if (!hasRequiredDeps) {
      setStatus('idle');
      setMessage('');
      onValidationChange(fieldName, true);
      return;
    }

    setStatus('checking');

    try {
      const data = await executeAction(actionUid, inputData, userId);


      if (data.status === 'authenticated') {
        setStatus('authenticated');
        setAuthUrl(null);
        setMessage(data.message || 'Authenticated');
        onValidationChange(fieldName, true);
        if (onInputChange) {
          onInputChange('scheme_type', 'oauth2');
        }
      } else if (data.status === 'requires_consent' || data.status === 'expired') {
        setStatus(data.status);
        setAuthUrl(data.authorization_url || null);
        setMessage(data.message || 'Sign in required');
        onValidationChange(fieldName, false);
      } else if (data.status === 'not_configured') {
        setStatus('not_configured');
        setAuthUrl(null);
        setMessage(data.message || 'Authentication not configured');
        onValidationChange(fieldName, false);
      } else {
        setStatus('error');
        setAuthUrl(null);
        setMessage(data.message || 'Authentication error');
        onValidationChange(fieldName, false);
      }
    } catch {
      setStatus('error');
      setMessage('Failed to check authentication status');
      onValidationChange(fieldName, false);
    }
  }, [actionUid, userId, formData, dependencies, fieldName, onValidationChange]);

  useEffect(() => {
    if (lastCheckedKeyRef.current === dependencyKey) return;

    const timer = setTimeout(() => {
      lastCheckedKeyRef.current = dependencyKey;
      checkAuth();
    }, 500);

    return () => clearTimeout(timer);
  }, [dependencyKey, checkAuth]);

  const handleSignIn = useCallback(() => {
    if (!authUrl) return;
    popupRef.current = window.open(authUrl, 'oauth_signin', 'width=600,height=700,scrollbars=yes');
  }, [authUrl]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type !== 'credentials_callback') return;

      if (popupRef.current) {
        popupRef.current.close();
        popupRef.current = null;
      }

      if (event.data.success) {
        lastCheckedKeyRef.current = null;
        checkAuth();
      } else {
        setStatus('error');
        setMessage(event.data.error || 'Authentication failed');
        onValidationChange(fieldName, false);
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [checkAuth, fieldName, onValidationChange]);

  const renderStatus = () => {
    switch (status) {
      case 'checking':
        return (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
            <span className="text-xs text-blue-400">Checking authentication...</span>
          </div>
        );

      case 'authenticated':
        return (
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-400" />
            <span className="text-xs text-green-400">Authenticated</span>
            {message && <Badge variant="outline" className="text-xs">{message}</Badge>}
          </div>
        );

      case 'requires_consent':
      case 'expired':
        return (
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-yellow-400" />
            <span className="text-xs text-yellow-400">
              {status === 'expired' ? 'Session expired' : 'Sign in required'}
            </span>
            {authUrl && (
              <button
                type="button"
                onClick={handleSignIn}
                className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white transition-colors"
              >
                <LogIn className="h-3 w-3" />
                {status === 'expired' ? 'Re-authenticate' : 'Sign In'}
              </button>
            )}
          </div>
        );

      case 'not_configured':
        return (
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-orange-400" />
            <span className="text-xs text-orange-400">{message || 'Authentication not configured'}</span>
          </div>
        );

      case 'error':
        return (
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-red-400" />
            <span className="text-xs text-red-400">{message || 'Authentication error'}</span>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div key={fieldName} className="space-y-2">
      <Label htmlFor={fieldName} className="flex items-center gap-1">
        {fieldSchema.description || fieldName}
      </Label>
      {renderStatus()}
    </div>
  );
};
