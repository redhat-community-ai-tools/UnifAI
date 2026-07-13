import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { motion } from 'framer-motion';
import { 
  Settings, 
  Trash2, 
  LoaderCircle,
  FileText,
  Database,
  Eye,
  Users,
  Check,
  AlertTriangle,
  ShieldCheck,
  LogIn,
  LogOut,
  ArrowLeft,
  KeyRound,
  Plus,
  X,
  CheckCircle,
  XCircle,
  Lock,
  Loader2,
} from 'lucide-react';
import SimpleTooltip from '@/components/shared/SimpleTooltip';
import { useShared } from '@/contexts/SharedContext';
import { useAgenticAI } from '@/contexts/AgenticAIContext';
import { useAuth } from "@/contexts/AuthContext";
import { useView } from "@/contexts/ViewContext";
import { useTeamEditLockPoll } from "@/hooks/use-team-edit-lock-poll";
import { ElementInstance, ElementType, ElementSchema } from '../../../types/workspace';
import { ElementValidationResult } from '../../../types/validation';
import { ElementData } from './ElementData';
import { ValidationResultModal } from './ValidationResultModal';
import { cn } from "@/lib/utils";
import axios from "../../../http/axiosAgentConfig";

type BuiltinCardType = 'sign_in' | 'access_token' | 'api_key' | 'none';

function getBuiltinCardType(element: ElementInstance): BuiltinCardType {
  if (!element.builtinStatus) return 'none';
  const cfg = element.config || {};
  if (cfg.auth_method === 'sign_in') return 'sign_in';
  if (cfg.auth_method === 'access_token') return 'access_token';
  if (element.category === 'llms') return 'api_key';
  return 'none';
}

interface ElementGridProps {
  elements: ElementInstance[];
  elementType: ElementType;
  isLoading: boolean;
  onEditElement: (element: ElementInstance) => void;
  onDeleteElement: (rid: string) => void;
  onConfigureBuiltin?: (rid: string, config: Record<string, any>) => Promise<any>;
  elementSchema?: ElementSchema | null;
}

const FIELD_PRIORITY: Record<string, number> = {
  mcp_url: 1, model_name: 1, base_url: 2,
  llm: 2, tools: 3, providers: 3, tool_names: 3,
  temperature: 4, max_tokens: 4, transport_type: 4,
  system_message: 5, retries: 6, verify_ssl: 6,
};

const HIDDEN_CARD_FIELDS = new Set([
  "type", "server_identifier", "scheme_type", "credential_token",
  "sign_in", "cwd", "env_vars",
]);

const BUILTIN_USER_FIELDS = new Set([
  "auth_method", "bearer_token", "api_key", "additional_headers",
]);

function sortFieldsByPriority(keys: string[]): string[] {
  return [...keys].sort((a, b) => {
    const pa = FIELD_PRIORITY[a] ?? 99;
    const pb = FIELD_PRIORITY[b] ?? 99;
    return pa - pb;
  });
}

function smartFormatValue(
  key: string,
  value: any,
  getResourceName: (ref: string) => string,
): string {
  if (value == null || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return String(value);

  if (typeof value === "string") {
    if (value.startsWith("$ref:")) {
      const name = getResourceName(value);
      return name || value.replace("$ref:", "").slice(0, 8) + "…";
    }
    if (value.length > 40) return value.slice(0, 37) + "…";
    return value;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return "None";
    const items = value.map((v) => {
      if (typeof v === "string") {
        if (v.startsWith("$ref:")) return getResourceName(v) || v.replace("$ref:", "").slice(0, 8);
        return v;
      }
      if (v?.$ref) return getResourceName(v) || "ref";
      if (v?.name) return v.name;
      return "…";
    });
    if (items.length <= 2) return items.join(", ");
    return `${items[0]}, ${items[1]} +${items.length - 2} more`;
  }

  if (typeof value === "object") {
    const keys = Object.keys(value);
    if (keys.length === 0) return "None";
    if (value.$ref) return getResourceName(value) || "ref";
    if (value.name) return value.name;
    const label = key.includes("header") ? "header" : "entry";
    return `${keys.length} ${label}${keys.length !== 1 ? "s" : ""}`;
  }

  return String(value);
}

export const ElementGrid: React.FC<ElementGridProps> = ({
  elements,
  elementType,
  isLoading,
  onEditElement,
  onDeleteElement,
  onConfigureBuiltin,
  elementSchema
}) => {
  const [selectedElement, setSelectedElement] = useState<ElementInstance | null>(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
  const [isValidationModalOpen, setIsValidationModalOpen] = useState(false);
  const [selectedValidationResult, setSelectedValidationResult] = useState<ElementValidationResult | null>(null);
  const [flippedCards, setFlippedCards] = useState<Set<string>>(new Set());
  const [builtinInputs, setBuiltinInputs] = useState<Record<string, Record<string, any>>>({});
  const [isSavingBuiltin, setIsSavingBuiltin] = useState<Record<string, boolean>>({});
  const [headerRows, setHeaderRows] = useState<Record<string, Array<{ key: string; value: string }>>>({});
  const [signInStatuses, setSignInStatuses] = useState<Record<string, 'checking' | 'authenticated' | 'unauthenticated'>>({});
  const [localConfigured, setLocalConfigured] = useState<Record<string, boolean>>({});
  const signInCheckedRef = useRef<Set<string>>(new Set());
  const { openShareForItem } = useShared();
  const { user } = useAuth();
  const { viewMode, selectedTeam } = useView();
  const isTeamWorkspace = viewMode === "team" && !!selectedTeam;
  const nonBuiltInElements = elements.filter(el => !el.builtinStatus);
  const resourceEditLocks = useTeamEditLockPoll(
    selectedTeam?.id,
    "resource",
    nonBuiltInElements.map((el) => el.rid),
    isTeamWorkspace,
  );
  const { 
    getResourceName, 
    getValidationResult, 
    getValidationStatus,
    validateResources 
  } = useAgenticAI();

  useEffect(() => {
    const realElements = elements.filter(el => !el.builtinStatus);
    if (realElements.length > 0) {
      const rids = realElements.map(el => el.rid);
      validateResources(rids);
    }
  }, [elements, validateResources]);

  useEffect(() => {
    const signInElements = elements.filter(el => getBuiltinCardType(el) === 'sign_in');
    if (signInElements.length === 0 || !user?.username) return;
    for (const el of signInElements) {
      if (signInCheckedRef.current.has(el.rid)) continue;
      signInCheckedRef.current.add(el.rid);
      setSignInStatuses(prev => ({ ...prev, [el.rid]: 'checking' }));
      axios.post('/actions/action.execute', {
        uid: 'auth.discovery',
        inputData: { mcp_url: String(el.config?.mcp_url || ''), user_id: user.username },
        userId: user.username,
      }).then(res => {
        const authenticated = res.data?.status === 'authenticated';
        setSignInStatuses(prev => ({ ...prev, [el.rid]: authenticated ? 'authenticated' : 'unauthenticated' }));
      }).catch(() => {
        setSignInStatuses(prev => ({ ...prev, [el.rid]: 'unauthenticated' }));
      });
    }
  }, [elements, user?.username]);

  const toggleCardFlip = (rid: string) => {
    setFlippedCards(prev => {
      const next = new Set(prev);
      if (next.has(rid)) next.delete(rid);
      else next.add(rid);
      return next;
    });
  };

  const setBuiltinField = (rid: string, field: string, value: any) => {
    setBuiltinInputs(prev => ({
      ...prev,
      [rid]: { ...(prev[rid] || {}), [field]: value },
    }));
  };

  const addHeaderRow = (rid: string) => {
    setHeaderRows(prev => ({
      ...prev,
      [rid]: [...(prev[rid] || []), { key: '', value: '' }],
    }));
  };

  const updateHeaderRow = (rid: string, idx: number, field: 'key' | 'value', val: string) => {
    setHeaderRows(prev => {
      const rows = [...(prev[rid] || [])];
      rows[idx] = { ...rows[idx], [field]: val };
      return { ...prev, [rid]: rows };
    });
  };

  const removeHeaderRow = (rid: string, idx: number) => {
    setHeaderRows(prev => {
      const rows = [...(prev[rid] || [])];
      rows.splice(idx, 1);
      return { ...prev, [rid]: rows };
    });
  };

  const handleBuiltinSave = async (rid: string, cardType: BuiltinCardType) => {
    if (!onConfigureBuiltin) return;
    const inputs = builtinInputs[rid] || {};
    const config: Record<string, any> = {};

    if (cardType === 'access_token') {
      if (inputs.bearer_token) config.bearer_token = inputs.bearer_token;
      const rows = headerRows[rid] || [];
      const headers: Record<string, string> = {};
      for (const r of rows) {
        if (r.key.trim()) headers[r.key.trim()] = r.value;
      }
      if (Object.keys(headers).length > 0) config.additional_headers = headers;
    } else if (cardType === 'api_key') {
      if (inputs.api_key) config.api_key = inputs.api_key;
    }

    if (Object.keys(config).length === 0) return;

    setIsSavingBuiltin(prev => ({ ...prev, [rid]: true }));
    try {
      await onConfigureBuiltin(rid, config);
      toggleCardFlip(rid);
      setLocalConfigured(prev => ({ ...prev, [rid]: true }));
      setBuiltinInputs(prev => { const next = { ...prev }; delete next[rid]; return next; });
      setHeaderRows(prev => { const next = { ...prev }; delete next[rid]; return next; });
    } finally {
      setIsSavingBuiltin(prev => ({ ...prev, [rid]: false }));
    }
  };

  const handleViewDetails = (element: ElementInstance) => {
    setSelectedElement(element);
    setIsDetailsModalOpen(true);
  };

  const handleShareElement = (element: ElementInstance) => {
    openShareForItem({
      itemKind: 'resource',
      itemId: element.rid,
      itemName: element.name || `${elementType.name} Instance`,
    });
  };

  const handleValidationClick = (rid: string) => {
    const result = getValidationResult(rid);
    if (result) {
      setSelectedValidationResult(result);
      setIsValidationModalOpen(true);
    }
  };

  // Render validation status icon
  const renderValidationStatus = (rid: string) => {
    const status = getValidationStatus(rid);

    if (status === 'loading') {
      return (
        <SimpleTooltip content={<p>Validating resource...</p>}>
          <div className="flex items-center justify-center w-8 h-8">
            <LoaderCircle className="h-4 w-4 animate-spin text-gray-400" />
          </div>
        </SimpleTooltip>
      );
    }

    if (status === 'valid') {
      return (
        <SimpleTooltip content={<p>Resource is valid - Click for details</p>}>
          <button 
            className="flex items-center justify-center w-8 h-8 rounded-md bg-green-500/10 hover:bg-green-500/20 transition-colors cursor-pointer"
            onClick={() => handleValidationClick(rid)}
          >
            <Check className="h-4 w-4 text-green-500" />
          </button>
        </SimpleTooltip>
      );
    }

    if (status === 'invalid') {
      return (
        <SimpleTooltip content={<p>Resource is invalid - Click for details</p>}>
          <button 
            className="flex items-center justify-center w-8 h-8 rounded-md bg-yellow-500/10 hover:bg-yellow-500/20 transition-colors cursor-pointer"
            onClick={() => handleValidationClick(rid)}
          >
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
          </button>
        </SimpleTooltip>
      );
    }

    return null;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoaderCircle className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (elements.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <Database className="h-12 w-12 mb-4 opacity-50" />
        <h3 className="text-lg font-medium mb-2">No {elementType.name} instances found</h3>
        <p className="text-sm text-center max-w-md">
          Create your first {elementType.name.toLowerCase()} instance by clicking the "Create New" button above.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {elements.map((element, index) => {
        const isBuiltIn = !!element.builtinStatus;
        const isFlipped = flippedCards.has(element.rid);
        const builtinCardType = getBuiltinCardType(element);
        const hasConfigurableBack = builtinCardType !== 'none';

        const lockHolder = isBuiltIn ? undefined : resourceEditLocks[element.rid];
        const lockUnknown = !isBuiltIn && lockHolder === "unknown";
        const lockedByOther =
          !isBuiltIn &&
          isTeamWorkspace &&
          !lockUnknown &&
          !!lockHolder &&
          !!user?.username &&
          lockHolder.userId !== user.username;
        const lockedByLabel = lockUnknown
          ? "unknown"
          : (lockHolder as any)?.displayName?.trim() || (lockHolder as any)?.userId || "another teammate";

        const allConfigKeys = element.config ? Object.keys(element.config) : [];
        const displayableKeys = sortFieldsByPriority(
          allConfigKeys.filter(k => !HIDDEN_CARD_FIELDS.has(k))
        );
        const builtInUserKeys = isBuiltIn
          ? allConfigKeys.filter(k => BUILTIN_USER_FIELDS.has(k))
          : [];

        return (
        <motion.div
          key={element.rid}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: index * 0.1 }}
          style={{ perspective: 1000 }}
        >
          <div
            className="relative h-full transition-transform duration-500"
            style={{
              transformStyle: "preserve-3d",
              transform: isFlipped ? "rotateY(180deg)" : "rotateY(0deg)",
            }}
          >
            {/* ---- FRONT FACE ---- */}
            <div
              className="w-full"
              style={{ backfaceVisibility: "hidden" }}
            >
              <Card className={cn(
                "bg-background-card shadow-card border-gray-800 h-full flex flex-col",
                isBuiltIn && "border-primary/20"
              )}>
                <CardHeader className="py-4 px-6 border-b border-gray-800">
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className={cn("h-5 w-5 flex-shrink-0", isBuiltIn ? "text-primary" : "text-primary")} />
                      <CardTitle className="text-lg font-heading truncate">
                        {element.name || `${elementType.name} Instance`}
                      </CardTitle>
                      {isBuiltIn && (
                        <Badge className="bg-primary/15 text-primary border-primary/30 text-[10px] px-1.5 py-0 font-medium flex-shrink-0 gap-1">
                          <ShieldCheck className="h-3 w-3" />
                          Built-in
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {!isBuiltIn && renderValidationStatus(element.rid)}
                      {!isBuiltIn && (
                        <>
                          <SimpleTooltip content={<p>Share this resource</p>}>
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              className="text-gray-400 hover:text-blue-400 hover:bg-blue-500/10"
                              onClick={() => handleShareElement(element)}
                            >
                              <Users className="h-4 w-4" />
                            </Button>
                          </SimpleTooltip>
                          <SimpleTooltip content={<p>Delete this resource</p>}>
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              className="text-gray-400 hover:text-red-400"
                              onClick={() => onDeleteElement(element.rid)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </SimpleTooltip>
                        </>
                      )}
                    </div>
                  </div>
                </CardHeader>
                
                <CardContent className="p-4 flex-grow">
                  <div className="space-y-2">
                    {!isBuiltIn && (
                      <div className="flex justify-between">
                        <span className="text-xs text-gray-500">ID:</span>
                        <span className="text-xs font-mono text-gray-300">
                          {element.rid.slice(0, 8)}...
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-500">Type:</span>
                      <Badge variant="outline" className="text-xs">
                        {elementType.type}
                      </Badge>
                    </div>
                    {!isBuiltIn && element.version && (
                      <div className="flex justify-between">
                        <span className="text-xs text-gray-500">Version:</span>
                        <span className="text-xs text-gray-300">v{element.version}</span>
                      </div>
                    )}
                    {!isBuiltIn && element.updated && (
                      <div className="flex justify-between">
                        <span className="text-xs text-gray-500">Last Updated:</span>
                        <span className="text-xs text-gray-300">
                          {new Date(element.updated).toLocaleDateString()}
                        </span>
                      </div>
                    )}
                    {element.contributed_by && (
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-gray-500">Contributed by:</span>
                        <span className="inline-flex items-center gap-1 text-[10px] text-primary bg-primary/10 px-1.5 py-0.5 rounded-full">
                          <Users className="h-2.5 w-2.5" />
                          {element.contributed_by}
                        </span>
                      </div>
                    )}

                    {/* Config preview — works for both built-in and personal */}
                    {element.config && displayableKeys.length > 0 && (
                      <div className="mt-3">
                        <span className="text-xs text-gray-500">
                          {isBuiltIn ? "Overview:" : "Configuration:"}
                        </span>
                        <div className="text-xs text-gray-300 mt-1 space-y-1">
                          {displayableKeys
                            .filter(k => !(isBuiltIn && BUILTIN_USER_FIELDS.has(k)))
                            .slice(0, 4)
                            .map((key) => {
                              const fieldSchema = elementSchema?.config_schema?.properties?.[key];
                              const rawValue = element.config[key];
                              const isSecret = fieldSchema?.hints?.secret?.hint_type === "secret";
                              const display = isSecret
                                ? "••••••••"
                                : smartFormatValue(key, rawValue, getResourceName);
                              return (
                                <div key={key} className="flex justify-between gap-2">
                                  <span className="text-gray-500 flex-shrink-0">{key}:</span>
                                  <span className="text-gray-300 truncate text-right" title={display}>
                                    {display}
                                  </span>
                                </div>
                              );
                          })}
                          {displayableKeys.filter(k => !(isBuiltIn && BUILTIN_USER_FIELDS.has(k))).length > 4 && (
                            <div className="text-gray-500 text-center">
                              +{displayableKeys.filter(k => !(isBuiltIn && BUILTIN_USER_FIELDS.has(k))).length - 4} more...
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Built-in user-configurable fields */}
                    {isBuiltIn && builtInUserKeys.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-800/50">
                        <span className="text-xs text-gray-500">Your configuration:</span>
                        <div className="text-xs text-gray-300 mt-1 space-y-1">
                          {builtInUserKeys.map(key => {
                            const val = element.config[key];
                            const display = smartFormatValue(key, val, getResourceName);
                            return (
                              <div key={key} className="flex justify-between items-center gap-2">
                                <span className="text-gray-500 flex-shrink-0">{key}:</span>
                                <span className="text-gray-300 truncate text-right">{display}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {isBuiltIn && displayableKeys.length === 0 && builtInUserKeys.length === 0 && (
                      <div className="mt-3 py-2 text-center">
                        <p className="text-xs text-gray-500">
                          Pre-configured &mdash; ready to use
                        </p>
                      </div>
                    )}
                  </div>
                </CardContent>

                <CardFooter className="px-6 py-3 border-t border-gray-800 bg-background-dark">
                  {isBuiltIn ? (
                    <div className="flex gap-2 w-full">
                      {builtinCardType === 'sign_in' && (() => {
                        const authStatus = signInStatuses[element.rid];
                        const isAuth = authStatus === 'authenticated';
                        return (
                          <Button
                            variant="outline"
                            size="sm"
                            className={`flex-1 flex items-center justify-center gap-2 ${
                              isAuth
                                ? 'border-red-400/40 text-red-400 hover:bg-red-400/10'
                                : 'border-primary/40 text-primary hover:bg-primary/10'
                            }`}
                            onClick={() => toggleCardFlip(element.rid)}
                            disabled={authStatus === 'checking'}
                          >
                            {authStatus === 'checking' ? (
                              <><Loader2 className="h-3 w-3 animate-spin" /> Checking...</>
                            ) : isAuth ? (
                              <><LogOut className="h-3 w-3" /> Sign Out</>
                            ) : (
                              <><LogIn className="h-3 w-3" /> Sign In</>
                            )}
                          </Button>
                        );
                      })()}
                      {(builtinCardType === 'access_token' || builtinCardType === 'api_key') && (() => {
                        const configured = localConfigured[element.rid] ?? element.userConfigured;
                        return (
                          <Button
                            variant="outline"
                            size="sm"
                            className="flex-1 flex items-center justify-center gap-2 border-primary/40 text-primary hover:bg-primary/10"
                            onClick={() => toggleCardFlip(element.rid)}
                          >
                            {configured ? (
                              <><KeyRound className="h-3 w-3" /> Edit Credentials</>
                            ) : (
                              <><LogIn className="h-3 w-3" /> Sign In</>
                            )}
                          </Button>
                        );
                      })()}
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="flex-1 flex items-center justify-center gap-2"
                        onClick={() => handleViewDetails(element)}
                      >
                        <Eye className="h-3 w-3" />
                        Details
                      </Button>
                    </div>
                  ) : (
                    <div className="flex gap-2 w-full">
                      <SimpleTooltip
                        collisionPadding={12}
                        content={
                          lockUnknown ? (
                            <p>Could not verify edit lock — try again shortly</p>
                          ) : lockedByOther ? (
                            <p>Currently being edited by {lockedByLabel}</p>
                          ) : (
                            <p>Configure this element</p>
                          )
                        }
                      >
                        <span
                          className={cn(
                            "flex flex-1",
                            (lockedByOther || lockUnknown) && "cursor-not-allowed",
                          )}
                        >
                          <Button
                            variant="outline"
                            size="sm"
                            className={cn(
                              "flex flex-1 items-center justify-center gap-2",
                              (lockedByOther || lockUnknown) && "pointer-events-none",
                            )}
                            onClick={() => onEditElement(element)}
                            disabled={lockedByOther || lockUnknown}
                          >
                            <Settings className="h-3 w-3" />
                            Configure
                          </Button>
                        </span>
                      </SimpleTooltip>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="flex-1 flex items-center justify-center gap-2"
                        onClick={() => handleViewDetails(element)}
                      >
                        <Eye className="h-3 w-3" />
                        Details
                      </Button>
                    </div>
                  )}
                </CardFooter>
              </Card>
            </div>

            {/* ---- BACK FACE — type-aware built-in configure ---- */}
            {isBuiltIn && hasConfigurableBack && (
              <div
                className="absolute inset-0 w-full"
                style={{
                  backfaceVisibility: "hidden",
                  transform: "rotateY(180deg)",
                }}
              >
                {builtinCardType === 'sign_in' ? (
                  <BuiltinSignInBack
                    element={element}
                    onBack={() => toggleCardFlip(element.rid)}
                    onStatusChange={(rid, authenticated) => {
                      setSignInStatuses(prev => ({ ...prev, [rid]: authenticated ? 'authenticated' : 'unauthenticated' }));
                      signInCheckedRef.current.delete(rid);
                    }}
                  />
                ) : builtinCardType === 'access_token' ? (
                  <Card className="bg-background-card shadow-card border-primary/30 h-full flex flex-col">
                    <CardHeader className="py-3 px-6 border-b border-gray-800">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleCardFlip(element.rid)}
                          className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
                        >
                          <ArrowLeft className="h-4 w-4" />
                        </button>
                        <KeyRound className="h-4 w-4 text-primary" />
                        <CardTitle className="text-base font-heading">
                          Configure {element.name}
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent className="p-4 flex-grow overflow-y-auto">
                      <div className="space-y-3">
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-gray-300">Access Token</label>
                          <Input
                            type="password"
                            placeholder="Bearer token or API key..."
                            className="bg-background-dark border-gray-700 text-sm h-8"
                            value={builtinInputs[element.rid]?.bearer_token ?? ""}
                            onChange={(e) => setBuiltinField(element.rid, 'bearer_token', e.target.value)}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between">
                            <label className="text-xs font-medium text-gray-300">Additional Headers</label>
                            <button
                              type="button"
                              onClick={() => addHeaderRow(element.rid)}
                              className="text-xs text-primary hover:text-primary/80 flex items-center gap-0.5"
                            >
                              <Plus className="h-3 w-3" /> Add
                            </button>
                          </div>
                          {(headerRows[element.rid] || []).length === 0 && (
                            <p className="text-[11px] text-gray-500">No custom headers</p>
                          )}
                          {(headerRows[element.rid] || []).map((row, idx) => (
                            <div key={idx} className="flex items-center gap-1.5">
                              <Input
                                placeholder="Header"
                                className="bg-background-dark border-gray-700 text-xs h-7 flex-1"
                                value={row.key}
                                onChange={(e) => updateHeaderRow(element.rid, idx, 'key', e.target.value)}
                              />
                              <Input
                                placeholder="Value"
                                className="bg-background-dark border-gray-700 text-xs h-7 flex-1"
                                value={row.value}
                                onChange={(e) => updateHeaderRow(element.rid, idx, 'value', e.target.value)}
                              />
                              <button
                                type="button"
                                onClick={() => removeHeaderRow(element.rid, idx)}
                                className="text-gray-500 hover:text-red-400 p-0.5"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                    <CardFooter className="px-6 py-3 border-t border-gray-800 bg-background-dark">
                      <div className="flex gap-2 w-full">
                        <Button variant="outline" size="sm" className="flex-1" onClick={() => toggleCardFlip(element.rid)}>
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          className="flex-1 bg-primary hover:bg-primary/80"
                          disabled={!builtinInputs[element.rid]?.bearer_token?.trim() || isSavingBuiltin[element.rid]}
                          onClick={() => handleBuiltinSave(element.rid, 'access_token')}
                        >
                          {isSavingBuiltin[element.rid] ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Check className="h-3 w-3 mr-1" />}
                          Save
                        </Button>
                      </div>
                    </CardFooter>
                  </Card>
                ) : builtinCardType === 'api_key' ? (
                  <Card className="bg-background-card shadow-card border-primary/30 h-full flex flex-col">
                    <CardHeader className="py-3 px-6 border-b border-gray-800">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleCardFlip(element.rid)}
                          className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
                        >
                          <ArrowLeft className="h-4 w-4" />
                        </button>
                        <KeyRound className="h-4 w-4 text-primary" />
                        <CardTitle className="text-base font-heading">
                          Configure {element.name}
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent className="p-6 flex-grow flex flex-col justify-center">
                      <div className="space-y-4">
                        <p className="text-sm text-gray-400 text-center">
                          Provide your API key to use <span className="text-white font-medium">{element.name}</span>
                        </p>
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium text-gray-300">API Key</label>
                          <Input
                            type="password"
                            placeholder="Enter your API key..."
                            className="bg-background-dark border-gray-700 text-sm"
                            value={builtinInputs[element.rid]?.api_key ?? ""}
                            onChange={(e) => setBuiltinField(element.rid, 'api_key', e.target.value)}
                          />
                        </div>
                      </div>
                    </CardContent>
                    <CardFooter className="px-6 py-3 border-t border-gray-800 bg-background-dark">
                      <div className="flex gap-2 w-full">
                        <Button variant="outline" size="sm" className="flex-1" onClick={() => toggleCardFlip(element.rid)}>
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          className="flex-1 bg-primary hover:bg-primary/80"
                          disabled={!builtinInputs[element.rid]?.api_key?.trim() || isSavingBuiltin[element.rid]}
                          onClick={() => handleBuiltinSave(element.rid, 'api_key')}
                        >
                          {isSavingBuiltin[element.rid] ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Check className="h-3 w-3 mr-1" />}
                          Save
                        </Button>
                      </div>
                    </CardFooter>
                  </Card>
                ) : null}
              </div>
            )}
          </div>
        </motion.div>
        );
      })}
      
      {/* Element Details Modal */}
      <ElementData
        element={selectedElement}
        elementType={elementType}
        isOpen={isDetailsModalOpen}
        onOpenChange={setIsDetailsModalOpen}
        elementSchema={elementSchema}
      />

      {/* Validation Result Modal */}
      <ValidationResultModal
        validationResult={selectedValidationResult}
        isOpen={isValidationModalOpen}
        onOpenChange={setIsValidationModalOpen}
      />
    </div>
  );
};


// ─────────────────────────────────────────────────────────────────────────────
//  BuiltinSignInBack — OAuth sign-in card back for auth_method=sign_in MCPs
// ─────────────────────────────────────────────────────────────────────────────

type SignInStatus = 'idle' | 'checking' | 'authenticated' | 'challenge' | 'not_configured' | 'error';

interface ChallengeData {
  challenge_type: string;
  authorization_url?: string;
  flow_id?: string;
  scopes?: string[];
  server_identifier?: string;
}

function BuiltinSignInBack({
  element,
  onBack,
  onStatusChange,
}: {
  element: ElementInstance;
  onBack: () => void;
  onStatusChange?: (rid: string, authenticated: boolean) => void;
}) {
  const { user } = useAuth();
  const userId = user?.username || "";
  const [status, setStatus] = useState<SignInStatus>('idle');
  const [challenge, setChallenge] = useState<ChallengeData | null>(null);
  const [actions, setActions] = useState<Array<{ uid: string; label: string; style?: string }>>([]);
  const [message, setMessage] = useState('');
  const [signingOut, setSigningOut] = useState(false);
  const popupRef = useRef<Window | null>(null);
  const checkedRef = useRef(false);

  const checkAuth = useCallback(async () => {
    if (!userId || !element.config?.mcp_url) return;
    setStatus('checking');
    try {
      const res = await axios.post('/actions/action.execute', {
        uid: 'auth.discovery',
        inputData: { mcp_url: String(element.config.mcp_url), user_id: userId },
        userId,
      });
      const data = res.data;
      if (data.status === 'authenticated') {
        setStatus('authenticated');
        setMessage(data.message || 'Authenticated');
        setActions(data.actions || []);
        onStatusChange?.(element.rid, true);
      } else if (data.status === 'challenge' && data.challenge) {
        setStatus('challenge');
        setChallenge(data.challenge);
        setMessage(data.message || 'Sign in required');
        onStatusChange?.(element.rid, false);
      } else if (data.status === 'not_configured') {
        setStatus('not_configured');
        setMessage(data.message || 'Authentication not configured for this server');
        onStatusChange?.(element.rid, false);
      } else {
        setStatus('error');
        setMessage(data.message || 'Could not determine auth status');
      }
    } catch {
      setStatus('error');
      setMessage('Failed to check authentication status');
    }
  }, [userId, element.config?.mcp_url, element.rid, onStatusChange]);

  useEffect(() => {
    if (!checkedRef.current) {
      checkedRef.current = true;
      checkAuth();
    }
  }, [checkAuth]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type !== 'credentials_callback') return;
      if (popupRef.current) {
        popupRef.current.close();
        popupRef.current = null;
      }
      if (event.data.success) {
        checkedRef.current = false;
        checkAuth();
      } else {
        setStatus('error');
        setMessage(event.data.error || 'Authentication failed');
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [checkAuth]);

  const handleSignIn = () => {
    if (!challenge?.authorization_url) return;
    popupRef.current = window.open(
      challenge.authorization_url,
      'oauth_signin',
      'width=600,height=700,scrollbars=yes',
    );
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
      setStatus('error');
      setMessage('Sign out failed');
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <Card className="bg-background-card shadow-card border-primary/30 h-full flex flex-col">
      <CardHeader className="py-3 px-6 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <button
            onClick={onBack}
            className="p-1 rounded-md text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          {status === 'authenticated' ? (
            <CheckCircle className="h-4 w-4 text-green-400" />
          ) : (
            <LogIn className="h-4 w-4 text-primary" />
          )}
          <CardTitle className="text-base font-heading">
            {status === 'authenticated' ? 'Signed In' : 'Sign In'} — {element.name}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-6 flex-grow flex flex-col items-center justify-center">
        {status === 'checking' && (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
            <span className="text-sm text-blue-400">Checking authentication...</span>
          </div>
        )}
        {status === 'authenticated' && (
          <div className="flex flex-col items-center gap-3">
            <CheckCircle className="h-8 w-8 text-green-400" />
            <span className="text-sm text-green-400 font-medium">{message}</span>
            <p className="text-xs text-gray-500 text-center">
              You&rsquo;re signed in and ready to use this resource.
            </p>
            {actions.filter(a => a.style === 'danger').map(action => (
              <Button
                key={action.uid}
                variant="outline"
                size="sm"
                className="border-red-400/40 text-red-400 hover:bg-red-400/10"
                disabled={signingOut}
                onClick={() => handleSignOut(action.uid)}
              >
                {signingOut ? (
                  <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> Signing Out...</>
                ) : (
                  <><LogOut className="h-3.5 w-3.5 mr-1.5" /> {action.label}</>
                )}
              </Button>
            ))}
          </div>
        )}
        {status === 'challenge' && (
          <div className="flex flex-col items-center gap-4">
            <Lock className="h-8 w-8 text-yellow-400" />
            <span className="text-sm text-yellow-400">{message}</span>
            {challenge?.authorization_url && (
              <Button
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white"
                onClick={handleSignIn}
              >
                <LogIn className="h-3.5 w-3.5 mr-1.5" />
                Sign In
              </Button>
            )}
          </div>
        )}
        {status === 'not_configured' && (
          <div className="flex flex-col items-center gap-3">
            <XCircle className="h-8 w-8 text-orange-400" />
            <span className="text-sm text-orange-400 text-center">{message}</span>
          </div>
        )}
        {status === 'error' && (
          <div className="flex flex-col items-center gap-3">
            <XCircle className="h-8 w-8 text-red-400" />
            <span className="text-sm text-red-400 text-center">{message}</span>
            <Button variant="outline" size="sm" onClick={() => { checkedRef.current = false; checkAuth(); }}>
              Retry
            </Button>
          </div>
        )}
        {status === 'idle' && (
          <div className="flex flex-col items-center gap-3">
            <Lock className="h-8 w-8 text-gray-500" />
            <span className="text-sm text-gray-400">Waiting for auth check...</span>
          </div>
        )}
      </CardContent>
      <CardFooter className="px-6 py-3 border-t border-gray-800 bg-background-dark">
        <Button variant="outline" size="sm" className="w-full" onClick={onBack}>
          Back
        </Button>
      </CardFooter>
    </Card>
  );
}
