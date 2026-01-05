import React from 'react';
import { CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { ElementValidationResult } from '@/types/validation';
import SimpleTooltip from '@/components/shared/SimpleTooltip';

interface NodeValidationIndicatorProps {
  validationResult?: ElementValidationResult;
  isValidating?: boolean;
  onClick?: (e: React.MouseEvent) => void;
  className?: string;
}

/**
 * A compact validation indicator component for displaying on graph nodes.
 * Shows a green checkmark for valid nodes, yellow warning for invalid nodes,
 * and a spinner while validation is in progress.
 */
export const NodeValidationIndicator: React.FC<NodeValidationIndicatorProps> = ({
  validationResult,
  isValidating = false,
  onClick,
  className = '',
}) => {
  // Show spinner while validating
  if (isValidating) {
    return (
      <div
        className={`flex items-center justify-center ${className}`}
        onClick={(e) => {
          e.stopPropagation();
        }}
      >
        <SimpleTooltip content={<p>Validating...</p>}>
          <div className="p-1 rounded-full bg-gray-700/50">
            <Loader2 className="h-3.5 w-3.5 text-gray-400 animate-spin" />
          </div>
        </SimpleTooltip>
      </div>
    );
  }

  // Don't show anything if no validation result
  if (!validationResult) {
    return null;
  }

  const isValid = validationResult.is_valid;

  // Count issues by severity
  const errorCount = validationResult.messages.filter(m => m.severity === 'error').length;
  const warningCount = validationResult.messages.filter(m => m.severity === 'warning').length;

  const tooltipContent = isValid
    ? 'Validation passed'
    : `${errorCount} error${errorCount !== 1 ? 's' : ''}${warningCount > 0 ? `, ${warningCount} warning${warningCount !== 1 ? 's' : ''}` : ''}`;

  return (
    <div
      className={`flex items-center justify-center cursor-pointer transition-transform hover:scale-110 ${className}`}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.(e);
      }}
    >
      <SimpleTooltip content={<p>{tooltipContent}</p>}>
        <div
          className={`p-1 rounded-full ${
            isValid
              ? 'bg-green-500/20 hover:bg-green-500/30'
              : 'bg-yellow-500/20 hover:bg-yellow-500/30'
          }`}
        >
          {isValid ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
          ) : (
            <AlertTriangle className="h-3.5 w-3.5 text-yellow-500" />
          )}
        </div>
      </SimpleTooltip>
    </div>
  );
};

export default NodeValidationIndicator;

