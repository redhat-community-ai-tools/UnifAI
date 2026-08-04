
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import axios from "../../../../http/axiosAgentConfig";
import { executeAction } from '@/api/actions';
import { useAuth } from "@/contexts/AuthContext";
import { FieldValidationTwoFactorAuth } from '../auth/FieldValidationTwoFactorAuth';


// Type guard to check if hint is an ApiHint (has endpoint) vs ActionHint (has action_uid)
const isApiHint = (hint: any): boolean => {
  return hint && typeof hint.endpoint === 'string' && hint.endpoint.length > 0;
};

// Per-item validation result for list fields
export interface ItemValidationResult {
  rid: string;
  isValid: boolean;
  message?: string;
}

interface FieldValidationProps {
  fieldName: string;
  fieldValue: any;
  validationHint: any;
  elementActions: any[];
  selectedElementType: any;
  isRequired?: boolean;
  /** All current config field values, used to resolve dependencies for validation actions */
  configValues?: Record<string, any>;
  /** Cached action outputs from other fields, for cross-field output references (field.key syntax) */
  actionOutputs?: Record<string, any>;
  onValidationChange: (fieldName: string, isValid: boolean, itemResults?: ItemValidationResult[]) => void;
  onInputChange?: (field: string, value: any) => void;
}

// Auth-related response statuses
const AUTH_STATUSES = new Set([
  'authenticated', 'requires_consent', 'expired',
  'not_configured', 'needs_client_registration',
  'auth_required', 'authenticated_but_rejected',
  'challenge',
]);

export const FieldValidation: React.FC<FieldValidationProps> = ({
  fieldName,
  fieldValue,
  validationHint,
  elementActions,
  selectedElementType,
  isRequired = false,
  configValues = {},
  actionOutputs = {},
  onValidationChange,
  onInputChange,
}) => {
  const { user } = useAuth();
  const userId = user?.username || "";

  const [validationState, setValidationState] = useState<{
    isValidating: boolean;
    isValid: boolean | null;
    message: string;
  }>({
    isValidating: false,
    isValid: null,
    message: ''
  });

  // Auth-specific state
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [authStatus, setAuthStatus] = useState<string | null>(null);
  const [authMessage, setAuthMessage] = useState<string | null>(null);

  const validationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastValidatedKeyRef = useRef<string | null>(null);

  // Determine if this is an ApiHint or ActionHint
  const useApiHint = isApiHint(validationHint);

  // Find the validation action from elementActions (only needed for ActionHint)
  const validationAction = !useApiHint 
    ? elementActions.find(action => action.uid === validationHint.action_uid)
    : null;

  /**
   * Creates a stable validation key that combines the field value and all dependency values.
   * This key is used to determine if validation should be re-triggered.
   * When either the field value or any dependency changes, this key will change.
   */
  /**
   * Resolves a dependency key to its value. Supports dot-notation for
   * cross-field output references: "field.output_key" reads from actionOutputs.
   */
  const resolveDependencyValue = (configField: string): any => {
    if (configField.includes('.')) {
      const [sourceField, outputKey] = configField.split('.', 2);
      return actionOutputs[sourceField]?.[outputKey];
    }
    return configValues[configField];
  };

  const validationKey = React.useMemo(() => {
    const dependencyValues: Record<string, any> = {};
    if (validationHint?.dependencies) {
      Object.keys(validationHint.dependencies).forEach((configField) => {
        if (configField !== fieldName) {
          dependencyValues[configField] = resolveDependencyValue(configField);
        }
      });
    }
    
    return JSON.stringify({
      fieldValue,
      dependencies: dependencyValues
    });
  }, [fieldValue, validationHint?.dependencies, fieldName, configValues, actionOutputs]);

  /**
   * Builds the input data for validation by:
   * 1. Always including the current field's value
   * 2. Gathering dependency values from configValues based on the hint's dependencies mapping
   * 
   * @param value - The current field's value
   * @param fieldNameMapping - Optional custom mapping for the current field name in the input
   * @returns Record with field values for the validation action/API
   */
  const buildInputWithDependencies = (value: any, fieldNameMapping?: string): Record<string, any> => {
    const inputData: Record<string, any> = {};
    
    const targetFieldName = fieldNameMapping || fieldName;
    inputData[targetFieldName] = value;
    
    if (validationHint.dependencies && Object.keys(validationHint.dependencies).length > 0) {
      Object.entries(validationHint.dependencies).forEach(([configField, actionField]) => {
        if (configField === fieldName) {
          return;
        }
        
        const dependencyValue = resolveDependencyValue(configField);
        if (dependencyValue !== undefined) {
          inputData[actionField as string] = dependencyValue;
        }
      });
    }
    
    return inputData;
  };

  /**
   * Fires the chained on_success action after the primary action succeeds.
   * Builds input from the chain hint's own dependencies and skips silently
   * if any required dependency value is empty.
   */
  const executeOnSuccessChain = async (chainHint: any) => {
    const chainAction = elementActions.find((a: any) => a.uid === chainHint.action_uid);
    if (!chainAction) return;

    const chainInput: Record<string, any> = {};
    if (chainHint.dependencies) {
      for (const [configField, actionField] of Object.entries(chainHint.dependencies)) {
        const val = configValues[configField];
        if (val === undefined || val === null || val === '') return;
        chainInput[actionField as string] = val;
      }
    }

    try {
      await executeAction(chainAction.uid, chainInput, userId);
    } catch (err) {
      console.warn('on_success chain action failed:', err);
    }
  };

  // Validate using ActionHint (via action system)
  const performActionValidation = async (value: any) => {
    if (!validationAction) {
      return { success: false, message: 'Validation action not found' };
    }

    // Determine the correct field name mapping for the current field
    let fieldNameMapping: string | undefined;
    
    // Check if the current field is explicitly mapped in dependencies
    if (validationHint.dependencies?.[fieldName]) {
      fieldNameMapping = validationHint.dependencies[fieldName];
    } else if (!validationAction.input_schema?.properties?.[fieldName]) {
      // If fieldName doesn't match input schema, try to find matching property
      const inputProperties = validationAction.input_schema?.properties || {};
      const inputKeys = Object.keys(inputProperties);
      
      // Use the first required property or first property as fallback
      const requiredFields = validationAction.input_schema?.required || [];
      fieldNameMapping = requiredFields.length > 0 ? requiredFields[0] : inputKeys[0];
    }

    const inputData = buildInputWithDependencies(value, fieldNameMapping);

    return executeAction(validationAction.uid, inputData, userId);
  };

  // Validate using ApiHint (direct API call)
  const performApiValidation = async (value: any) => {
    // Determine field name mapping for the current field
    const fieldNameMapping = validationHint.dependencies?.[fieldName] || fieldName;
    
    // Build request body with current field and dependencies
    const requestBody = buildInputWithDependencies(value, fieldNameMapping);
    if (userId) {
      requestBody.userId = userId;
    }

    // Determine the HTTP method (default to POST)
    const method = (validationHint.method || 'POST').toUpperCase();
    const endpoint = validationHint.endpoint;

    let response;
    if (method === 'GET') {
      // For GET requests, send data as query params
      response = await axios.get(endpoint, { params: requestBody });
    } else {
      // For POST/PUT/PATCH, send data in body
      response = await axios({
        method: method.toLowerCase(),
        url: endpoint,
        data: requestBody
      });
    }

    return response.data;
  };

  const performValidation = async (value: any) => {
    // For ActionHint, we need the action to exist
    if (!useApiHint && !validationAction) {
      setValidationState({ isValidating: false, isValid: null, message: '' });
      onValidationChange(fieldName, false);
      return;
    }

    // For ApiHint, we need the endpoint to exist
    if (useApiHint && !validationHint.endpoint) {
      setValidationState({ isValidating: false, isValid: null, message: '' });
      onValidationChange(fieldName, false);
      return;
    }

    // Skip if no value
    if (!value || value === '' || (Array.isArray(value) && value.length === 0)) {
      setValidationState({ isValidating: false, isValid: null, message: '' });
      setAuthUrl(null);
      setAuthStatus(null);
      // For non-required fields, empty value should not block save (report as valid)
      // For required fields, empty value is invalid
      onValidationChange(fieldName, !isRequired);
      return;
    }

    // Skip validation if neither the value nor dependencies have changed
    if (lastValidatedKeyRef.current === validationKey) {
      return;
    }

    setValidationState(prev => ({ ...prev, isValidating: true }));

    try {
      // Use the appropriate validation method based on hint type
      const responseData = useApiHint 
        ? await performApiValidation(value)
        : await performActionValidation(value);

      // Extract validation result based on field_mapping or default to 'success'
      const fieldMapping = validationHint.field_mapping || 'success';

      if (onInputChange && responseData.form_updates) {
        for (const [field, value] of Object.entries(responseData.form_updates)) {
          onInputChange(field, value as any);
        }
      }

      // ── Auth-aware response handling ──
      if (responseData.status && AUTH_STATUSES.has(responseData.status)) {
        lastValidatedKeyRef.current = validationKey;
        handleAuthResponse(responseData);
        return;
      }
      
      // ── Standard validation handling ──
      // Handle array responses (for list validation like resources.validate)
      if (Array.isArray(responseData)) {
        const itemResults: ItemValidationResult[] = responseData.map((item: any) => ({
          rid: item.element_rid || '',
          isValid: item[fieldMapping] === true,
          message: item.messages?.[0]?.message || (item[fieldMapping] ? 'Valid' : 'Invalid')
        }));
        
        // Field is valid only if ALL items are valid
        const allValid = itemResults.every(item => item.isValid);
        const invalidCount = itemResults.filter(item => !item.isValid).length;
        
        setValidationState({
          isValidating: false,
          isValid: allValid,
          message: allValid 
            ? `All ${itemResults.length} items valid` 
            : `${invalidCount} of ${itemResults.length} items invalid`
        });

        lastValidatedKeyRef.current = validationKey;
        onValidationChange(fieldName, allValid, itemResults);
      } else {
        // Single item response (original behavior)
        const isValid = responseData[fieldMapping] === true;

        if (isValid && validationHint.on_success) {
          await executeOnSuccessChain(validationHint.on_success);
        }
        
        setValidationState({
          isValidating: false,
          isValid,
          message: responseData.message || (isValid ? 'Valid' : 'Invalid')
        });

        lastValidatedKeyRef.current = validationKey;
        onValidationChange(fieldName, isValid);
      }

    } catch (error: any) {
      console.error('Validation error:', error);
      const errorMessage = error.response?.data?.message || 'Validation failed';
      
      setValidationState({ isValidating: false, isValid: false, message: errorMessage });
      onValidationChange(fieldName, false);
    }
  };

  /**
   * Dispatches an auth-aware response to the correct state-update path.
   * Uses switch/case so each auth status maps to exactly one update.
   */
  const handleAuthResponse = useCallback((data: any) => {
    const status: string = data.status;
    const message: string = data.message || '';

    switch (status) {
      case 'authenticated':
        setAuthUrl(null);
        setAuthStatus('authenticated');
        setAuthMessage(message);
        setValidationState({ isValidating: false, isValid: true, message });
        onValidationChange(fieldName, true);
        break;

      case 'requires_consent':
      case 'expired':
        setAuthUrl(data.authorization_url || null);
        setAuthStatus(status);
        setAuthMessage(message);
        setValidationState({ isValidating: false, isValid: null, message });
        onValidationChange(fieldName, false);
        break;

      case 'needs_client_registration':
        setAuthUrl(null);
        setAuthStatus('needs_client_registration');
        setAuthMessage(message || 'OAuth client registration required');
        setValidationState({ isValidating: false, isValid: false, message: message || '' });
        onValidationChange(fieldName, false);
        break;

      default:
        setAuthUrl(null);
        setAuthStatus(status);
        setAuthMessage(message);
        setValidationState({ isValidating: false, isValid: false, message });
        onValidationChange(fieldName, false);
        break;
    }
  }, [fieldName, onValidationChange]);

  /** Called by FieldValidationTwoFactorAuth after a successful OAuth callback */
  const handleAuthRevalidate = useCallback(() => {
    lastValidatedKeyRef.current = null;
    performValidation(fieldValue);
  }, [fieldValue]);

  /** Called by FieldValidationTwoFactorAuth when the OAuth popup reports failure */
  const handleAuthError = useCallback((errorMessage: string) => {
    setAuthStatus('error');
    setAuthMessage(errorMessage);
    setValidationState({ isValidating: false, isValid: false, message: errorMessage });
    onValidationChange(fieldName, false);
  }, [fieldName, onValidationChange]);

  // Debounced validation on field value change OR dependency value change
  const isInitialRenderRef = useRef(true);
  useEffect(() => {
    if (validationTimeoutRef.current) {
      clearTimeout(validationTimeoutRef.current);
    }

    if (!isInitialRenderRef.current) {
      lastValidatedKeyRef.current = null;
      setAuthStatus(null);
      setAuthUrl(null);
      setAuthMessage(null);
      onValidationChange(fieldName, false);
      setValidationState({ isValidating: true, isValid: null, message: '' });
    }
    isInitialRenderRef.current = false;

    validationTimeoutRef.current = setTimeout(() => {
      performValidation(fieldValue);
    }, 1500);

    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
    };
  }, [validationKey]); // Re-trigger when field value OR any dependency changes

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
    };
  }, []);

  // For ActionHint, we need a valid action; for ApiHint, we need an endpoint
  if (!useApiHint && !validationAction) {
    return null;
  }
  if (useApiHint && !validationHint.endpoint) {
    return null;
  }

  // ── Auth-aware rendering — delegated to sub-component ──

  if (authStatus) {
    return (
      <FieldValidationTwoFactorAuth
        authStatus={authStatus}
        authUrl={authUrl}
        authMessage={authMessage}
        onRevalidate={handleAuthRevalidate}
        onAuthError={handleAuthError}
      />
    );
  }

  // ── Standard validation rendering ──

  const renderValidationIcon = () => {
    if (validationState.isValidating) {
      return <Loader2 className="h-4 w-4 animate-spin text-blue-400" />;
    }
    if (validationState.isValid === true) {
      return <CheckCircle className="h-4 w-4 text-green-400" />;
    }
    if (validationState.isValid === false) {
      return <XCircle className="h-4 w-4 text-red-400" />;
    }
    return null;
  };

  const getValidationStatus = () => {
    if (validationState.isValidating) {
      return { color: 'text-blue-400', text: 'Validating...' };
    }
    if (validationState.isValid === true) {
      return { color: 'text-green-400', text: 'Valid' };
    }
    if (validationState.isValid === false) {
      return { color: 'text-red-400', text: 'Invalid' };
    }
    return { color: 'text-gray-400', text: 'Not validated' };
  };

  const status = getValidationStatus();

  return (
    <div className="flex items-center gap-2 mt-1">
      {renderValidationIcon()}
      <span className={`text-xs ${status.color}`}>
        {status.text}
      </span>
      {validationState.message && (
        <Badge variant="outline" className="text-xs">
          {validationState.message}
        </Badge>
      )}
    </div>
  );
};
