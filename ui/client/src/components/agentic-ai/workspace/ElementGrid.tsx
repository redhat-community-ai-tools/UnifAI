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
import { ValidationResultModal } from './validation/ValidationResultModal';
import { BuiltInElementCard } from './BuiltInElementCard';
import { RegularElementCard } from './RegularElementCard';
import { getCardFields } from '@/lib/cardFields';

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
  const nonBuiltInElements = useMemo(
    () => elements.filter(el => el.ownership !== 'builtin'),
    [elements],
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
  // of the `elements` array so a re-render that produces an equivalent-but-new
  // array doesn't re-trigger validation calls.
  const validatedRidsKey = useMemo(
    () => elements.map(el => el.rid).join(','),
    [elements],
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
              validationStatus={getValidationStatus(element.rid)}
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
