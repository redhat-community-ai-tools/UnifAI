import { useCallback, useEffect, useRef, useState } from "react";
import { executeAction } from "@/api/actions";
import { isTrustedCredentialsCallback } from "@/lib/oauthPopupSecurity";
import { ElementInstance } from "../types/workspace";

export type SignInStatus = "idle" | "checking" | "authenticated" | "challenge" | "not_configured" | "error";

export interface ChallengeData {
  challenge_type: string;
  authorization_url?: string;
  flow_id?: string;
  scopes?: string[];
  server_identifier?: string;
}

export interface SignOutAction {
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

interface UseBuiltinSignInParams {
  element: ElementInstance;
  userId: string;
  isSignIn: boolean;
  onConfigureBuiltin?: (
    rid: string,
    config: Record<string, any>,
    options?: { silent?: boolean },
  ) => Promise<any>;
  /** Called after sign-in/out completes, so the caller can re-run its own validation. */
  onAuthChange: () => void;
}

/**
 * Drives the sign-in/out flow for a built-in "sign in" MCP card: runs
 * `auth.discovery`, manages the OAuth popup handshake, and persists the
 * discovered `server_identifier` back onto the resource (there's no wizard
 * Save step for built-ins to do this after the fact) so later validations
 * can use a fast credential lookup instead of a live rediscovery probe.
 */
export function useBuiltinSignIn({
  element,
  userId,
  isSignIn,
  onConfigureBuiltin,
  onAuthChange,
}: UseBuiltinSignInParams) {
  const [signInStatus, setSignInStatus] = useState<SignInStatus>("idle");
  const [challenge, setChallenge] = useState<ChallengeData | null>(null);
  const [signInMessage, setSignInMessage] = useState("");
  const [signOutActions, setSignOutActions] = useState<SignOutAction[]>([]);
  // Auth-flow fields from discovery (server_identifier, scheme_type, ...) —
  // resolves sign-out's `dependencies` the same way AuthFieldRenderer does.
  const [authFields, setAuthFields] = useState<Record<string, any>>({});
  const [signingOut, setSigningOut] = useState(false);

  const popupRef = useRef<Window | null>(null);
  const popupAuthUrlRef = useRef<string | null>(null);
  const checkedRef = useRef(false);
  const persistedIdentifierRef = useRef<string>(String(element.config?.server_identifier || ""));

  const persistAuthIdentifier = useCallback((serverIdentifier?: string, schemeType?: string) => {
    if (!onConfigureBuiltin || !serverIdentifier) return;
    if (persistedIdentifierRef.current === serverIdentifier) return;
    const previous = persistedIdentifierRef.current;
    persistedIdentifierRef.current = serverIdentifier;
    onConfigureBuiltin(
      element.rid,
      { server_identifier: serverIdentifier, scheme_type: schemeType || "" },
      { silent: true },
    ).then(() => {
      // A validation badge cached "Invalid" from before the identifier was
      // known can now use the fast lookup path — re-run it to catch up.
      onAuthChange();
    }).catch(() => {
      persistedIdentifierRef.current = previous;
    });
  }, [onConfigureBuiltin, element.rid, onAuthChange]);

  const resolveDependencyValue = useCallback((configField: string): any => {
    if (configField === "mcp_url") return String(element.config?.mcp_url || "");
    return authFields[configField];
  }, [element.config?.mcp_url, authFields]);

  const checkAuth = useCallback(async (): Promise<DiscoveryResponse | null> => {
    if (!userId || !element.config?.mcp_url) return null;
    setSignInStatus("checking");
    try {
      const data: DiscoveryResponse = await executeAction(
        "auth.discovery",
        { mcp_url: String(element.config.mcp_url), user_id: userId },
        userId,
      );
      const nextAuthFields = {
        ...data.form_updates,
        ...(data.server_identifier ? { server_identifier: data.server_identifier } : {}),
        ...(data.scheme_type ? { scheme_type: data.scheme_type } : {}),
      };
      if (Object.keys(nextAuthFields).length > 0) {
        setAuthFields((prev) => ({ ...prev, ...nextAuthFields }));
      }
      if (data.status === "authenticated") {
        setSignInStatus("authenticated");
        setSignInMessage(data.message || "Authenticated");
        setSignOutActions(data.actions || []);
        persistAuthIdentifier(data.server_identifier, data.scheme_type);
      } else if (data.status === "challenge" && data.challenge) {
        setSignInStatus("challenge");
        setChallenge(data.challenge);
        setSignInMessage(data.message || "Sign in required");
      } else if (data.status === "not_configured") {
        setSignInStatus("not_configured");
        setSignInMessage(data.message || "Authentication not configured");
      } else {
        setSignInStatus("error");
        setSignInMessage(data.message || "Could not determine auth status");
      }
      return data;
    } catch {
      setSignInStatus("error");
      setSignInMessage("Failed to check authentication status");
      return null;
    }
  }, [userId, element.config?.mcp_url, persistAuthIdentifier]);

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
        onAuthChange();
      } else {
        setSignInStatus("error");
        setSignInMessage(event.data.error || "Authentication failed");
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [checkAuth, onAuthChange]);

  const openAuthPopup = (url: string) => {
    popupAuthUrlRef.current = url;
    popupRef.current = window.open(url, "oauth_signin", "width=600,height=700,scrollbars=yes");
  };

  // Opens the popup immediately, either from an already-known challenge or by
  // running discovery right now, instead of requiring a second click once
  // status has caught up to 'challenge'.
  const handleSignIn = async () => {
    if (signInStatus === "authenticated" || signInStatus === "checking") return;

    if (signInStatus === "challenge" && challenge?.authorization_url) {
      openAuthPopup(challenge.authorization_url);
      return;
    }

    checkedRef.current = true;
    const data = await checkAuth();
    if (data?.status === "challenge" && data.challenge?.authorization_url) {
      openAuthPopup(data.challenge.authorization_url);
    }
  };

  const handleSignOut = async (action: SignOutAction) => {
    setSigningOut(true);
    try {
      const inputData: Record<string, any> = { user_id: userId };
      const dependencies = action.dependencies || { server_identifier: "server_identifier" };
      Object.entries(dependencies).forEach(([configField, actionField]) => {
        const val = resolveDependencyValue(configField);
        if (val !== undefined) {
          inputData[actionField] = val;
        }
      });

      await executeAction(action.uid, inputData, userId);
      checkedRef.current = false;
      checkAuth();
      onAuthChange();
    } catch {
      setSignInStatus("error");
      setSignInMessage("Sign out failed");
    } finally {
      setSigningOut(false);
    }
  };

  return {
    signInStatus,
    challenge,
    signInMessage,
    signOutActions,
    signingOut,
    handleSignIn,
    handleSignOut,
  };
}
