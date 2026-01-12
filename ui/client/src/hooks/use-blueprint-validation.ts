import { useState, useCallback } from 'react';
import { validateBlueprint } from '@/api/blueprints';
import { BlueprintValidationResult, ElementValidationResult } from '@/types/validation';
import { useToast } from '@/hooks/use-toast';

export interface UseBlueprintValidationOptions {
  /** Callback when validation state changes */
  onValidationChange?: (isValid: boolean, validationResult: BlueprintValidationResult | null, isValidating: boolean) => void;
  /** Callback to cache validation results */
  onCacheResults?: (result: BlueprintValidationResult) => void;
  /** Whether to show toast notifications on validation failure */
  showToastOnFailure?: boolean;
}

export interface UseBlueprintValidationResult {
  /** Whether validation is currently in progress */
  isValidating: boolean;
  /** Validation results by element ID */
  validationResults: Record<string, ElementValidationResult>;
  /** Whether the current blueprint is valid */
  isValid: boolean;
  /** Function to validate a blueprint by ID */
  validateBlueprint: (blueprintId: string) => Promise<void>;
  /** Function to clear validation state */
  clearValidation: () => void;
}

/**
 * Hook to manage blueprint validation state and logic.
 * Used by components that need to validate blueprints and display validation results.
 */
export function useBlueprintValidation(
  options: UseBlueprintValidationOptions = {}
): UseBlueprintValidationResult {
  const { 
    onValidationChange, 
    onCacheResults, 
    showToastOnFailure = true 
  } = options;
  
  const { toast } = useToast();
  
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationResults, setValidationResults] = useState<Record<string, ElementValidationResult>>({});
  const [isValid, setIsValid] = useState<boolean>(true);

  const clearValidation = useCallback(() => {
    setValidationResults({});
    setIsValid(true);
    onValidationChange?.(true, null, false);
  }, [onValidationChange]);

  const validate = useCallback(async (blueprintId: string) => {
    setIsValidating(true);
    setValidationResults({});
    setIsValid(true); // Assume valid until proven otherwise
    
    // Notify parent that validation is starting
    onValidationChange?.(true, null, true);
    
    try {
      const result = await validateBlueprint({ blueprintId });
      setValidationResults(result.element_results || {});
      setIsValid(result.is_valid);
      
      // Cache validation results if callback provided
      if (result && onCacheResults) {
        onCacheResults(result);
      }
      
      // Notify parent of validation result
      onValidationChange?.(result.is_valid, result, false);
      
      // Show toast if validation failed
      if (!result.is_valid && showToastOnFailure) {
        const errorCount = Object.values(result.element_results).filter(r => !r.is_valid).length;
        toast({
          title: "Workflow Validation Failed",
          description: `${errorCount} element${errorCount !== 1 ? 's' : ''} failed validation.`,
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error("Error validating blueprint:", error);
      setIsValid(false);
      
      // Notify parent that validation failed
      onValidationChange?.(false, null, false);
      
      if (showToastOnFailure) {
        toast({
          title: "Validation Error",
          description: "Failed to validate the workflow. Please try again.",
          variant: "destructive",
        });
      }
    } finally {
      setIsValidating(false);
    }
  }, [onValidationChange, onCacheResults, showToastOnFailure, toast]);

  return {
    isValidating,
    validationResults,
    isValid,
    validateBlueprint: validate,
    clearValidation,
  };
}

