
import React, { useState, useEffect, useRef } from 'react';
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import axios from "../../../http/axiosAgentConfig";

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

  // Find the validation action from elementActions
  const validationAction = elementActions.find(
    action => action.uid === validationHint.action_uid
  );

  const performValidation = async (value: any) => {
    if (!validationAction || !value || value === '') {
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

      // Extract validation result based on field_mapping or default to 'success'
      const fieldMapping = validationHint.field_mapping || 'success';
      const isValid = response.data[fieldMapping] === true;
      
      setValidationState({
        isValidating: false,
        isValid,
        message: response.data.message || (isValid ? 'Valid' : 'Invalid')
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

  if (!validationAction) {
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
