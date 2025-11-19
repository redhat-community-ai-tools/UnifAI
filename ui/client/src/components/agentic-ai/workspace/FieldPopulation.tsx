
import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, RefreshCw } from 'lucide-react';
import axios from "../../../http/axiosAgentConfig";

interface FieldPopulationProps {
  fieldName: string;
  populateHint: any;
  elementActions: any[];
  selectedElementType: any;
  formData: any;
  onPopulateResult: (fieldName: string, results: string[], multiSelect: boolean) => void;
}

export const FieldPopulation: React.FC<FieldPopulationProps> = ({
  fieldName,
  populateHint,
  elementActions,
  selectedElementType,
  formData,
  onPopulateResult
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [populatedOptions, setPopulatedOptions] = useState<string[]>([]);
  const [selectedValues, setSelectedValues] = useState<string[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [shouldKeepOpen, setShouldKeepOpen] = useState(false);

  // Find the populate action from elementActions
  const populateAction = elementActions.find(
    action => action.uid === populateHint.action_uid
  );

  if (!populateAction) {
    return null;
  }

  // Effect to force dropdown to stay open for multi-select
  useEffect(() => {
    if (shouldKeepOpen && populateHint.multi_select && !isDropdownOpen) {
      const timer = setTimeout(() => {
        setIsDropdownOpen(true);
        setShouldKeepOpen(false);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [shouldKeepOpen, populateHint.multi_select, isDropdownOpen]);

  const performPopulation = async () => {
    setIsLoading(true);

    try {
      // Prepare input data based on populate action's input schema
      const inputData: any = {};
      
      // Map dependencies from populate hint or use field name directly
      if (populateHint.dependencies && Object.keys(populateHint.dependencies).length > 0) {
        Object.entries(populateHint.dependencies).forEach(([configField, actionField]) => {
          const configValue = formData[configField];
          if (configValue !== undefined && configValue !== null && configValue !== '') {
            inputData[actionField as string] = configValue;
          }
        });
      } else {
        // If no dependencies specified, use form data directly
        Object.keys(populateAction.input_schema?.properties || {}).forEach(inputField => {
          if (formData[inputField] !== undefined && formData[inputField] !== null && formData[inputField] !== '') {
            inputData[inputField] = formData[inputField];
          }
        });
      }

      const response = await axios.post('/actions/action.execute', {
        uid: populateAction.uid,
        inputData
      });

      // Extract results based on field_mapping
      const fieldMapping = populateHint.field_mapping || 'results';
      const results = response.data[fieldMapping] || [];
      
      // Ensure results is an array of strings
      const stringResults = Array.isArray(results) ? results.map(String) : [];
      
      setPopulatedOptions(stringResults);
      
      // If multi_select is false, clear previous selections
      if (!populateHint.multi_select) {
        setSelectedValues([]);
      }

      // Notify parent component
      onPopulateResult(fieldName, stringResults, populateHint.multi_select || false);

    } catch (error: any) {
      console.error('Population error:', error);
      const errorMessage = error.response?.data?.message || 'Population failed';
      // You might want to show this error to the user
      console.warn(`Failed to populate ${fieldName}:`, errorMessage);
      setPopulatedOptions([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectChange = (value: string) => {
    if (!value || value === "__no_options_disabled__") return;

    let newSelectedValues: string[];
    
    if (populateHint.multi_select) {
      // Multi-select: add if not already selected
      if (!selectedValues.includes(value)) {
        newSelectedValues = [...selectedValues, value];
      } else {
        newSelectedValues = selectedValues;
      }
    } else {
      // Single select: replace current selection
      newSelectedValues = [value];
    }

    setSelectedValues(newSelectedValues);
    
    // Update parent component with selected values
    onPopulateResult(fieldName, newSelectedValues, populateHint.multi_select || false);
  };

  // Handle item selection for multi-select to keep dropdown open
  const handleItemSelect = (value: string) => {
    handleSelectChange(value);
    // For multi-select, signal that we want to keep the dropdown open
    if (populateHint.multi_select) {
      setShouldKeepOpen(true);
    }
  };

  const removeSelectedValue = (valueToRemove: string) => {
    const newSelectedValues = selectedValues.filter(val => val !== valueToRemove);
    setSelectedValues(newSelectedValues);
    onPopulateResult(fieldName, newSelectedValues, populateHint.multi_select || false);
  };

  const getAvailableOptions = () => {
    if (populateHint.multi_select) {
      // For multi-select, show options that aren't already selected
      return populatedOptions.filter(option => !selectedValues.includes(option));
    }
    // For single select, show all options
    return populatedOptions;
  };

  const availableOptions = getAvailableOptions();

  return (
    <div className="space-y-3">
      {/* Populate Button */}
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={performPopulation}
          disabled={isLoading}
          className="flex items-center gap-2"
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          {populateAction.uid}
        </Button>
        <Badge variant="outline" className="text-xs">
          populate
        </Badge>
        {populateHint.multi_select && (
          <Badge variant="outline" className="text-xs">
            multi-select
          </Badge>
        )}
      </div>

      {/* Selection Dropdown (only show if we have options) */}
      {populatedOptions.length > 0 && (
        <div className="space-y-2">
          <Select
            value=""
            open={isDropdownOpen}
            onOpenChange={(open) => {
              setIsDropdownOpen(open);
            }}
            onValueChange={(value) => {
              if (populateHint.multi_select) {
                handleItemSelect(value);
              } else {
                handleSelectChange(value);
                setIsDropdownOpen(false);
              }
            }}
          >
            <SelectTrigger className="bg-background-dark">
              <SelectValue placeholder={
                populateHint.multi_select 
                  ? `Add ${populateHint.field_mapping || 'option'}...`
                  : `Select ${populateHint.field_mapping || 'option'}...`
              } />
            </SelectTrigger>
            <SelectContent
              onCloseAutoFocus={(e) => {
                // Prevent auto-focus to allow multiple selections for multi-select
                if (populateHint.multi_select) {
                  e.preventDefault();
                }
              }}
              onPointerDownOutside={() => {
                // Close when clicking outside
                setIsDropdownOpen(false);
              }}
              onEscapeKeyDown={() => {
                // Close on Escape key
                setIsDropdownOpen(false);
              }}
            >
              {availableOptions.map((option: string, index: number) => (
                <SelectItem 
                  key={index} 
                  value={option}
                  onSelect={(event) => {
                    if (populateHint.multi_select) {
                      event.preventDefault();
                      handleItemSelect(option);
                    }
                  }}
                >
                  {option}
                </SelectItem>
              ))}
              {availableOptions.length === 0 && populatedOptions.length > 0 && (
                <SelectItem value="__no_options_disabled__" disabled>
                  {populateHint.multi_select ? 'All options selected' : 'No options available'}
                </SelectItem>
              )}
              {populatedOptions.length === 0 && (
                <SelectItem value="__no_options_disabled__" disabled>
                  No options available
                </SelectItem>
              )}
            </SelectContent>
          </Select>

          {/* Show selected items (for multi-select or single select) */}
          {selectedValues.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {selectedValues.map((selectedValue: string, index: number) => (
                <Badge
                  key={index}
                  variant="secondary"
                  className="flex items-center gap-1 bg-gray-700 text-white border-gray-600 hover:bg-gray-600"
                >
                  {selectedValue}
                  <button
                    type="button"
                    onClick={() => removeSelectedValue(selectedValue)}
                    className="ml-1 text-xs text-gray-300 hover:text-red-400 transition-colors"
                  >
                    ×
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Show message when no options populated yet */}
      {populatedOptions.length === 0 && !isLoading && (
        <p className="text-xs text-gray-400">
          Click the button above to populate {populateHint.field_mapping || 'options'}
        </p>
      )}
    </div>
  );
};
