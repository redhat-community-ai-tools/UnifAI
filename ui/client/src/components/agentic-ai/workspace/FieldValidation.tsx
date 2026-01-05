
import React, { useState, useEffect, useRef } from 'react';
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import axios from "../../../http/axiosAgentConfig";

// Type guard to check if hint is an ApiHint (has endpoint) vs ActionHint (has action_uid)
const isApiHint = (hint: any): boolean => {
  return hint && typeof hint.endpoint === 'string' && hint.endpoint.length > 0;
};

interface FieldValidationProps {
  fieldName: string;
  fieldValue: any;
  validationHint: any;
  elementActions: any[];
  selectedElementType: any;
  onValidationChange: (fieldName: string, isValid: boolean) => void;
}

export const FieldValidation: React.FC<FieldValidationProps> = ({
  fieldName,
  fieldValue,
  validationHint,
  elementActions,
  selectedElementType,
  onValidationChange
}) => {
  const [validationState, setValidationState] = useState<{
    isValidating: boolean;
    isValid: boolean | null;
    message: string;
  }>({
    isValidating: false,
    isValid: null,
    message: ''
  });

  const validationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastValidatedValueRef = useRef<any>(null);

  // Determine if this is an ApiHint or ActionHint
  const useApiHint = isApiHint(validationHint);

  // Find the validation action from elementActions (only needed for ActionHint)
  const validationAction = !useApiHint 
    ? elementActions.find(action => action.uid === validationHint.action_uid)
    : null;

  // Validate using ActionHint (via action system)
  const performActionValidation = async (value: any) => {
    if (!validationAction) {
      return { success: false, message: 'Validation action not found' };
    }

    // Prepare input data based on validation action's input schema
    const inputData: any = {};
    
    // Map dependencies from validation hint or use field name directly
    if (validationHint.dependencies && Object.keys(validationHint.dependencies).length > 0) {
      Object.entries(validationHint.dependencies).forEach(([configField, actionField]) => {
        if (configField === fieldName) {
          inputData[actionField as string] = value;
        }
      });
    } else {
      // Check if the field name exists in the action's input schema
      if (validationAction.input_schema?.properties?.[fieldName]) {
        inputData[fieldName] = value;
      } else {
        // If fieldName doesn't match input schema, try to find matching property
        const inputProperties = validationAction.input_schema?.properties || {};
        const inputKeys = Object.keys(inputProperties);
        
        // Use the first required property or first property as fallback
        const requiredFields = validationAction.input_schema?.required || [];
        const targetField = requiredFields.length > 0 ? requiredFields[0] : inputKeys[0];
        
        if (targetField) {
          inputData[targetField] = value;
        }
      }
    }

    const response = await axios.post('/actions/action.execute', {
      uid: validationAction.uid,
      inputData
    });

    return response.data;
  };

  // Validate using ApiHint (direct API call)
  const performApiValidation = async (value: any) => {
    // Build request body from dependencies mapping
    const requestBody: any = {};
    
    if (validationHint.dependencies && Object.keys(validationHint.dependencies).length > 0) {
      Object.entries(validationHint.dependencies).forEach(([configField, requestField]) => {
        if (configField === fieldName) {
          requestBody[requestField as string] = value;
        }
      });
    } else {
      // If no dependencies specified, use the field name directly
      requestBody[fieldName] = value;
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
      setValidationState({
        isValidating: false,
        isValid: null,
        message: ''
      });
      onValidationChange(fieldName, false);
      return;
    }

    // For ApiHint, we need the endpoint to exist
    if (useApiHint && !validationHint.endpoint) {
      setValidationState({
        isValidating: false,
        isValid: null,
        message: ''
      });
      onValidationChange(fieldName, false);
      return;
    }

    // Skip if no value
    if (!value || value === '') {
      setValidationState({
        isValidating: false,
        isValid: null,
        message: ''
      });
      onValidationChange(fieldName, false);
      return;
    }

    // Skip validation if value hasn't changed
    if (lastValidatedValueRef.current === value) {
      return;
    }

    setValidationState(prev => ({
      ...prev,
      isValidating: true
    }));

    try {
      // Use the appropriate validation method based on hint type
      const responseData = useApiHint 
        ? await performApiValidation(value)
        : await performActionValidation(value);

      // Extract validation result based on field_mapping or default to 'success'
      const fieldMapping = validationHint.field_mapping || 'success';
      const isValid = responseData[fieldMapping] === true;
      
      setValidationState({
        isValidating: false,
        isValid,
        message: responseData.message || (isValid ? 'Valid' : 'Invalid')
      });

      lastValidatedValueRef.current = value;
      onValidationChange(fieldName, isValid);

    } catch (error: any) {
      console.error('Validation error:', error);
      const errorMessage = error.response?.data?.message || 'Validation failed';
      
      setValidationState({
        isValidating: false,
        isValid: false,
        message: errorMessage
      });

      onValidationChange(fieldName, false);
    }
  };

  // Debounced validation on value change
  useEffect(() => {
    if (validationTimeoutRef.current) {
      clearTimeout(validationTimeoutRef.current);
    }

    validationTimeoutRef.current = setTimeout(() => {
      performValidation(fieldValue);
    }, 1500); // 1.5 second delay

    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
    };
  }, [fieldValue]);

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
