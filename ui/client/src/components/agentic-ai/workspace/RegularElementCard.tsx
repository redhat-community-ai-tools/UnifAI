import React from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings, Trash2, FileText, Eye, Users, Clock } from 'lucide-react';
import SimpleTooltip from '@/components/shared/SimpleTooltip';
import { SelectionCheckbox } from '@/components/shared/SelectionCheckbox';
import { ElementInstance, ElementType } from '../../../types/workspace';
import { ValidationStatus } from '@/contexts/AgenticAIContext';
import { CardField } from '@/lib/cardFields';
import { CardFieldList } from './CardFieldList';
import { ValidationStatusBadge } from './validation/ValidationStatusBadge';
import { cn } from "@/lib/utils";

interface RegularElementCardProps {
  element: ElementInstance;
  elementType: ElementType;
  index: number;
  cardFields: CardField[];
  primaryLight: string;
  validationStatus: ValidationStatus;
  lockedByOther: boolean;
  lockUnknown: boolean;
  lockedByLabel: string;
  onViewDetails: () => void;
  onShare: () => void;
  onDelete: () => void;
  onEdit: () => void;
  onValidationClick: () => void;
  /** When set, card is in multiselect mode and shows a checkbox. */
  isSelected?: boolean;
  onSelectionChange?: (checked: boolean) => void;
}

/** Inventory card for a non-built-in (user-owned) element instance. */
export const RegularElementCard: React.FC<RegularElementCardProps> = ({
  element,
  elementType,
  index,
  cardFields,
  primaryLight,
  validationStatus,
  lockedByOther,
  lockUnknown,
  lockedByLabel,
  onViewDetails,
  onShare,
  onDelete,
  onEdit,
  onValidationClick,
  isSelected = false,
  onSelectionChange,
}) => {
  const isLocked = lockedByOther || lockUnknown;
  const selectionMode = typeof onSelectionChange === 'function';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.3, delay: Math.min(index, 10) * 0.1 } }}
      whileHover={{ y: -8, scale: 1.03, transition: { duration: 0.15, delay: 0 } }}
      whileTap={{ scale: 0.97, transition: { duration: 0.1, delay: 0 } }}
      className="h-full"
    >
      <Card
        className={cn(
          "group relative bg-background-card border h-full flex flex-col cursor-pointer transition-all duration-300",
          isSelected
            ? "border-primary/60 shadow-xl shadow-primary/15 ring-1 ring-primary/40"
            : "border-white/10 hover:border-primary/50 hover:shadow-xl hover:shadow-primary/10",
        )}
        onClick={() => {
          if (selectionMode) {
            onSelectionChange!(!isSelected);
            return;
          }
          onViewDetails();
        }}
      >
        {isSelected && (
          <div
            className="pointer-events-none absolute inset-0 rounded-[inherit] bg-primary/5"
            aria-hidden
          />
        )}
        <CardHeader className="py-3.5 px-4 border-b border-white/5">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2.5 min-w-0">
              {selectionMode ? (
                <div
                  className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 transition-colors duration-300 group-hover:bg-primary/20"
                  onClick={(e) => e.stopPropagation()}
                >
                  <SelectionCheckbox
                    checked={isSelected}
                    onCheckedChange={onSelectionChange!}
                    ariaLabel={`Select resource ${element.name || element.rid}`}
                    align="center"
                  />
                </div>
              ) : (
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 transition-colors duration-300 group-hover:bg-primary/20">
                  <FileText className="h-4 w-4" style={{ color: primaryLight }} />
                </div>
              )}
              <CardTitle className="text-lg font-heading truncate leading-tight min-w-0" title={element.name || undefined}>
                {element.name || `${elementType.name} Instance`}
              </CardTitle>
            </div>
            <div className="flex items-center gap-0.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
              <ValidationStatusBadge status={validationStatus} onClick={onValidationClick} />
              {!selectionMode && (
                <>
                  <SimpleTooltip content={<p>Share this resource</p>}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-gray-400 hover:text-[var(--share-icon-accent)] hover:bg-primary/10"
                      style={{ '--share-icon-accent': primaryLight } as React.CSSProperties}
                      onClick={onShare}
                    >
                      <Users className="h-4 w-4" />
                    </Button>
                  </SimpleTooltip>
                  <SimpleTooltip content={<p>Delete this resource</p>}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-gray-400 hover:text-red-400"
                      onClick={onDelete}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </SimpleTooltip>
                </>
              )}
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
              <span className={cn("flex flex-1", isLocked && "cursor-not-allowed")}>
                <Button
                  variant="outline"
                  size="sm"
                  className={cn(
                    "flex flex-1 items-center justify-center gap-1.5 h-9 text-sm border-primary/30 text-primary hover:bg-primary/10 hover:border-primary/50",
                    isLocked && "pointer-events-none",
                  )}
                  onClick={onEdit}
                  disabled={isLocked}
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
                onClick={onViewDetails}
              >
                <Eye className="h-4 w-4" />
              </Button>
            </SimpleTooltip>
          </div>
        </CardFooter>
      </Card>
    </motion.div>
  );
};
