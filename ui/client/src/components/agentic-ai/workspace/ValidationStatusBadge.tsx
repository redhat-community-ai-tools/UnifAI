import React from 'react';
import { Check, AlertTriangle, LoaderCircle } from 'lucide-react';
import SimpleTooltip from '@/components/shared/SimpleTooltip';
import { ValidationStatus } from '@/contexts/AgenticAIContext';

interface ValidationStatusBadgeProps {
  status: ValidationStatus;
  onClick?: () => void;
}

/**
 * Small validity indicator for a resource's inventory card — shared by the
 * custom-element card in `ElementGrid` and `BuiltInElementCard` (for built-in
 * elements whose validity is worth surfacing, e.g. built-in MCP servers).
 */
export const ValidationStatusBadge: React.FC<ValidationStatusBadgeProps> = ({ status, onClick }) => {
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
          type="button"
          aria-label="Resource is valid. Click for details"
          className="flex items-center justify-center w-8 h-8 rounded-md bg-green-500/10 hover:bg-green-500/20 transition-colors cursor-pointer"
          onClick={onClick}
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
          type="button"
          aria-label="Resource is invalid. Click for details"
          className="flex items-center justify-center w-8 h-8 rounded-md bg-yellow-500/10 hover:bg-yellow-500/20 transition-colors cursor-pointer"
          onClick={onClick}
        >
          <AlertTriangle className="h-4 w-4 text-yellow-500" />
        </button>
      </SimpleTooltip>
    );
  }

  return null;
};
