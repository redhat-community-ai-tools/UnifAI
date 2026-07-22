import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { useAgenticAI } from "@/contexts/AgenticAIContext";
import { useTheme } from "@/contexts/ThemeContext";
import { ElementInstance, ElementType, ElementSchema } from '../../../types/workspace';
import { BuiltinConfigureModal } from './BuiltinConfigureModal';
import axios from "../../../http/axiosAgentConfig";
import { isTrustedCredentialsCallback } from "@/lib/oauthPopupSecurity";
import { deriveThemeColors } from "@/lib/colorUtils";
import { cn } from "@/lib/utils";

type SignInStatus = 'idle' | 'checking' | 'authenticated' | 'challenge' | 'not_configured' | 'error';

interface ChallengeData {
  challenge_type: string;
  authorization_url?: string;
  flow_id?: string;
  scopes?: string[];
  server_identifier?: string;
}

interface SignOutAction {
  uid: string;
  label: string;
  style?: string;
  dependencies?: Record<string, string>;
}

interface DiscoveryResponse {
  status: string;
  message?: string;
  challenge?: ChallengeData;
  actions?: SignOutAction[];
  server_identifier?: string;
  scheme_type?: string;
  form_updates?: Record<string, any>;
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
  const { revalidateResourceAndAncestors } = useAgenticAI();
  const { primaryHex } = useTheme();
  // `primaryLight` is a lightened tint of the site's selected accent color —
  // using the raw `primary` color for small icon glyphs/text can be nearly
  // unreadable on the dark background for darker accent choices (e.g. red).
  const { primaryLight } = useMemo(() => deriveThemeColors(primaryHex), [primaryHex]);

  const isSignIn = hasSignInAuth(element);
  const hasConfigFields = hasConfigurableFields(element, elementSchema);

  const [signInStatus, setSignInStatus] = useState<SignInStatus>('idle');
  const [challenge, setChallenge] = useState<ChallengeData | null>(null);
  const [signInMessage, setSignInMessage] = useState('');
  const [signOutActions, setSignOutActions] = useState<SignOutAction[]>([]);
  // Auth-flow fields returned by discovery (server_identifier, scheme_type,
  // credential_token, ...) — mirrors what the regular sign-in MCP form keeps
  // in `formData` after an auth action's `form_updates`, so sign-out (and
  // any other auth action) can resolve its `dependencies` the same way.
  const [authFields, setAuthFields] = useState<Record<string, any>>({});
  const [signingOut, setSigningOut] = useState(false);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);

  const popupRef = useRef<Window | null>(null);
  const popupAuthUrlRef = useRef<string | null>(null);
  const checkedRef = useRef(false);

  // Mirrors the "action validation" flow used by AuthFieldRenderer for the
  // regular (non-built-in) sign-in MCP configuration: every action returned
  // by the discovery call carries its own `dependencies` map (config field ->
  // action input field). Inputs are resolved from this map rather than being
  // hardcoded, so sign-out (and any future auth action) works the same way
  // here as it does in the regular configuration modal.
  const resolveDependencyValue = useCallback((configField: string): any => {
    if (configField === 'mcp_url') return String(element.config?.mcp_url || '');
    return authFields[configField];
  }, [element.config?.mcp_url, authFields]);

  const checkAuth = useCallback(async (): Promise<DiscoveryResponse | null> => {
    if (!userId || !element.config?.mcp_url) return null;
    setSignInStatus('checking');
    try {
      const res = await axios.post('/actions/action.execute', {
        uid: 'auth.discovery',
        inputData: { mcp_url: String(element.config.mcp_url), user_id: userId },
        userId,
      });
      const data: DiscoveryResponse = res.data;
      const nextAuthFields = {
        ...data.form_updates,
        ...(data.server_identifier ? { server_identifier: data.server_identifier } : {}),
        ...(data.scheme_type ? { scheme_type: data.scheme_type } : {}),
      };
      if (Object.keys(nextAuthFields).length > 0) {
        setAuthFields((prev) => ({ ...prev, ...nextAuthFields }));
      }
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
      return data;
    } catch {
      setSignInStatus('error');
      setSignInMessage('Failed to check authentication status');
      return null;
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
      if (!isTrustedCredentialsCallback(event, popupRef.current, popupAuthUrlRef.current)) return;
      popupRef.current?.close();
      popupRef.current = null;
      if (event.data.success) {
        checkedRef.current = false;
        checkAuth();
        // The card's "invalid" badge is a cached real-connection probe from
        // before sign-in completed — without this it would keep showing
        // invalid forever even though the user just authenticated.
        revalidateResourceAndAncestors(element.rid);
      } else {
        setSignInStatus('error');
        setSignInMessage(event.data.error || 'Authentication failed');
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [checkAuth, element.rid, revalidateResourceAndAncestors]);

  const openAuthPopup = (url: string) => {
    popupAuthUrlRef.current = url;
    popupRef.current = window.open(url, 'oauth_signin', 'width=600,height=700,scrollbars=yes');
  };

  // Clicking "Sign In" should open the OAuth popup immediately — either
  // using an already-known challenge, or by running the discovery check
  // right now and acting on its result, instead of requiring a second
  // click once the status has caught up to 'challenge'.
  const handleSignIn = async () => {
    if (signInStatus === 'authenticated' || signInStatus === 'checking') return;

    if (signInStatus === 'challenge' && challenge?.authorization_url) {
      openAuthPopup(challenge.authorization_url);
      return;
    }

    checkedRef.current = true;
    const data = await checkAuth();
    if (data?.status === 'challenge' && data.challenge?.authorization_url) {
      openAuthPopup(data.challenge.authorization_url);
    }
  };

  const handleSignOut = async (action: SignOutAction) => {
    setSigningOut(true);
    try {
      const inputData: Record<string, any> = { user_id: userId };
      const dependencies = action.dependencies || { server_identifier: 'server_identifier' };
      Object.entries(dependencies).forEach(([configField, actionField]) => {
        const val = resolveDependencyValue(configField);
        if (val !== undefined) {
          inputData[actionField] = val;
        }
      });

      await axios.post('/actions/action.execute', {
        uid: action.uid,
        inputData,
        userId,
      });
      checkedRef.current = false;
      checkAuth();
      // Same reasoning as the sign-in callback — the cached validation
      // badge needs to catch up with the new (signed-out) auth state.
      revalidateResourceAndAncestors(element.rid);
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

  const isCardClickable = hasConfigFields;

  return (
    <>
      <Card
        className={cn(
          "group relative bg-background-card border border-white/10 h-full flex flex-col transition-all duration-300 hover:border-primary/50 hover:shadow-xl hover:shadow-primary/10",
          isCardClickable && "cursor-pointer",
        )}
        onClick={isCardClickable ? () => setIsConfigModalOpen(true) : undefined}
      >
        <CardHeader className="py-3.5 px-4 border-b border-white/5">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 transition-colors duration-300 group-hover:bg-primary/20">
                <FileText className="h-4 w-4" style={{ color: primaryLight }} />
              </div>
              <div className="min-w-0">
                <CardTitle className="text-lg font-heading truncate leading-tight" title={element.name || undefined}>
                  {element.name || `${elementType.name} Instance`}
                </CardTitle>
                <span className="inline-flex items-center gap-1 text-xs mt-0.5" style={{ color: primaryLight }}>
                  <ShieldCheck className="h-3 w-3" />
                  Built-in
                </span>
              </div>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-4 flex-grow flex flex-col items-center justify-center">
          {isSignIn ? (
            <div className="flex flex-col items-center gap-1 py-2">
              {renderSignInStatus()}
            </div>
          ) : (
            <div className="py-2 text-center">
              <p className="text-sm text-gray-500">
                Pre-configured &mdash; ready to use
              </p>
            </div>
          )}
        </CardContent>

        <CardFooter className="px-4 py-3 border-t border-white/5" onClick={(e) => e.stopPropagation()}>
          <div className="flex gap-2 w-full">
            {isSignIn && (
              <>
                {signInStatus === 'authenticated' && signOutAction ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 flex items-center justify-center gap-1.5 h-9 text-sm border-red-400/40 text-red-400 hover:bg-red-400/10"
                    disabled={signingOut}
                    onClick={() => handleSignOut(signOutAction)}
                  >
                    {signingOut ? (
                      <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Signing Out...</>
                    ) : (
                      <><LogOut className="h-3.5 w-3.5" /> Sign Out</>
                    )}
                  </Button>
                ) : signInStatus !== 'authenticated' ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 flex items-center justify-center gap-1.5 h-9 text-sm border-primary/40 text-primary hover:bg-primary/10"
                    onClick={handleSignIn}
                    disabled={signInStatus === 'checking'}
                  >
                    {signInStatus === 'checking' ? (
                      <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Checking...</>
                    ) : (
                      <><LogIn className="h-3.5 w-3.5" /> Sign In</>
                    )}
                  </Button>
                ) : null}
              </>
            )}
            {hasConfigFields && (
              <Button
                variant="outline"
                size="sm"
                className="flex-1 flex items-center justify-center gap-1.5 h-9 text-sm border-primary/30 text-primary hover:bg-primary/10 hover:border-primary/50"
                onClick={() => setIsConfigModalOpen(true)}
              >
                <Settings className="h-3.5 w-3.5" />
                Configure
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
