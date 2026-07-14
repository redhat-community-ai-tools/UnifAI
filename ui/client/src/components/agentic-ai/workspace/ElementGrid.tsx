import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { BuiltInElementCard } from './BuiltInElementCard';
import { cn } from "@/lib/utils";

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
  const { openShareForItem } = useShared();
  const { user } = useAuth();
  const { viewMode, selectedTeam } = useView();
  const isTeamWorkspace = viewMode === "team" && !!selectedTeam;
  const nonBuiltInElements = elements.filter(el => el.ownership !== 'builtin');
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
    const realElements = elements.filter(el => el.ownership !== 'builtin');
    if (realElements.length > 0) {
      const rids = realElements.map(el => el.rid);
      validateResources(rids);
    }
  }, [elements, validateResources]);

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
        const isBuiltIn = element.ownership === 'builtin';

        if (isBuiltIn) {
          return (
            <motion.div
              key={element.rid}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.1 }}
            >
              <BuiltInElementCard
                element={element}
                elementType={elementType}
                elementSchema={elementSchema}
                onConfigureBuiltin={onConfigureBuiltin}
                index={index}
              />
            </motion.div>
          );
        }

        const lockHolder = resourceEditLocks[element.rid];
        const lockUnknown = lockHolder === "unknown";
        const lockedByOther =
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

        return (
        <motion.div
          key={element.rid}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: index * 0.1 }}
        >
              <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col">
                <CardHeader className="py-4 px-6 border-b border-gray-800">
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="h-5 w-5 flex-shrink-0 text-primary" />
                      <CardTitle className="text-lg font-heading truncate">
                        {element.name || `${elementType.name} Instance`}
                      </CardTitle>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {renderValidationStatus(element.rid)}
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
                    </div>
                  </div>
                </CardHeader>
                
                <CardContent className="p-4 flex-grow">
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-500">ID:</span>
                      <span className="text-xs font-mono text-gray-300">
                        {element.rid.slice(0, 8)}...
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-500">Type:</span>
                      <Badge variant="outline" className="text-xs">
                        {elementType.type}
                      </Badge>
                    </div>
                    {element.version && (
                      <div className="flex justify-between">
                        <span className="text-xs text-gray-500">Version:</span>
                        <span className="text-xs text-gray-300">v{element.version}</span>
                      </div>
                    )}
                    {element.updated && (
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

                    {element.config && displayableKeys.length > 0 && (
                      <div className="mt-3">
                        <span className="text-xs text-gray-500">Configuration:</span>
                        <div className="text-xs text-gray-300 mt-1 space-y-1">
                          {displayableKeys
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
                          {displayableKeys.length > 4 && (
                            <div className="text-gray-500 text-center">
                              +{displayableKeys.length - 4} more...
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>

                <CardFooter className="px-6 py-3 border-t border-gray-800 bg-background-dark">
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
                </CardFooter>
              </Card>
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
