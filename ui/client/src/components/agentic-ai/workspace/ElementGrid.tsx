import React, { useState, useEffect, useMemo } from 'react';
import { LoaderCircle, Database } from 'lucide-react';
import { useShared } from '@/contexts/SharedContext';
import { useAgenticAI } from '@/contexts/AgenticAIContext';
import { useAuth } from "@/contexts/AuthContext";
import { useView } from "@/contexts/ViewContext";
import { usePrimaryLightColor } from "@/hooks/use-primary-light-color";
import { useTeamEditLockPoll } from "@/hooks/use-team-edit-lock-poll";
import { resolveEditLockStatus } from "@/lib/editLockStatus";
import { ElementInstance, ElementType, ElementSchema } from '../../../types/workspace';
import { ElementValidationResult } from '../../../types/validation';
import { ElementData } from './ElementData';
import { ValidationResultModal } from './ValidationResultModal';
import { BuiltInElementCard } from './BuiltInElementCard';
import { RegularElementCard } from './RegularElementCard';
import { getCardFields } from '@/lib/cardFields';

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
  const primaryLight = usePrimaryLightColor();
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
        if (element.ownership === 'builtin') {
          return (
            <BuiltInElementCard
              key={element.rid}
              element={element}
              elementType={elementType}
              elementSchema={elementSchema}
              onConfigureBuiltin={onConfigureBuiltin}
              index={index}
              primaryLight={primaryLight}
              validationStatus={isBuiltinValidatedType ? getValidationStatus(element.rid) : undefined}
              onValidationClick={() => handleValidationClick(element.rid)}
            />
          );
        }

        const cardFields = getCardFields(elementSchema, resolveRefsInConfig(element.config), 'custom');
        const { lockedByOther, lockUnknown, lockedByLabel } = resolveEditLockStatus(
          resourceEditLocks[element.rid],
          user?.username ?? "",
          "another teammate",
        );

        return (
          <RegularElementCard
            key={element.rid}
            element={element}
            elementType={elementType}
            index={index}
            cardFields={cardFields}
            primaryLight={primaryLight}
            validationStatus={getValidationStatus(element.rid)}
            lockedByOther={isTeamWorkspace && lockedByOther}
            lockUnknown={lockUnknown}
            lockedByLabel={lockedByLabel}
            onViewDetails={() => handleViewDetails(element)}
            onShare={() => handleShareElement(element)}
            onDelete={() => onDeleteElement(element.rid)}
            onEdit={() => onEditElement(element)}
            onValidationClick={() => handleValidationClick(element.rid)}
          />
        );
      })}

      <ElementData
        element={selectedElement}
        elementType={elementType}
        isOpen={isDetailsModalOpen}
        onOpenChange={setIsDetailsModalOpen}
        elementSchema={elementSchema}
      />

      <ValidationResultModal
        validationResult={selectedValidationResult}
        isOpen={isValidationModalOpen}
        onOpenChange={setIsValidationModalOpen}
      />
    </div>
  );
};
