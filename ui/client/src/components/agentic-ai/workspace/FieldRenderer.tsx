import React, { useState, useEffect, useRef, useCallback } from "react";
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldValidation, ItemValidationResult } from "./FieldValidation";
import { FieldPopulation } from "./FieldPopulation";
import { AuthFieldRenderer } from "./AuthFieldRenderer";
import { AgentCardVisualization } from "./AgentCardVisualization";
import { FileUpload } from "@/components/ui/file-upload";
import { ElementType } from "../../../types/workspace";
import { maskSecretValue } from "../../../utils/maskSecretFields";
import { XCircle, Lock, Settings } from "lucide-react";
import {getArrayDisplayText, getArrayFieldMode, getValidRefOptions,} from "./arrayFieldHelpers";
import { getStringEnumFromRef } from "@/lib/schemaRefs";

/** Builds the dropdown label for a ref option, flagging drafts so users can
 * see (and not select) built-ins that aren't published yet. */
const getRefOptionLabel = (option: any): string =>
  `${option.name} (${option.type})${option.visibility === "draft" ? " (Draft)" : ""}`;

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
  itemValidationStates?: { [fieldName: string]: ItemValidationResult[] };
  actionOutputs?: Record<string, any>;
  isArrayWithRefItems: (fieldSchema: any) => boolean;
  getArrayItemsSchema: (fieldSchema: any) => any;
  extractCategoryFromField: (fieldSchema: any) => string | null;
  resolveSchemaRef?: (ref: string) => any | null;
  onInputChange: (field: string, value: any) => void;
  onArrayChange?: (field: string, index: number, value: any) => void;
  onAddArrayItem?: (field: string) => void;
  onRemoveArrayItem?: (field: string, index: number) => void;
  onValidationChange: (fieldName: string, isValid: boolean, itemResults?: ItemValidationResult[]) => void;
  onPopulateResult: (fieldName: string, results: string[] | any, multiSelect: boolean) => void;
  onActionOutput?: (fieldName: string, output: any) => void;
  onEditRefElement?: (rid: string) => void;
  /** Optional badge rendered inline with the field label. */
  labelBadge?: React.ReactNode;
}

// Controlled number input with local state buffer to handle intermediate typing (e.g., "0.")
interface NumberFieldInputProps {
  fieldName: string;
  value: number | null;
  isFloatField: boolean;
  hasFieldError: boolean;
  placeholder?: string;
  isReadOnly?: boolean;
  onChange: (value: number | null) => void;
}

const NumberFieldInput: React.FC<NumberFieldInputProps> = ({
  fieldName,
  value,
  isFloatField,
  hasFieldError,
  placeholder,
  isReadOnly,
  onChange,
}) => {
  // Local string buffer to preserve intermediate typing states like "0." or "-"
  const [localNumStr, setLocalNumStr] = useState<string>(
    value != null ? String(value) : ""
  );

  // Sync from parent when value changes externally (e.g., clear, populate, reset)
  useEffect(() => {
    const incoming = value != null ? String(value) : "";
    setLocalNumStr((prev) => {
      // Don't overwrite if user is mid-edit with the same numeric value
      // e.g., user typed "0." which parent sees as 0, don't replace "0." with "0"
      if (prev === "") {
        return incoming;
      }
      const parsed = parseFloat(prev);
      if (!isNaN(parsed) && parsed === value) {
        return prev; // Same numeric value, keep user's string representation
      }
      return incoming;
    });
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const strValue = e.target.value;
    
    // For integer fields, reject any input containing a decimal point
    if (!isFloatField && strValue.includes('.')) {
      return; // Don't update - reject decimal input for integers
    }
    
    setLocalNumStr(strValue);
    
    // Parse and notify parent
    if (strValue === "") {
      onChange(null);
    } else {
      const numValue = isFloatField
        ? parseFloat(strValue)
        : parseInt(strValue, 10);
      onChange(isNaN(numValue) ? null : numValue);
    }
  };

  return (
    <Input
      id={fieldName}
      type="number"
      step={isFloatField ? "any" : "1"}
      value={localNumStr}
      onChange={handleChange}
      className={`bg-background-dark ${hasFieldError ? 'border-red-500' : ''}`}
      placeholder={placeholder}
      readOnly={isReadOnly}
      disabled={isReadOnly}
    />
  );
};

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
  itemValidationStates,
  actionOutputs,
  isArrayWithRefItems,
  getArrayItemsSchema,
  extractCategoryFromField,
  resolveSchemaRef,
  onInputChange,
  onArrayChange,
  onAddArrayItem,
  onRemoveArrayItem,
  onValidationChange,
  onPopulateResult,
  onActionOutput,
  onEditRefElement,
  labelBadge,
}) => {
  // Check if this field has validation errors based on validation action result
  // Use useMemo to recalculate when fieldValidationStates changes after validation action
  // For non-required fields with no value, don't show error
  const hasFieldError = React.useMemo(() => {
    if (!validationHint || fieldValidationStates?.[fieldName] !== false) {
      return false;
    }
    // If field is not required and has no value, don't show error
    const hasValue = value !== undefined && value !== null && value !== '' && 
      !(Array.isArray(value) && value.length === 0);
    if (!isRequired && !hasValue) {
      return false;
    }
    return true;
  }, [validationHint, fieldValidationStates, fieldName, value, isRequired]);

  // Helper function to check if a specific item in a list field is invalid
  const isItemInvalid = React.useCallback((rid: string): boolean => {
    const itemResults = itemValidationStates?.[fieldName];
    if (!itemResults) return false;
    const itemResult = itemResults.find(item => item.rid === rid);
    return itemResult ? !itemResult.isValid : false;
  }, [itemValidationStates, fieldName]);

  const [showMasked, setShowMasked] = useState(true);
  const isSecret = fieldType === "secret";
  const isReadOnly = fieldSchema?.hints?.read_only?.read_only === true;

  // Object-field JSON textarea: buffers the raw (possibly invalid) text so a
  // mid-edit parse failure doesn't corrupt `formData` with a plain string in
  // place of the expected object, while still surfacing the error inline.
  const [objectFieldRawText, setObjectFieldRawText] = useState<string | null>(null);
  const [objectParseError, setObjectParseError] = useState<string | null>(null);

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

  // Check if this is an array-like field (direct type or anyOf containing array)
  const isArrayField = fieldSchema.type === "array" ||
    (fieldSchema.anyOf && fieldSchema.anyOf.some((opt: any) => opt.type === "array"));

  // Handle all array fields in a unified block
  if (isArrayField) {
    // Determine array mode and gather mode-specific data
    const arrayMode = getArrayFieldMode(
      isArrayWithRefItems(fieldSchema),
      !!populateHint,
      fieldSchema.type === "array"
    );

    if (!arrayMode) return null;

    const category = arrayMode === 'refItems' ? extractCategoryFromField(fieldSchema) : null;
    const validOptions = arrayMode === 'refItems' ? getValidRefOptions(refOptions, category) : [];
    const displayFieldPath = populateHint?.display_field || populateHint?.label_field;
    const displayName = populateHint?.display_name || fieldName;

    // Early return for missing category in refItems mode
    if (arrayMode === 'refItems' && !category) {
      console.warn(`No category found for array field ${fieldName}`);
      return null;
    }

    // Early return for missing handlers in regular mode
    if (arrayMode === 'regular' && (!onArrayChange || !onAddArrayItem || !onRemoveArrayItem)) {
      console.warn("Array handlers not provided for array field", fieldName);
      return null;
    }

    // Render content based on mode
    const renderArrayContent = () => {
      switch (arrayMode) {
        case 'refItems':
          return (
            <>
              <div className="space-y-2">
                <Select
                  value=""
                  onValueChange={(newValue) => {
                    if (isReadOnly) return;
                    if (newValue && newValue !== "__no_options_disabled__") {
                      const currentArray = formData[fieldName] || [];
                      if (!currentArray.includes(newValue)) {
                        onInputChange(fieldName, [...currentArray, newValue]);
                      }
                    }
                  }}
                  disabled={isReadOnly}
                >
                  <SelectTrigger className={`bg-background-dark ${hasFieldError ? 'border-red-500' : ''}`}>
                    <SelectValue placeholder={`Add ${category}`} />
                  </SelectTrigger>
                  <SelectContent>
                    {validOptions.map((option: any) => (
                      <SelectItem
                        key={option.rid}
                        value={option.rid}
                        disabled={option.visibility === "draft"}
                      >
                        {getRefOptionLabel(option)}
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
                      const itemInvalid = isItemInvalid(selectedRid);
                      return (
                        <Badge
                          key={index}
                          variant="secondary"
                          className={`flex items-center gap-1 ${itemInvalid ? 'border-red-500 border' : ''}`}
                        >
                          {itemInvalid && <XCircle className="h-3 w-3 text-red-500" />}
                          {selectedOption
                            ? `${selectedOption.name} (${selectedOption.type})`
                            : selectedRid}
                          {onEditRefElement && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onEditRefElement(selectedRid);
                              }}
                              className="ml-1 hover:text-primary"
                              title="Configure this element"
                            >
                              <Settings className="h-3 w-3" />
                            </button>
                          )}
                          {!isReadOnly && (
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
                          )}
                        </Badge>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          );

        case 'dynamic':
          return (
            <Textarea
              id={fieldName}
              value={getArrayDisplayText(value, displayFieldPath)}
              readOnly
              disabled
              rows={1}
              className="bg-background-dark resize-none"
              placeholder={fieldSchema.description || `Selected ${fieldName} will appear here...`}
            />
          );

        case 'regular':
          return (
            <div className="space-y-2">
              {(value || []).map((item: any, index: number) => (
                <div key={index} className="flex gap-2">
                  <Input
                    value={typeof item === 'object' ? JSON.stringify(item) : item}
                    onChange={(e) => onArrayChange!(fieldName, index, e.target.value)}
                    className={`bg-background-dark flex-1 ${hasFieldError ? 'border-red-500' : ''}`}
                    placeholder={`${fieldName} item ${index + 1}`}
                    readOnly={isReadOnly}
                    disabled={isReadOnly}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onRemoveArrayItem!(fieldName, index)}
                    disabled={isReadOnly}
                  >
                    Remove
                  </Button>
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onAddArrayItem!(fieldName)}
                disabled={isReadOnly}
              >
                Add {fieldName}
              </Button>
            </div>
          );
      }
    };

    return (
      <div key={fieldName} className={`space-y-2 ${isReadOnly ? "opacity-60" : ""}`}>
        {/* Label with badges */}
        <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
          {displayName} {isRequired && <span className="text-red-400">*</span>}
          {labelBadge}
          {arrayMode === 'refItems' && category && (
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
          {isReadOnly && <Lock className="h-3.5 w-3.5 text-gray-500 ml-1" />}
          {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
        </Label>

        {/* Description */}
        {fieldSchema.description && (
          <p className="text-xs text-gray-400">{fieldSchema.description}</p>
        )}

        {/* Mode-specific content */}
        {renderArrayContent()}

        {/* Validation */}
        {validationHint && (
          <FieldValidation
            fieldName={fieldName}
            fieldValue={value}
            validationHint={validationHint}
            elementActions={elementActions}
            selectedElementType={elementType}
            isRequired={isRequired}
            configValues={formData}
            actionOutputs={actionOutputs}
            onValidationChange={onValidationChange}
            onInputChange={onInputChange}
          />
        )}

        {/* Population - rendered once for all modes that need it */}
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

  // Handle string enum fields (from $ref to $defs with type: "string" and enum)
  const stringEnumDef = getStringEnumFromRef(fieldSchema, resolveSchemaRef);
  
  if (stringEnumDef) {
    const enumOptions = stringEnumDef.enum;
    const enumTitle = stringEnumDef.title;

    return (
      <div key={fieldName} className={`space-y-2 ${isReadOnly ? "opacity-60" : ""}`}>
        <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {labelBadge}
          {enumTitle && (
            <Badge variant="outline" className="ml-2 text-xs">
              {enumTitle}
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
          {isReadOnly && <Lock className="h-3.5 w-3.5 text-gray-500 ml-1" />}
          {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
        </Label>
        
        {fieldSchema.description && (
          <p className="text-xs text-gray-400">{fieldSchema.description}</p>
        )}

        <RadioGroup
          value={value || ""}
          onValueChange={(newValue) => {
            onInputChange(fieldName, newValue);
          }}
          disabled={isReadOnly}
          className={`flex flex-wrap gap-4 ${hasFieldError ? 'border border-red-500 rounded-md p-2' : ''} ${isReadOnly ? 'pointer-events-none' : ''}`}
        >
          {enumOptions.map((option: string) => (
            <div key={option} className="flex items-center space-x-2">
              <RadioGroupItem value={option} id={`${fieldName}-${option}`} />
              <Label
                htmlFor={`${fieldName}-${option}`}
                className="font-normal cursor-pointer"
              >
                {option}
              </Label>
            </div>
          ))}
        </RadioGroup>

        {/* Validation component for string enum fields */}
        {validationHint && (
          <FieldValidation
            fieldName={fieldName}
            fieldValue={value}
            validationHint={validationHint}
            elementActions={elementActions}
            selectedElementType={elementType}
            isRequired={isRequired}
            configValues={formData}
            actionOutputs={actionOutputs}
            onValidationChange={onValidationChange}
            onInputChange={onInputChange}
          />
        )}

        {/* Population component for string enum fields */}
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

  // Handle fields with AuthHint — render as Sign In / auth status component
  if (fieldSchema?.hints?.auth) {
    return (
      <AuthFieldRenderer
        fieldName={fieldName}
        fieldSchema={fieldSchema}
        formData={formData}
        elementActions={elementActions}
        onValidationChange={onValidationChange}
        onInputChange={onInputChange}
        onActionOutput={onActionOutput}
      />
    );
  }

  // Handle fields with file_upload hint — render file picker
  const fileUploadHint = fieldSchema?.hints?.file_upload;
  if (fileUploadHint) {
    return (
      <div key={fieldName} className={`space-y-2 ${isReadOnly ? "opacity-60" : ""}`}>
        <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {labelBadge}
          {isReadOnly && <Lock className="h-3.5 w-3.5 text-gray-500 ml-1" />}
          {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
        </Label>
        {fieldSchema.description && (
          <p className="text-xs text-gray-400">{fieldSchema.description}</p>
        )}
        <FileUpload
          accept={fileUploadHint.accept || ".pem,.crt,.key"}
          formatType={fileUploadHint.validate_format || "pem"}
          maxSizeBytes={fileUploadHint.max_size_bytes || 16384}
          value={value}
          hasError={hasFieldError}
          disabled={isReadOnly}
          onUploadSuccess={(content, filename) => onInputChange(fieldName, content)}
          onClear={() => onInputChange(fieldName, "")}
        />
        {validationHint && (
          <FieldValidation
            fieldName={fieldName}
            fieldValue={value}
            validationHint={validationHint}
            elementActions={elementActions}
            selectedElementType={elementType}
            isRequired={isRequired}
            configValues={formData}
            onValidationChange={onValidationChange}
            onInputChange={onInputChange}
          />
        )}
      </div>
    );
  }

  // Handle auth category fields with dedicated AuthSelector component
  if (fieldSchema.category === 'auths') {
    const authOptions = (refOptions['auths'] || [])
      .filter((option: any) => option.rid && option.rid.trim() !== "");

    const authActionUid = validationHint?.action_uid || fieldSchema.action_uid || 'auth.authenticate';

    return (
      <AuthSelector
        fieldName={fieldName}
        value={value}
        refOptions={authOptions}
        actionUid={authActionUid}
        onInputChange={onInputChange}
        isRequired={isRequired}
        description={fieldSchema.description}
      />
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
      const validOptions = (refOptions[category] || [])
        .filter((option: any) => option.rid && option.rid.trim() !== "")
        .sort((a: any, b: any) => (a.name || "").localeCompare(b.name || ""));

      return (
        <div key={fieldName} className={`space-y-2 ${isReadOnly ? "opacity-60" : ""}`}>
          <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
            {fieldName} {isRequired && <span className="text-red-400">*</span>}
            {labelBadge}
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
            {isReadOnly && <Lock className="h-3.5 w-3.5 text-gray-500 ml-1" />}
            {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
          </Label>
          
          {fieldSchema.description && (
            <p className="text-xs text-gray-400">{fieldSchema.description}</p>
          )}

          <div className="flex gap-2">
            <Select
              key={value || 'empty'}
              value={value || undefined}
              onValueChange={(newValue) => {
                if (!isReadOnly) onInputChange(fieldName, newValue);
              }}
              disabled={isReadOnly}
            >
              <SelectTrigger className={`bg-background-dark flex-1 ${hasFieldError ? 'border-red-500' : ''}`}>
                <SelectValue placeholder={`Select ${fieldName}`} />
              </SelectTrigger>
              <SelectContent>
                {validOptions.map((option: any) => (
                  <SelectItem
                    key={option.rid}
                    value={option.rid}
                    disabled={option.visibility === "draft"}
                  >
                    {getRefOptionLabel(option)}
                  </SelectItem>
                ))}
                {validOptions.length === 0 && (
                  <SelectItem value="__no_options_disabled__" disabled>
                    No {category} resources available
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
            {value && onEditRefElement && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-10 w-10 shrink-0"
                onClick={() => onEditRefElement(value)}
                title="Configure this element"
              >
                <Settings className="h-4 w-4 text-muted-foreground hover:text-primary" />
              </Button>
            )}
            {!isRequired && value && !isReadOnly && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-10 w-10 shrink-0"
                onClick={() => onInputChange(fieldName, null)}
              >
                <XCircle className="h-4 w-4 text-muted-foreground hover:text-red-400" />
              </Button>
            )}
          </div>

          {/* Validation component for $ref fields */}
          {validationHint && (
            <FieldValidation
              fieldName={fieldName}
              fieldValue={value}
              validationHint={validationHint}
              elementActions={elementActions}
              selectedElementType={elementType}
              isRequired={isRequired}
              configValues={formData}
              actionOutputs={actionOutputs}
              onValidationChange={onValidationChange}
              onInputChange={onInputChange}
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
    const isEmptyObject = typeof value === "object" && value !== null && Object.keys(value).length === 0;
    const displayValue = objectFieldRawText !== null
      ? objectFieldRawText
      : isEmptyObject
      ? ""
      : typeof value === "object" ? JSON.stringify(value, null, 2) : value;

    return (
      <div key={fieldName} className={`space-y-2 ${isReadOnly ? "opacity-60" : ""}`}>
        <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {labelBadge}
          {isReadOnly && <Lock className="h-3.5 w-3.5 text-gray-500 ml-1" />}
          {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
        </Label>
        <Textarea
          id={fieldName}
          value={displayValue}
          onChange={(e) => {
            if (isReadOnly) return;
            const text = e.target.value;
            if (text.trim() === "") {
              setObjectFieldRawText(null);
              setObjectParseError(null);
              onValidationChange(fieldName, true);
              onInputChange(fieldName, {});
              return;
            }
            let parsed: unknown;
            try {
              parsed = JSON.parse(text);
            } catch (error) {
              // Keep the raw text in local state only — don't propagate
              // invalid JSON to `formData`, which expects an object here.
              setObjectFieldRawText(text);
              setObjectParseError("Invalid JSON — fix it before this field can be saved.");
              onValidationChange(fieldName, false);
              return;
            }
            if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
              // Valid JSON but not an object (array, string, number, boolean,
              // null) — reject the same way as a parse failure so formData
              // never ends up holding a value of the wrong type.
              setObjectFieldRawText(text);
              setObjectParseError("Value must be a JSON object (not an array or primitive).");
              onValidationChange(fieldName, false);
              return;
            }
            setObjectFieldRawText(null);
            setObjectParseError(null);
            onValidationChange(fieldName, true);
            onInputChange(fieldName, parsed);
          }}
          rows={6}
          readOnly={isReadOnly}
          disabled={isReadOnly}
          className={`bg-background-dark resize-none font-mono text-sm ${hasFieldError || objectParseError ? 'border-red-500' : ''}`}
          placeholder="Enter JSON object (e.g., {})"
        />
        {objectParseError && (
          <p className="text-xs text-red-400">{objectParseError}</p>
        )}
        {fieldSchema.description && (
          <p className="text-xs text-gray-400">{fieldSchema.description}</p>
        )}
      </div>
    );
  }


  // Handle boolean fields
  if (fieldSchema.type === "boolean") {
    return (
      <div key={fieldName} className={`space-y-2 ${isReadOnly ? "opacity-60" : ""}`}>
        <div className={`flex items-center space-x-2 ${isReadOnly ? "pointer-events-none" : ""}`}>
          <Checkbox
            id={fieldName}
            checked={value}
            onCheckedChange={(checked) => onInputChange(fieldName, checked)}
            className={hasFieldError ? 'border-red-500' : ''}
            disabled={isReadOnly}
          />
          <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
            {fieldName}{" "}
            {isRequired && <span className="text-red-400">*</span>}
            {labelBadge}
            {isReadOnly && <Lock className="h-3.5 w-3.5 text-gray-500 ml-1" />}
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

  // Determine if the field should accept float values (step="any") or only integers (step="1")
  const isFloatField =
    fieldSchema.type === "number" ||
    (fieldSchema.anyOf &&
      fieldSchema.anyOf.some((option: any) => option.type === "number"));

  if (isNumberField) {
    return (
      <div key={fieldName} className={`space-y-2 ${isReadOnly ? "opacity-60" : ""}`}>
        <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {labelBadge}
          {isFloatField && (
            <Badge variant="outline" className="ml-2 text-xs">
              float
            </Badge>
          )}
          {isReadOnly && <Lock className="h-3.5 w-3.5 text-gray-500 ml-1" />}
          {hasFieldError && <XCircle className="h-4 w-4 text-red-500 inline-block ml-2" />}
        </Label>
        <NumberFieldInput
          key={`${fieldName}-${editingElement?.rid || 'new'}`}
          fieldName={fieldName}
          value={value}
          isFloatField={isFloatField}
          hasFieldError={hasFieldError}
          placeholder={fieldSchema.description}
          isReadOnly={isReadOnly}
          onChange={(numValue) => onInputChange(fieldName, numValue)}
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
      <div key={fieldName} className={`space-y-2 ${isReadOnly ? "opacity-60" : ""}`}>
        <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
          {fieldName} {isRequired && <span className="text-red-400">*</span>}
          {labelBadge}
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
        {isReadOnly && <Lock className="h-3.5 w-3.5 text-gray-500 ml-1" />}
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
          readOnly={isReadOnly || !!populateHint}
          disabled={isReadOnly || !!populateHint}
        />
      )}

      {validationHint && (
        <FieldValidation
          fieldName={fieldName}
          fieldValue={value}
          validationHint={validationHint}
          elementActions={elementActions}
          selectedElementType={elementType}
          isRequired={isRequired}
          configValues={formData}
          actionOutputs={actionOutputs}
          onValidationChange={onValidationChange}
          onInputChange={onInputChange}
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
    <div key={fieldName} className={`space-y-2 ${isReadOnly ? "opacity-60" : ""}`}>
      <Label htmlFor={fieldName} className="flex items-center flex-wrap gap-1">
        {fieldName} {isRequired && <span className="text-red-400">*</span>}
        {labelBadge}
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
      {isReadOnly && <Lock className="h-3.5 w-3.5 text-gray-500 ml-1" />}
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
        readOnly={isReadOnly || !!populateHint}
        disabled={isReadOnly || !!populateHint}
      />
    )}

    {validationHint && (
      <FieldValidation
        fieldName={fieldName}
        fieldValue={value}
        validationHint={validationHint}
        elementActions={elementActions}
        selectedElementType={elementType}
        isRequired={isRequired}
        configValues={formData}
        actionOutputs={actionOutputs}
        onValidationChange={onValidationChange}
        onInputChange={onInputChange}
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
