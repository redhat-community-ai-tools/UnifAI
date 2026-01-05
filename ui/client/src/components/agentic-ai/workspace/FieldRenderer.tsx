import React, { useState, useEffect, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldValidation } from "./FieldValidation";
import { FieldPopulation } from "./FieldPopulation";
import { AgentCardVisualization } from "./AgentCardVisualization";
import { ElementType } from "../../../types/workspace";
import { maskSecretValue } from "../../../utils/maskSecretFields";
import { XCircle } from "lucide-react";

interface FieldRendererProps {
  fieldName: string;
  fieldSchema: any;
  value: any;
  isRequired: boolean;
  validationHint: any;
  populateHint: any;
  editingElement: any;
  elementActions: any[];
  elementType: ElementType;
  formData: any;
  refOptions: { [category: string]: any[] };
  fieldType: "secret" | "public";
  fieldValidationStates?: { [fieldName: string]: boolean };
  isArrayWithRefItems: (fieldSchema: any) => boolean;
  getArrayItemsSchema: (fieldSchema: any) => any;
  extractCategoryFromField: (fieldSchema: any) => string | null;
  onInputChange: (field: string, value: any) => void;
  onArrayChange?: (field: string, index: number, value: any) => void;
  onAddArrayItem?: (field: string) => void;
  onRemoveArrayItem?: (field: string, index: number) => void;
  onValidationChange: (fieldName: string, isValid: boolean) => void;
  onPopulateResult: (fieldName: string, results: string[] | any, multiSelect: boolean) => void;
}

export const FieldRenderer: React.FC<FieldRendererProps> = ({
  fieldName,
  fieldSchema,
  value,
  isRequired,
  validationHint,
  populateHint,
  editingElement,
  elementActions,
  elementType,
  formData,
  refOptions,
  fieldType,
  fieldValidationStates,
  isArrayWithRefItems,
  getArrayItemsSchema,
  extractCategoryFromField,
  onInputChange,
  onArrayChange,
  onAddArrayItem,
  onRemoveArrayItem,
  onValidationChange,
  onPopulateResult,
}) => {
  // Check if this field has validation errors based on validation action result
  // Use useMemo to recalculate when fieldValidationStates changes after validation action
  const hasFieldError = React.useMemo(() => {
    return validationHint && fieldValidationStates?.[fieldName] === false;
  }, [validationHint, fieldValidationStates, fieldName]);

  const [showMasked, setShowMasked] = useState(true);
  const isSecret = fieldType === "secret";

  // Calculate if dependencies are validated for automatic population fields
  const areDependenciesValid = React.useMemo(() => {
    if (populateHint?.selection_type === "automatic" && populateHint?.dependencies) {
      const dependencies = populateHint.dependencies || {};
      const dependencyKeys = Object.keys(dependencies);
      return dependencyKeys.every((depKey) => fieldValidationStates?.[depKey] === true);
    }
    return false;
  }, [populateHint, fieldValidationStates]);

  // Track previous dependency values for automatic population fields
  const prevDependencyValuesRef = useRef<{[key: string]: any}>({});
  
  // Clear field value when dependency values change (for automatic population fields)
  useEffect(() => {
    if (populateHint?.selection_type === "automatic" && populateHint?.dependencies) {
      const dependencies = populateHint.dependencies || {};
      const dependencyKeys = Object.keys(dependencies);
      
      const currentDependencyValues: {[key: string]: any} = {};
      dependencyKeys.forEach((depKey) => {
        currentDependencyValues[depKey] = formData[depKey];
      });

      // Check if any dependency value has changed
      const hasChanged = dependencyKeys.some((depKey) => {
        return prevDependencyValuesRef.current[depKey] !== currentDependencyValues[depKey];
      });

      if (hasChanged && Object.keys(prevDependencyValuesRef.current).length > 0) {
        // Dependency changed - clear the field value
        console.log(`Dependency changed - clearing field value for ${fieldName}`);
        onInputChange(fieldName, null);
      }

      // Update the ref with current values
      prevDependencyValuesRef.current = currentDependencyValues;
    }
  }, [fieldName, populateHint?.selection_type, populateHint?.dependencies, formData, onInputChange]);

  // Secret field masking logic
  const getSecretInputProps = () => {
    if (!isSecret) {
      return {
        displayValue: value || "",
        inputType: "text" as const,
        handleChange: (e: React.ChangeEvent<HTMLInputElement>) => {
          onInputChange(fieldName, e.target.value);
        },
        handleFocus: () => {},
      };
    }

    // In edit mode: if value exists and matches original, show masked dots
    const originalValue = editingElement?.config?.[fieldName];
    const isUnchanged = editingElement && value && value === originalValue;

    // Display: show masked dots if unchanged, otherwise show actual (password type)
    const displayValue =
      isUnchanged && showMasked
        ? maskSecretValue(originalValue, fieldSchema)
        : value || "";
    const inputType = isUnchanged && showMasked ? "text" : "password";

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      // User started typing - stop showing masked
      if (showMasked) {
        setShowMasked(false);
      }
      onInputChange(fieldName, e.target.value);
    };

    const handleFocus = () => {
      // When user focuses, stop showing masked so they can type
      if (showMasked) {
        setShowMasked(false);
      }
    };

    return { displayValue, inputType, handleChange, handleFocus };
  };

  // Handle array fields with $ref items (multi-select dropdown)
  if (isArrayWithRefItems(fieldSchema)) {
    const itemsSchema = getArrayItemsSchema(fieldSchema);
    const category = extractCategoryFromField(fieldSchema);

    if (!category) {
      console.warn(`No category found for array field ${fieldName}`);
      return null;
    }

    const validOptions = (refOptions[category] || []).filter(
      (option: any) => option.rid && option.rid.trim() !== "",
    );

    return (
      <div key={fieldName} className="space-y-2">
        <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {category && (
            <Badge variant="outline" className="ml-2 text-xs">
              {category}
            </Badge>
          )}
          {validationHint && (
            <Badge variant="outline" className="ml-2 text-xs">
              validation
            </Badge>
          )}
          {populateHint && (
            <Badge variant="outline" className="ml-2 text-xs">
              populate
            </Badge>
          )}
          {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
        </Label>
        
        {fieldSchema.description && (
          <p className="text-xs text-gray-400">{fieldSchema.description}</p>
        )}

        <div className="space-y-2">
          <Select
            value=""
            onValueChange={(newValue) => {
              if (newValue && newValue !== "__no_options_disabled__") {
                const currentArray = formData[fieldName] || [];
                if (!currentArray.includes(newValue)) {
                  onInputChange(fieldName, [...currentArray, newValue]);
                }
              }
            }}
          >
            <SelectTrigger className={`bg-background-dark ${hasFieldError ? 'border-red-500' : ''}`}>
              <SelectValue placeholder={`Add ${category}`} />
            </SelectTrigger>
            <SelectContent>
              {validOptions.map((option: any) => (
                <SelectItem key={option.rid} value={option.rid}>
                  {option.name} ({option.type})
                </SelectItem>
              ))}
              {validOptions.length === 0 && (
                <SelectItem value="__no_options_disabled__" disabled>
                  No {category} resources available
                </SelectItem>
              )}
            </SelectContent>
          </Select>

          {/* Show selected items */}
          {value && Array.isArray(value) && value.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {value.map((selectedRid: string, index: number) => {
                const selectedOption = validOptions.find(
                  (opt: any) => opt.rid === selectedRid,
                );
                return (
                  <Badge
                    key={index}
                    variant="secondary"
                    className="flex items-center gap-1"
                  >
                    {selectedOption
                      ? `${selectedOption.name} (${selectedOption.type})`
                      : selectedRid}
                    <button
                      type="button"
                      onClick={() => {
                        const newArray = value.filter(
                          (_: any, i: number) => i !== index,
                        );
                        onInputChange(fieldName, newArray);
                      }}
                      className="ml-1 text-xs hover:text-red-400"
                    >
                      ×
                    </button>
                  </Badge>
                );
              })}
            </div>
          )}
        </div>

        {/* Validation component for array $ref fields */}
        {validationHint && (
          <FieldValidation
            fieldName={fieldName}
            fieldValue={value}
            validationHint={validationHint}
            elementActions={elementActions}
            selectedElementType={elementType}
            onValidationChange={onValidationChange}
          />
        )}

        {/* Population component for array $ref fields */}
        {populateHint && (
          <FieldPopulation
            fieldName={fieldName}
            populateHint={populateHint}
            elementActions={elementActions}
            selectedElementType={elementType}
            formData={formData}
            onPopulateResult={onPopulateResult}
            hideUI={populateHint.selection_type === 'automatic'}
            autoTrigger={areDependenciesValid}
            currentValue={value}
          />
        )}
      </div>
    );
  }

  // Handle $ref fields (dropdown selection) - including anyOf with $ref
  const hasRefField =
    fieldSchema.$ref ||
    (fieldSchema.anyOf &&
      fieldSchema.anyOf.some((option: any) => option.$ref));

  if (hasRefField) {
    const category = extractCategoryFromField(fieldSchema);

    if (category) {
      const validOptions = (refOptions[category] || []).filter(
        (option: any) => option.rid && option.rid.trim() !== "",
      );

      return (
        <div key={fieldName} className="space-y-2">
          <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
            {fieldName} {isRequired && <span className="text-red-400">*</span>}
            {category && (
              <Badge variant="outline" className="ml-2 text-xs">
                {category}
              </Badge>
            )}
            {validationHint && (
              <Badge variant="outline" className="ml-2 text-xs">
                validation
              </Badge>
            )}
            {populateHint && (
              <Badge variant="outline" className="ml-2 text-xs">
                populate
              </Badge>
            )}
            {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
          </Label>
          
          {fieldSchema.description && (
            <p className="text-xs text-gray-400">{fieldSchema.description}</p>
          )}

          <Select
            value={value && value !== "" ? value : undefined}
            onValueChange={(newValue) => {
              onInputChange(fieldName, newValue);
            }}
          >
            <SelectTrigger className={`bg-background-dark ${hasFieldError ? 'border-red-500' : ''}`}>
              <SelectValue placeholder={`Select ${fieldName}`} />
            </SelectTrigger>
            <SelectContent>
              {validOptions.map((option: any) => (
                <SelectItem 
                  key={option.rid} 
                  value={option.rid}
                >
                  {option.name} ({option.type})
                </SelectItem>
              ))}
              {validOptions.length === 0 && (
                <SelectItem value="__no_options_disabled__" disabled>
                  No {category} resources available
                </SelectItem>
              )}
            </SelectContent>
          </Select>

          {/* Validation component for $ref fields */}
          {validationHint && (
            <FieldValidation
              fieldName={fieldName}
              fieldValue={value}
              validationHint={validationHint}
              elementActions={elementActions}
              selectedElementType={elementType}
              onValidationChange={onValidationChange}
            />
          )}

          {/* Population component for $ref fields */}
          {populateHint && (
            <FieldPopulation
              fieldName={fieldName}
              populateHint={populateHint}
              elementActions={elementActions}
              selectedElementType={elementType}
              formData={formData}
              onPopulateResult={onPopulateResult}
              hideUI={populateHint.selection_type === 'automatic'}
              autoTrigger={areDependenciesValid}
              currentValue={value}
            />
          )}
        </div>
      );
    }
  }


  // Handle object fields (like 'extra')
  if (fieldSchema.type === "object") {
    return (
      <div key={fieldName} className="space-y-2">
        <Label htmlFor={fieldName} className="flex items-center">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
        </Label>
        <Textarea
          id={fieldName}
          value={
            typeof value === "object" ? JSON.stringify(value, null, 2) : value
          }
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              onInputChange(fieldName, parsed);
            } catch (error) {
              // If invalid JSON, store as string for now
              onInputChange(fieldName, e.target.value);
            }
          }}
          rows={6}
          className={`bg-background-dark resize-none font-mono text-sm ${hasFieldError ? 'border-red-500' : ''}`}
          placeholder="Enter JSON object (e.g., {})"
        />
        {fieldSchema.description && (
          <p className="text-xs text-gray-400">{fieldSchema.description}</p>
        )}
      </div>
    );
  }

  // Handle array fields (non-$ref arrays)
  if (fieldSchema.type === "array") {
    if (!onArrayChange || !onAddArrayItem || !onRemoveArrayItem) {
      console.warn(
        "Array handlers not provided for array field",
        fieldName,
      );
      return null;
    }

    return (
      <div key={fieldName} className="space-y-2">
        <Label className="flex items-center">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
        </Label>
        <div className="space-y-2">
          {(value || []).map((item: any, index: number) => (
            <div key={index} className="flex gap-2">
              <Input
                value={item}
                onChange={(e) => onArrayChange(fieldName, index, e.target.value)}
                className={`bg-background-dark flex-1 ${hasFieldError ? 'border-red-500' : ''}`}
                placeholder={`${fieldName} item ${index + 1}`}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onRemoveArrayItem(fieldName, index)}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onAddArrayItem(fieldName)}
          >
            Add {fieldName}
          </Button>
        </div>
        {fieldSchema.description && (
          <p className="text-xs text-gray-400">{fieldSchema.description}</p>
        )}
      </div>
    );
  }

  // Handle boolean fields
  if (fieldSchema.type === "boolean") {
    return (
      <div key={fieldName} className="space-y-2">
        <div className="flex items-center space-x-2">
          <Checkbox
            id={fieldName}
            checked={value}
            onCheckedChange={(checked) => onInputChange(fieldName, checked)}
            className={hasFieldError ? 'border-red-500' : ''}
          />
          <Label htmlFor={fieldName} className="flex items-center">
            {fieldName}{" "}
            {isRequired && <span className="text-red-400">*</span>}
            {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
          </Label>
        </div>
        {fieldSchema.description && (
          <p className="text-xs text-gray-400">{fieldSchema.description}</p>
        )}
      </div>
    );
  }

  // Handle number fields (including anyOf with integer/number types)
  const isNumberField =
    fieldSchema.type === "integer" ||
    fieldSchema.type === "number" ||
    (fieldSchema.anyOf &&
      fieldSchema.anyOf.some(
        (option: any) =>
          option.type === "integer" || option.type === "number",
      ));

  if (isNumberField) {
    return (
      <div key={fieldName} className="space-y-2">
        <Label htmlFor={fieldName} className="flex items-center">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
        </Label>
        <Input
          id={fieldName}
          type="number"
          value={value || ""}
          onChange={(e) => {
            const numValue =
              e.target.value === "" ? null : parseFloat(e.target.value);
            onInputChange(fieldName, numValue);
          }}
          className={`bg-background-dark ${hasFieldError ? 'border-red-500' : ''}`}
          placeholder={fieldSchema.description}
        />
        {fieldSchema.description && (
          <p className="text-xs text-gray-400">{fieldSchema.description}</p>
        )}
      </div>
    );
  }

  // Handle long text fields
  if (
    fieldName.includes("message") ||
    fieldName.includes("prompt") ||
    fieldName.includes("description")
  ) {
    return (
      <div key={fieldName} className="space-y-2">
        <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {isSecret && (
            <Badge variant="outline" className="ml-2 text-xs">
              secret
            </Badge>
          )}
          {validationHint && (
            <Badge variant="outline" className="ml-2 text-xs">
              validation
            </Badge>
          )}
        {populateHint && (
          <Badge variant="outline" className="ml-2 text-xs">
            populate
          </Badge>
        )}
        {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
      </Label>

      {fieldSchema.description && (
        <p className="text-xs text-gray-400">{fieldSchema.description}</p>
      )}

      {populateHint?.selection_type != 'automatic' && (
        <Textarea
          id={fieldName}
          value={value}
          onChange={(e) => onInputChange(fieldName, e.target.value)}
          rows={4}
          className={`bg-background-dark resize-none ${hasFieldError ? 'border-red-500' : ''}`}
          placeholder={fieldSchema.description}
          readOnly={!!populateHint}
          disabled={!!populateHint}
        />
      )}

      {validationHint && (
        <FieldValidation
          fieldName={fieldName}
          fieldValue={value}
          validationHint={validationHint}
          elementActions={elementActions}
          selectedElementType={elementType}
          onValidationChange={onValidationChange}
        />
      )}
      {populateHint && (
        <FieldPopulation
          fieldName={fieldName}
          populateHint={populateHint}
          elementActions={elementActions}
          selectedElementType={elementType}
          formData={formData}
          onPopulateResult={onPopulateResult}
          hideUI={populateHint.selection_type == 'automatic'}
          autoTrigger={areDependenciesValid}
          currentValue={value}
        />
      )}
      {/* Agent Card Visualization */}
      {fieldName === "agent_card" && (
        <AgentCardVisualization agentCard={value} 
        />
      )}
    </div>
  );
}

  // Handle regular string fields (with secret masking if needed)
  const secretProps = getSecretInputProps();

  return (
    <div key={fieldName} className="space-y-2">
      <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
        {fieldName} {isRequired && <span className="text-red-400">*</span>}
        {isSecret && (
          <Badge variant="outline" className="ml-2 text-xs">
            secret
          </Badge>
        )}
        {validationHint && (
          <Badge variant="outline" className="ml-2 text-xs">
            validation
          </Badge>
        )}
      {populateHint && (
        <Badge variant="outline" className="ml-2 text-xs">
          populate
        </Badge>
      )}
      {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
    </Label>
    
    {fieldSchema.description && (
      <p className="text-xs text-gray-400">{fieldSchema.description}</p>
    )}

    {populateHint?.selection_type != 'automatic' && (
      <Input
        id={fieldName}
        type={secretProps.inputType}
        value={secretProps.displayValue}
        onChange={secretProps.handleChange}
        onFocus={secretProps.handleFocus}
        className={`bg-background-dark ${hasFieldError ? 'border-red-500' : ''}`}
        placeholder={fieldSchema.description}
        readOnly={!!populateHint}
        disabled={!!populateHint}
      />
    )}

    {validationHint && (
      <FieldValidation
        fieldName={fieldName}
        fieldValue={value}
        validationHint={validationHint}
        elementActions={elementActions}
        selectedElementType={elementType}
        onValidationChange={onValidationChange}
      />
    )}
    {populateHint && (
      <FieldPopulation
        fieldName={fieldName}
        populateHint={populateHint}
        elementActions={elementActions}
        selectedElementType={elementType}
        formData={formData}
        onPopulateResult={onPopulateResult}
        hideUI={populateHint.selection_type == 'automatic'}
        autoTrigger={areDependenciesValid}
        currentValue={value}
      />
    )}
    {/* Agent Card Visualization */}
    {fieldName === "agent_card" && (
      <AgentCardVisualization agentCard={value} />
    )}
  </div>
);
};
