/**
 * AuthFieldRenderer — renders a field with an AuthHint as an auth status
 * component instead of a normal text input.
 *
 * Driven entirely by the backend:
 *   1. The field schema contains ``hints.auth`` with ``action_uid`` and
 *      ``dependencies``.
 *   2. This component calls the action, checks the response status, and
 *      renders the appropriate UI.
 *   3. When status is "challenge", delegates to a challenge-type renderer
 *      via registry lookup (consent → OAuth popup, collect → input form).
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Lock, LogIn, Loader2 } from 'lucide-react';
import { executeAction } from "@/api/actions";
import { useAuth } from "@/contexts/AuthContext";

interface AuthFieldRendererProps {
  fieldName: string;
  fieldSchema: any;
  formData: any;
  elementActions: any[];
  onValidationChange: (fieldName: string, isValid: boolean) => void;
  onInputChange?: (field: string, value: any) => void;
  onActionOutput?: (fieldName: string, output: any) => void;
}

type AuthStatus = 'idle' | 'checking' | 'authenticated' | 'challenge' | 'not_configured' | 'error';

interface ChallengeData {
  challenge_type: string;
  authorization_url?: string;
  fields?: Array<{ name: string; label: string; secret?: boolean }>;
  flow_id?: string;
  scopes?: string[];
  server_identifier?: string;
}

// ── Challenge renderers (registry) ──────────────────────────────────────

interface ChallengeRendererProps {
  challenge: ChallengeData;
  message: string;
  onSignIn: () => void;
}

const ConsentChallenge: React.FC<ChallengeRendererProps> = ({ challenge, message, onSignIn }) => (
  <div className="flex items-center gap-2">
    <Lock className="h-4 w-4 text-yellow-400" />
    <span className="text-xs text-yellow-400">{message || 'Sign in required'}</span>
    {challenge.authorization_url && (
      <button
        type="button"
        onClick={onSignIn}
        className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white transition-colors"
      >
        <LogIn className="h-3 w-3" />
        Sign In
      </button>
    )}
  </div>
);

const CollectChallenge: React.FC<ChallengeRendererProps> = ({ challenge, message }) => (
  <div className="flex items-center gap-2">
    <Lock className="h-4 w-4 text-yellow-400" />
    <span className="text-xs text-yellow-400">{message || 'Credentials required'}</span>
  </div>
);

const CHALLENGE_RENDERERS: Record<string, React.FC<ChallengeRendererProps>> = {
  consent: ConsentChallenge,
  collect: CollectChallenge,
};

// ── Main component ──────────────────────────────────────────────────────

export const AuthFieldRenderer: React.FC<AuthFieldRendererProps> = ({
  fieldName,
  fieldSchema,
  formData,
  elementActions,
  onValidationChange,
  onInputChange,
  onActionOutput,
}) => {
  const { user } = useAuth();
  const userId = user?.username || "";

  const authHint = fieldSchema?.hints?.auth;
  const actionUid = authHint?.action_uid;
  const dependencies = authHint?.dependencies || {};

  const [status, setStatus] = useState<AuthStatus>('idle');
  const [challenge, setChallenge] = useState<ChallengeData | null>(null);
  const [message, setMessage] = useState('');
  const [availableActions, setAvailableActions] = useState<any[]>([]);
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

      if (onActionOutput) {
        onActionOutput(fieldName, data);
      }

      if (onInputChange && data.form_updates) {
        for (const [field, value] of Object.entries(data.form_updates)) {
          onInputChange(field, value);
        }
      }

      setAvailableActions(data.actions || []);

      if (data.status === 'authenticated') {
        setStatus('authenticated');
        setChallenge(null);
        setMessage(data.message || 'Authenticated');
        onValidationChange(fieldName, true);
      } else if (data.status === 'challenge' && data.challenge) {
        setStatus('challenge');
        setChallenge(data.challenge);
        setMessage(data.message || 'Sign in required');
        onValidationChange(fieldName, false);
      } else if (data.status === 'not_configured') {
        setStatus('not_configured');
        setChallenge(null);
        setMessage(data.message || 'Authentication not configured');
        onValidationChange(fieldName, false);
      } else {
        setStatus('error');
        setChallenge(null);
        setMessage(data.message || 'Authentication error');
        onValidationChange(fieldName, false);
      }
    } catch {
      setStatus('error');
      setMessage('Failed to check authentication status');
      onValidationChange(fieldName, false);
    }
  }, [actionUid, userId, formData, dependencies, fieldName, onValidationChange, onInputChange]);

  useEffect(() => {
    if (lastCheckedKeyRef.current === dependencyKey) return;

    const timer = setTimeout(() => {
      lastCheckedKeyRef.current = dependencyKey;
      checkAuth();
    }, 500);

    return () => clearTimeout(timer);
  }, [dependencyKey, checkAuth]);

  const handleSignIn = useCallback(() => {
    if (!challenge?.authorization_url) return;
    popupRef.current = window.open(challenge.authorization_url, 'oauth_signin', 'width=600,height=700,scrollbars=yes');
  }, [challenge]);

  const handleActionClick = useCallback(async (action: any) => {
    const inputData: Record<string, any> = { user_id: userId };
    if (action.dependencies) {
      for (const [configField, actionField] of Object.entries(action.dependencies)) {
        const val = formData[configField as string];
        if (val !== undefined) {
          inputData[actionField as string] = val;
        }
      }
    }
    try {
      const result = await executeAction(action.uid, inputData, userId);
      if (onInputChange && result?.form_updates) {
        for (const [field, value] of Object.entries(result.form_updates)) {
          onInputChange(field, value);
        }
      }
      lastCheckedKeyRef.current = null;
      checkAuth();
    } catch {
      setStatus('error');
      setMessage('Action failed');
      onValidationChange(fieldName, false);
    }
  }, [userId, formData, onInputChange, checkAuth, fieldName, onValidationChange]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type !== 'credentials_callback') return;

      if (popupRef.current) {
        popupRef.current.close();
        popupRef.current = null;
      }

      if (event.data.success) {
        lastCheckedKeyRef.current = null;
        if (onInputChange) {
          onInputChange(fieldName, 'authenticated');
        }
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

  // ── Render ──────────────────────────────────────────────────────────────

  const renderContent = () => {
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
            {availableActions.map((action) => (
              <button
                key={action.uid}
                type="button"
                onClick={() => handleActionClick(action)}
                className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${
                  action.style === 'danger'
                    ? 'bg-red-600/20 hover:bg-red-600/40 text-red-400 border border-red-600/30'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                {action.label}
              </button>
            ))}
          </div>
        );

      case 'challenge': {
        if (!challenge) return null;
        const Renderer = CHALLENGE_RENDERERS[challenge.challenge_type];
        if (!Renderer) {
          return (
            <div className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-yellow-400" />
              <span className="text-xs text-yellow-400">{message}</span>
            </div>
          );
        }
        return <Renderer challenge={challenge} message={message} onSignIn={handleSignIn} />;
      }

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
      {renderContent()}
    </div>
  );
};
