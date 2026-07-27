/**
 * FieldValidationTwoFactorAuth — sub-component of FieldValidation.
 *
 * Owns all OAuth / two-factor auth UI concerns:
 *   - Rendering auth status indicators (authenticated, consent required, expired, …)
 *   - Opening the OAuth popup and listening for the postMessage callback
 *   - Reporting the callback result back to the parent via onRevalidate / onAuthError
 *
 * The parent (FieldValidation) keeps the auth state (authStatus, authUrl,
 * authMessage) and passes it here as props.  This component never calls
 * the validation API directly — it only requests re-validation from the parent.
 */

import React, { useEffect, useRef, useCallback } from 'react';
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Lock, LogIn } from 'lucide-react';

export interface FieldValidationTwoFactorAuthProps {
  authStatus: string;
  authUrl: string | null;
  authMessage: string | null;
  /** Called after a successful OAuth callback so the parent can re-run validation */
  onRevalidate: () => void;
  /** Called when the OAuth popup reports a failure */
  onAuthError: (errorMessage: string) => void;
}

export const FieldValidationTwoFactorAuth: React.FC<FieldValidationTwoFactorAuthProps> = ({
  authStatus,
  authUrl,
  authMessage,
  onRevalidate,
  onAuthError,
}) => {
  const popupRef = useRef<Window | null>(null);

  const handleSignIn = useCallback(() => {
    if (!authUrl) return;
    popupRef.current = window.open(authUrl, 'oauth_signin', 'width=600,height=700,scrollbars=yes');
  }, [authUrl]);

  // Listen for OAuth callback postMessage from popup
  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type !== 'credentials_callback') return;

      if (popupRef.current) {
        popupRef.current.close();
        popupRef.current = null;
      }

      if (event.data.success) {
        onRevalidate();
      } else {
        onAuthError(event.data.error || 'Authentication failed');
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [onRevalidate, onAuthError]);

  // ── Render based on auth status ──

  switch (authStatus) {
    case 'authenticated':
      return (
        <div className="flex items-center gap-2 mt-1">
          <CheckCircle className="h-4 w-4 text-green-400" />
          <span className="text-xs text-green-400">Authenticated</span>
          {authMessage && <Badge variant="outline" className="text-xs">{authMessage}</Badge>}
        </div>
      );

    case 'requires_consent':
    case 'expired':
      if (authUrl) {
        return (
          <div className="flex items-center gap-2 mt-1">
            <Lock className="h-4 w-4 text-yellow-400" />
            <span className="text-xs text-yellow-400">
              {authStatus === 'expired' ? 'Session expired' : 'Sign in required'}
            </span>
            <button
              type="button"
              onClick={handleSignIn}
              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-blue-600 hover:bg-blue-700 text-white transition-colors"
            >
              <LogIn className="h-3 w-3" />
              {authStatus === 'expired' ? 'Re-authenticate' : 'Sign In'}
            </button>
            {authMessage && <Badge variant="outline" className="text-xs">{authMessage}</Badge>}
          </div>
        );
      }
      return (
        <div className="flex items-center gap-2 mt-1">
          <Lock className="h-4 w-4 text-yellow-400" />
          <span className="text-xs text-yellow-400">{authMessage || 'Sign in required'}</span>
        </div>
      );

    case 'needs_client_registration':
      return (
        <div className="flex items-center gap-2 mt-1">
          <XCircle className="h-4 w-4 text-orange-400" />
          <span className="text-xs text-orange-400">{authMessage || 'Client registration required'}</span>
        </div>
      );

    case 'auth_required':
      return (
        <div className="flex items-center gap-2 mt-1">
          <Lock className="h-4 w-4 text-yellow-400" />
          <span className="text-xs text-yellow-400">{authMessage || 'Authentication required'}</span>
        </div>
      );

    case 'authenticated_but_rejected':
      return (
        <div className="flex items-center gap-2 mt-1">
          <XCircle className="h-4 w-4 text-red-400" />
          <span className="text-xs text-red-400">{authMessage || 'Authenticated but the server rejected the request'}</span>
        </div>
      );

    default:
      return (
        <div className="flex items-center gap-2 mt-1">
          <XCircle className="h-4 w-4 text-red-400" />
          <span className="text-xs text-red-400">{authMessage || 'Authentication error'}</span>
        </div>
      );
  }
};
