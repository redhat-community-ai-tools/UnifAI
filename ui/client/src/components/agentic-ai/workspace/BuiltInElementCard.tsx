import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  ShieldCheck,
  LogIn,
  LogOut,
  Settings,
  Loader2,
  CheckCircle,
  XCircle,
  Lock,
} from 'lucide-react';
import { useAuth } from "@/contexts/AuthContext";
import { ElementInstance, ElementType, ElementSchema } from '../../../types/workspace';
import { BuiltinConfigureModal } from './BuiltinConfigureModal';
import axios from "../../../http/axiosAgentConfig";

type SignInStatus = 'idle' | 'checking' | 'authenticated' | 'challenge' | 'not_configured' | 'error';

interface ChallengeData {
  challenge_type: string;
  authorization_url?: string;
  flow_id?: string;
  scopes?: string[];
  server_identifier?: string;
}

interface BuiltInElementCardProps {
  element: ElementInstance;
  elementType: ElementType;
  elementSchema?: ElementSchema | null;
  onConfigureBuiltin?: (rid: string, config: Record<string, any>) => Promise<any>;
  index: number;
}

function hasSignInAuth(element: ElementInstance): boolean {
  return element.config?.auth_method === 'sign_in';
}

function hasConfigurableFields(element: ElementInstance, elementSchema?: ElementSchema | null): boolean {
  if (!elementSchema?.config_schema?.properties) return false;
  return Object.values(elementSchema.config_schema.properties).some(
    (field: any) => field?.hints?.read_only?.read_only === false
  );
}

export const BuiltInElementCard: React.FC<BuiltInElementCardProps> = ({
  element,
  elementType,
  elementSchema,
  onConfigureBuiltin,
  index,
}) => {
  const { user } = useAuth();
  const userId = user?.username || '';

  const isSignIn = hasSignInAuth(element);
  const hasConfigFields = hasConfigurableFields(element, elementSchema);

  const [signInStatus, setSignInStatus] = useState<SignInStatus>('idle');
  const [challenge, setChallenge] = useState<ChallengeData | null>(null);
  const [signInMessage, setSignInMessage] = useState('');
  const [signOutActions, setSignOutActions] = useState<Array<{ uid: string; label: string; style?: string }>>([]);
  const [signingOut, setSigningOut] = useState(false);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);

  const popupRef = useRef<Window | null>(null);
  const checkedRef = useRef(false);

  const checkAuth = useCallback(async () => {
    if (!userId || !element.config?.mcp_url) return;
    setSignInStatus('checking');
    try {
      const res = await axios.post('/actions/action.execute', {
        uid: 'auth.discovery',
        inputData: { mcp_url: String(element.config.mcp_url), user_id: userId },
        userId,
      });
      const data = res.data;
      if (data.status === 'authenticated') {
        setSignInStatus('authenticated');
        setSignInMessage(data.message || 'Authenticated');
        setSignOutActions(data.actions || []);
      } else if (data.status === 'challenge' && data.challenge) {
        setSignInStatus('challenge');
        setChallenge(data.challenge);
        setSignInMessage(data.message || 'Sign in required');
      } else if (data.status === 'not_configured') {
        setSignInStatus('not_configured');
        setSignInMessage(data.message || 'Authentication not configured');
      } else {
        setSignInStatus('error');
        setSignInMessage(data.message || 'Could not determine auth status');
      }
    } catch {
      setSignInStatus('error');
      setSignInMessage('Failed to check authentication status');
    }
  }, [userId, element.config?.mcp_url]);

  useEffect(() => {
    if (isSignIn && !checkedRef.current) {
      checkedRef.current = true;
      checkAuth();
    }
  }, [isSignIn, checkAuth]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type !== 'credentials_callback') return;
      // Only trust messages from the popup window we actually opened —
      // the identity service's callback page runs on a different origin
      // than the frontend (no client-exposed config for that origin today),
      // so we validate the message source instead of event.origin.
      if (!popupRef.current || event.source !== popupRef.current) return;
      popupRef.current.close();
      popupRef.current = null;
      if (event.data.success) {
        checkedRef.current = false;
        checkAuth();
      } else {
        setSignInStatus('error');
        setSignInMessage(event.data.error || 'Authentication failed');
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [checkAuth]);

  const handleSignIn = () => {
    if (signInStatus === 'challenge' && challenge?.authorization_url) {
      popupRef.current = window.open(
        challenge.authorization_url,
        'oauth_signin',
        'width=600,height=700,scrollbars=yes',
      );
    } else if (signInStatus !== 'authenticated' && signInStatus !== 'checking') {
      checkedRef.current = false;
      checkAuth();
    }
  };

  const handleSignOut = async (actionUid: string) => {
    setSigningOut(true);
    try {
      await axios.post('/actions/action.execute', {
        uid: actionUid,
        inputData: { mcp_url: String(element.config?.mcp_url || ''), user_id: userId },
        userId,
      });
      checkedRef.current = false;
      checkAuth();
    } catch {
      setSignInStatus('error');
      setSignInMessage('Sign out failed');
    } finally {
      setSigningOut(false);
    }
  };

  const handleConfigureSave = async (config: Record<string, any>) => {
    if (onConfigureBuiltin) {
      await onConfigureBuiltin(element.rid, config);
    }
  };

  const renderSignInStatus = () => {
    if (!isSignIn) return null;

    switch (signInStatus) {
      case 'checking':
        return (
          <div className="flex items-center gap-2 text-blue-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-xs">Checking...</span>
          </div>
        );
      case 'authenticated':
        return (
          <div className="flex items-center gap-2 text-green-400">
            <CheckCircle className="h-4 w-4" />
            <span className="text-xs font-medium">Signed In</span>
          </div>
        );
      case 'error':
        return (
          <div className="flex items-center gap-2 text-red-400">
            <XCircle className="h-4 w-4" />
            <span className="text-xs">{signInMessage}</span>
          </div>
        );
      case 'not_configured':
        return (
          <div className="flex items-center gap-2 text-orange-400">
            <XCircle className="h-4 w-4" />
            <span className="text-xs">{signInMessage}</span>
          </div>
        );
      case 'challenge':
        return (
          <div className="flex items-center gap-2 text-yellow-400">
            <Lock className="h-4 w-4" />
            <span className="text-xs">Sign in required</span>
          </div>
        );
      default:
        return null;
    }
  };

  const signOutAction = signOutActions.find(a => a.style === 'danger');

  return (
    <>
      <Card className="bg-background-card shadow-card border-primary/20 h-full flex flex-col">
        <CardHeader className="py-4 px-6 border-b border-gray-800">
          <div className="flex justify-between items-start">
            <div className="flex items-center gap-2 min-w-0">
              <FileText className="h-5 w-5 flex-shrink-0 text-primary" />
              <CardTitle className="text-lg font-heading truncate">
                {element.name || `${elementType.name} Instance`}
              </CardTitle>
              <Badge className="bg-primary/15 text-primary border-primary/30 text-[10px] px-1.5 py-0 font-medium flex-shrink-0 gap-1">
                <ShieldCheck className="h-3 w-3" />
                Built-in
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-4 flex-grow flex flex-col items-center justify-center">
          {isSignIn ? (
            <div className="flex flex-col items-center gap-2 py-4">
              {renderSignInStatus()}
            </div>
          ) : (
            <div className="py-4 text-center">
              <p className="text-xs text-gray-500">
                Pre-configured &mdash; ready to use
              </p>
            </div>
          )}
        </CardContent>

        <CardFooter className="px-6 py-3 border-t border-gray-800 bg-background-dark">
          <div className="flex gap-2 w-full">
            {isSignIn && (
              <>
                {signInStatus === 'authenticated' && signOutAction ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 flex items-center justify-center gap-2 border-red-400/40 text-red-400 hover:bg-red-400/10"
                    disabled={signingOut}
                    onClick={() => handleSignOut(signOutAction.uid)}
                  >
                    {signingOut ? (
                      <><Loader2 className="h-3 w-3 animate-spin" /> Signing Out...</>
                    ) : (
                      <><LogOut className="h-3 w-3" /> Sign Out</>
                    )}
                  </Button>
                ) : signInStatus !== 'authenticated' ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 flex items-center justify-center gap-2 border-primary/40 text-primary hover:bg-primary/10"
                    onClick={handleSignIn}
                    disabled={signInStatus === 'checking'}
                  >
                    {signInStatus === 'checking' ? (
                      <><Loader2 className="h-3 w-3 animate-spin" /> Checking...</>
                    ) : (
                      <><LogIn className="h-3 w-3" /> Sign In</>
                    )}
                  </Button>
                ) : null}
              </>
            )}
            {hasConfigFields && (
              <Button
                variant="outline"
                size="sm"
                className="flex-1 flex items-center justify-center gap-2"
                onClick={() => setIsConfigModalOpen(true)}
              >
                <Settings className="h-3 w-3" />
                Configure Fields
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>

      {hasConfigFields && (
        <BuiltinConfigureModal
          isOpen={isConfigModalOpen}
          onClose={() => setIsConfigModalOpen(false)}
          element={element}
          elementType={elementType}
          elementSchema={elementSchema}
          onSave={handleConfigureSave}
        />
      )}
    </>
  );
};
