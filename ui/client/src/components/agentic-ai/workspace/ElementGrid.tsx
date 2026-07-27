import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { motion } from 'framer-motion';
import { 
  Settings, 
  Trash2, 
  LoaderCircle,
  FileText,
  Database,
  Eye,
  Users,
  Clock,
} from 'lucide-react';
import SimpleTooltip from '@/components/shared/SimpleTooltip';
import { useShared } from '@/contexts/SharedContext';
import { useAgenticAI } from '@/contexts/AgenticAIContext';
import { useAuth } from "@/contexts/AuthContext";
import { useView } from "@/contexts/ViewContext";
import { useTheme } from "@/contexts/ThemeContext";
import { useTeamEditLockPoll } from "@/hooks/use-team-edit-lock-poll";
import { ElementInstance, ElementType, ElementSchema } from '../../../types/workspace';
import { ElementValidationResult } from '../../../types/validation';
import { ElementData } from './ElementData';
import { ValidationResultModal } from './ValidationResultModal';
import { BuiltInElementCard } from './BuiltInElementCard';
import { CardFieldList } from './CardFieldList';
import { ValidationStatusBadge } from './ValidationStatusBadge';
import { deriveThemeColors } from '@/lib/colorUtils';
import { getCardFields } from '@/lib/cardFields';
import { cn } from "@/lib/utils";

/** Element types whose built-in instances are still worth live-validating —
 * e.g. an MCP server's reachability is meaningful even on a built-in card,
 * unlike most other built-ins which ship without live credentials. */
const BUILTIN_VALIDATED_TYPES = new Set(['mcp_server']);

interface ElementGridProps {
  elements: ElementInstance[];
  elementType: ElementType;
  isLoading: boolean;
  onEditElement: (element: ElementInstance) => void;
  onDeleteElement: (rid: string) => void;
  onConfigureBuiltin?: (
    rid: string,
    config: Record<string, any>,
    options?: { silent?: boolean },
  ) => Promise<any>;
  elementSchema?: ElementSchema | null;
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
  const { primaryHex } = useTheme();
  // `primaryLight` is a lightened tint of the site's selected accent color —
  // using the raw `primary` color for small icon glyphs/text can be nearly
  // unreadable on the dark background for darker accent choices (e.g. red).
  const { primaryLight } = useMemo(() => deriveThemeColors(primaryHex), [primaryHex]);
  const isTeamWorkspace = viewMode === "team" && !!selectedTeam;
  const isBuiltinValidatedType = BUILTIN_VALIDATED_TYPES.has(elementType.type);
  // Memoized on `elements` so this array is only recreated when the element
  // list itself changes — not on every re-render (e.g. from lock polling or
  // modal state) — otherwise the validation effect below would re-fire and
  // re-trigger network calls on every unrelated render.
  const nonBuiltInElements = useMemo(
    () => elements.filter(el => el.ownership !== 'builtin'),
    [elements],
  );
  // Elements whose live validity should be probed and surfaced on their card.
  // Built-ins are excluded by default: many ship without live credentials/
  // connectivity configured in a given environment, so probing them surfaces
  // "invalid" for resources that are actually fine, and that failure cascades
  // to anything depending on them. Built-in MCP servers are the exception —
  // their reachability is meaningful signal even without user configuration.
  const elementsNeedingValidation = useMemo(
    () => isBuiltinValidatedType ? elements : nonBuiltInElements,
    [elements, nonBuiltInElements, isBuiltinValidatedType],
  );
  const resourceEditLocks = useTeamEditLockPoll(
    selectedTeam?.id,
    "resource",
    nonBuiltInElements.map((el) => el.rid),
    isTeamWorkspace,
  );
  const { 
    getValidationResult, 
    getValidationStatus,
    validateResources,
    resolveRefsInConfig,
  } = useAgenticAI();

  // Stable string key of the rid set — used as the effect dependency instead
  // of the `elementsNeedingValidation` array so a re-render that produces an
  // equivalent-but-new array (or object) doesn't re-trigger validation calls.
  const validatedRidsKey = useMemo(
    () => elementsNeedingValidation.map(el => el.rid).join(','),
    [elementsNeedingValidation],
  );

  useEffect(() => {
    if (validatedRidsKey) {
      validateResources(validatedRidsKey.split(','));
    }
  }, [validatedRidsKey, validateResources]);

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
  const renderValidationStatus = (rid: string) => (
    <ValidationStatusBadge status={getValidationStatus(rid)} onClick={() => handleValidationClick(rid)} />
  );

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
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {elements.map((element, index) => {
        const isBuiltIn = element.ownership === 'builtin';

        if (isBuiltIn) {
          return (
            <motion.div
              key={element.rid}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0, transition: { duration: 0.3, delay: index * 0.1 } }}
              whileHover={{ y: -4, scale: 1.02, transition: { duration: 0.15, delay: 0 } }}
              whileTap={{ scale: 0.98, transition: { duration: 0.1, delay: 0 } }}
              className="h-full"
            >
              <BuiltInElementCard
                element={element}
                elementType={elementType}
                elementSchema={elementSchema}
                onConfigureBuiltin={onConfigureBuiltin}
                index={index}
                validationStatus={isBuiltinValidatedType ? getValidationStatus(element.rid) : undefined}
                onValidationClick={() => handleValidationClick(element.rid)}
              />
            </motion.div>
          );
        }

        const cardFields = getCardFields(elementSchema, resolveRefsInConfig(element.config), 'custom');
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

        return (
        <motion.div
          key={element.rid}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.3, delay: index * 0.1 } }}
          whileHover={{ y: -8, scale: 1.03, transition: { duration: 0.15, delay: 0 } }}
          whileTap={{ scale: 0.97, transition: { duration: 0.1, delay: 0 } }}
          className="h-full"
        >
              <Card
                className="group relative bg-background-card border border-white/10 h-full flex flex-col cursor-pointer transition-all duration-300 hover:border-primary/50 hover:shadow-xl hover:shadow-primary/10"
                onClick={() => handleViewDetails(element)}
              >
                <CardHeader className="py-3.5 px-4 border-b border-white/5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 transition-colors duration-300 group-hover:bg-primary/20">
                        <FileText className="h-4 w-4" style={{ color: primaryLight }} />
                      </div>
                      <CardTitle className="text-lg font-heading truncate leading-tight min-w-0" title={element.name || undefined}>
                        {element.name || `${elementType.name} Instance`}
                      </CardTitle>
                    </div>
                    <div className="flex items-center gap-0.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                      {renderValidationStatus(element.rid)}
                      <SimpleTooltip content={<p>Share this resource</p>}>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-8 w-8 p-0 text-gray-400 hover:text-[var(--share-icon-accent)] hover:bg-primary/10"
                          style={{ '--share-icon-accent': primaryLight } as React.CSSProperties}
                          onClick={() => handleShareElement(element)}
                        >
                          <Users className="h-4 w-4" />
                        </Button>
                      </SimpleTooltip>
                      <SimpleTooltip content={<p>Delete this resource</p>}>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-8 w-8 p-0 text-gray-400 hover:text-red-400"
                          onClick={() => onDeleteElement(element.rid)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </SimpleTooltip>
                    </div>
                  </div>
                </CardHeader>
                
                <CardContent className="p-4 flex-grow flex flex-col justify-center gap-2">
                  {(element.version || element.updated) && (
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <Clock className="h-3 w-3 flex-shrink-0" />
                      <span className="truncate">
                        {element.version && `v${element.version}`}
                        {element.version && element.updated && " · "}
                        {element.updated && new Date(element.updated).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                  {element.contributed_by && (
                    <span className="inline-flex items-center gap-1 text-xs text-primary bg-primary/10 px-2 py-0.5 rounded-full w-fit">
                      <Users className="h-3 w-3" />
                      {element.contributed_by}
                    </span>
                  )}
                  {cardFields.length > 0 && <CardFieldList fields={cardFields} />}
                  {!element.version && !element.updated && !element.contributed_by && cardFields.length === 0 && (
                    <p className="text-xs text-gray-600 italic">Click to view full details</p>
                  )}
                </CardContent>

                <CardFooter className="px-4 py-3 border-t border-white/5" onClick={(e) => e.stopPropagation()}>
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
                              "flex flex-1 items-center justify-center gap-1.5 h-9 text-sm border-primary/30 text-primary hover:bg-primary/10 hover:border-primary/50",
                              (lockedByOther || lockUnknown) && "pointer-events-none",
                            )}
                            onClick={() => onEditElement(element)}
                            disabled={lockedByOther || lockUnknown}
                          >
                            <Settings className="h-3.5 w-3.5" />
                            Configure
                          </Button>
                        </span>
                      </SimpleTooltip>
                      <SimpleTooltip content={<p>View details</p>}>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="h-9 w-9 p-0 flex-shrink-0 flex items-center justify-center border-white/10 text-gray-400 hover:text-gray-200 hover:bg-white/5 hover:border-white/20"
                          onClick={() => handleViewDetails(element)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </SimpleTooltip>
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
