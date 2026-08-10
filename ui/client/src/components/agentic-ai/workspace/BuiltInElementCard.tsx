import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  FileText,
  ShieldCheck,
  LogIn,
  LogOut,
  Settings,
  Loader2,
} from 'lucide-react';
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";
import { useAgenticAI } from "@/contexts/AgenticAIContext";
import { useBuiltinSignIn, SignOutAction } from "@/hooks/use-builtin-sign-in";
import { ElementInstance, ElementType, ElementSchema } from '../../../types/workspace';
import { ValidationStatus } from '@/contexts/AgenticAIContext';
import { BuiltinConfigureModal } from './BuiltinConfigureModal';
import { CardFieldList } from './CardFieldList';
import { ValidationStatusBadge } from './validation/ValidationStatusBadge';
import { SignInStatusIndicator } from './auth/SignInStatusIndicator';
import { getCardFields, isUserConfigurable } from "@/lib/cardFields";
import { isFieldConditionallyVisible } from "@/lib/schemaRefs";
import { cn } from "@/lib/utils";

interface BuiltInElementCardProps {
  element: ElementInstance;
  elementType: ElementType;
  elementSchema?: ElementSchema | null;
  onConfigureBuiltin?: (
    rid: string,
    config: Record<string, any>,
    options?: { silent?: boolean },
  ) => Promise<any>;
  index: number;
  primaryLight: string;
  /** Live validity status for this built-in resource. Omit to hide the badge —
   * most built-ins ship without live credentials, so only opted-in types pass this. */
  validationStatus?: ValidationStatus;
  onValidationClick?: () => void;
}

/**
 * Whether this built-in instance currently needs an interactive sign-in —
 * driven entirely by the schema's `sign_in` field (if any) rather than a
 * hardcoded auth_method value, so it works for both MCP's single static
 * "sign_in" mode and A2A's open-ended registry server identifiers (e.g.
 * `visible_when: {auth_method: {not_in: ["none", "access_token"]}}`).
 * `auth_method` itself is admin-controlled (see `A2AAgentNodeConfig`), so
 * reading it straight off `element.config` (the shared base config) is
 * correct — it's the same for every caller of this built-in.
 */
function hasSignInAuth(element: ElementInstance, elementSchema?: ElementSchema | null): boolean {
  const signInField = elementSchema?.config_schema?.properties?.sign_in as any;
  if (!signInField?.hints?.auth) return false;
  return isFieldConditionallyVisible(signInField, element.config || {});
}

/**
 * Whether the "Configure" modal has anything worth showing. Uses the same
 * `isUserConfigurable` predicate as `BuiltinConfigureModal`'s field list
 * (hidden/read-only/auth-trigger fields excluded) so this button's
 * visibility never drifts from what the modal actually renders. Fields
 * gated behind a `ConditionalHint` that doesn't currently match (e.g.
 * `bearer_token` when `auth_method` is "none" or an SSO server) are
 * excluded too, so the button doesn't appear when there's genuinely
 * nothing to configure.
 */
function hasConfigurableFields(element: ElementInstance, elementSchema?: ElementSchema | null): boolean {
  if (!elementSchema?.config_schema?.properties) return false;
  return Object.values(elementSchema.config_schema.properties).some((field: any) =>
    isUserConfigurable(field) &&
    isFieldConditionallyVisible(field, element.config || {})
  );
}

export const BuiltInElementCard: React.FC<BuiltInElementCardProps> = ({
  element,
  elementType,
  elementSchema,
  onConfigureBuiltin,
  index,
  primaryLight,
  validationStatus,
  onValidationClick,
}) => {
  // Sign-in/auth is an OAuth-style credential lookup, keyed per human member
  // even in team view — `credentialUserId` is the canonical source for that
  // (see `useWorkspaceIdentity`), while the team-scoped `userId` there is
  // reserved for identity-scoped resource ownership.
  const { credentialUserId: userId } = useWorkspaceIdentity();
  const { revalidateResourceAndAncestors, resolveRefsInConfig } = useAgenticAI();

  const isSignIn = hasSignInAuth(element, elementSchema);
  const hasConfigFields = hasConfigurableFields(element, elementSchema);
  const cardFields = useMemo(
    () => getCardFields(elementSchema, resolveRefsInConfig(element.config), 'builtin'),
    [elementSchema, element.config, resolveRefsInConfig],
  );

  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);

  const {
    signInStatus,
    signInMessage,
    signOutActions,
    signingOut,
    handleSignIn,
    handleSignOut,
  } = useBuiltinSignIn({
    element,
    elementSchema,
    userId,
    isSignIn,
    onConfigureBuiltin,
    onAuthChange: () => revalidateResourceAndAncestors(element.rid),
  });

  const handleConfigureSave = async (config: Record<string, any>) => {
    if (onConfigureBuiltin) {
      await onConfigureBuiltin(element.rid, config);
    }
  };

  const signOutAction: SignOutAction | undefined = signOutActions.find(a => a.style === 'danger');
  const configureBlocked = isSignIn && signInStatus !== 'authenticated';
  const isCardClickable = hasConfigFields && !configureBlocked;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.3, delay: Math.min(index, 10) * 0.1 } }}
      whileHover={{ y: -4, scale: 1.02, transition: { duration: 0.15, delay: 0 } }}
      whileTap={{ scale: 0.98, transition: { duration: 0.1, delay: 0 } }}
      className="h-full"
    >
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
            {validationStatus && (
              <div className="flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                <ValidationStatusBadge status={validationStatus} onClick={onValidationClick} />
              </div>
            )}
          </div>
        </CardHeader>

        <CardContent className="p-4 flex-grow flex flex-col items-center justify-center gap-2">
          {isSignIn && (
            <div className="flex flex-col items-center gap-1 py-2">
              <SignInStatusIndicator status={signInStatus} message={signInMessage} />
            </div>
          )}
          {cardFields.length > 0 ? (
            <CardFieldList fields={cardFields} />
          ) : !isSignIn ? (
            <div className="py-2 text-center">
              <p className="text-sm text-gray-500">
                Pre-configured &mdash; ready to use
              </p>
            </div>
          ) : null}
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
                className="flex-1 flex items-center justify-center gap-1.5 h-9 text-sm border-primary/30 text-primary hover:bg-primary/10 hover:border-primary/50 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => setIsConfigModalOpen(true)}
                disabled={isSignIn && signInStatus !== 'authenticated'}
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
    </motion.div>
  );
};
