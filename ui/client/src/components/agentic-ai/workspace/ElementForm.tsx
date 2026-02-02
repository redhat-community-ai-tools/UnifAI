import React, { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { Button } from "@/components/ui/button";
import {
  ElementType,
  ElementSchema,
  ElementInstance,
} from "../../../types/workspace";
import { FieldRenderer } from "./FieldRenderer";
import { ItemValidationResult } from "./FieldValidation";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';

interface ElementFormProps {
  isOpen: boolean;
  onClose: () => void;
  elementType: ElementType;
  elementSchema: ElementSchema;
  elementActions?: any[];
  editingElement: ElementInstance | null;
  onSave: (data: any) => Promise<void>;
}

export const ElementForm: React.FC<ElementFormProps> = ({
  isOpen,
  onClose,
  elementType,
  elementSchema,
  elementActions = [],
  editingElement,
  onSave,
}) => {
  const [formData, setFormData] = useState<any>({});
  const [isSaving, setIsSaving] = useState(false);
  const [refOptions, setRefOptions] = useState<{ [category: string]: any[] }>(
    {},
  );
  const [fieldValidationStates, setFieldValidationStates] = useState<{ [fieldName: string]: boolean }>({});
  const [itemValidationStates, setItemValidationStates] = useState<{ [fieldName: string]: ItemValidationResult[] }>({});
  const [validatingFields, setValidatingFields] = useState<Set<string>>(new Set());
  const [populateResults, setPopulateResults] = useState<{ [fieldName: string]: string[] | any }>({});

  const { fetchResourcesForCategory } = useWorkspaceData();

  // Helper to check if a field has validation hint
  const fieldHasValidation = useCallback((fieldName: string): boolean => {
    const fieldSchema = elementSchema?.config_schema.properties[fieldName];
    if (!fieldSchema) return false;
    return fieldSchema.hints?.action?.hint_type === 'validate' || 
           fieldSchema.hints?.api?.hint_type === 'validate';
  }, [elementSchema]);

  const handleValidationChange = (fieldName: string, isValid: boolean, itemResults?: ItemValidationResult[]) => {
    setFieldValidationStates(prev => ({
      ...prev,
      [fieldName]: isValid
    }));
    // Store per-item validation results if provided (for list fields)
    if (itemResults) {
      setItemValidationStates(prev => ({
        ...prev,
        [fieldName]: itemResults
      }));
    }
    // Remove from validating set when validation completes
    setValidatingFields(prev => {
      const next = new Set(prev);
      next.delete(fieldName);
      return next;
    });
  };

  const handlePopulateResult = (fieldName: string, results: any[], multiSelect: boolean) => {
    setPopulateResults(prev => ({
      ...prev,
      [fieldName]: results
    }));
    
    // For multi-select fields, store the full array of objects (or strings)
    // For single select, store just the first item (can be object or string)
    if (multiSelect) {
      // Multi-select: always store as array
      handleInputChange(fieldName, results);
    } else {
      // Single select: store single item (first in array, or empty string)
      const singleResult = results.length > 0 ? results[0] : "";
      handleInputChange(fieldName, singleResult);
    }
  };


  // Initialize form data
  useEffect(() => {
    if (elementSchema && isOpen) {
      const initialData: any = {};
      const fieldsToValidate = new Set<string>();

      // Set default values from combined schema, excluding hidden fields
      Object.entries(elementSchema.config_schema.properties).forEach(
        ([key, property]: [string, any]) => {
          // Skip hidden fields - don't initialize them
          if (property?.hints?.hidden?.hint_type === "hidden") {
            return;
          }
          
          if (property.default !== undefined) {
            initialData[key] = property.default;
          } else if (property.type === "array") {
            initialData[key] = [];
          } else if (property.type === "boolean") {
            initialData[key] = false;
          } else if (property.type === "object") {
            initialData[key] = {};
          } else {
            initialData[key] = "";
          }
        },
      );

      // If editing, populate with existing data (override defaults)
      if (editingElement) {
        // Handle first-level fields directly from editingElement
        // Only handle 'name' field explicitly to avoid TypeScript indexing errors
        if (editingElement.name !== undefined) {
          initialData.name = editingElement.name;
        }

        // Handle config data, excluding hidden fields
        if (editingElement.config) {
          Object.entries(editingElement.config).forEach(([key, value]) => {
            const fieldSchema = elementSchema.config_schema.properties[key];
            
            // Skip hidden fields - don't populate them in edit mode
            if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
              return;
            }
            
            // Handle $ref values - extract the rid from $ref:rid format
            // Note: Secret fields are handled like normal fields - FieldRenderer handles masking for display
            if (typeof value === "string" && value.startsWith("$ref:")) {
              initialData[key] = value.substring(5); // Remove '$ref:' prefix
            } else if (Array.isArray(value)) {
              // Handle array of $ref values
              initialData[key] = value.map((item: any) =>
                typeof item === "string" && item.startsWith("$ref:")
                  ? item.substring(5)
                  : item,
              );
            } else {
              initialData[key] = value;
            }

            // Track fields with validation hints that have values - these will trigger validation
            // and Save button should be disabled until validation completes
            const hasValidationHint = fieldSchema?.hints?.action?.hint_type === 'validate' || 
                                      fieldSchema?.hints?.api?.hint_type === 'validate';
            if (hasValidationHint) {
              const processedValue = initialData[key];
              const hasValue = Array.isArray(processedValue) 
                ? processedValue.length > 0 
                : processedValue !== undefined && processedValue !== null && processedValue !== '';
              if (hasValue) {
                fieldsToValidate.add(key);
              }
            }
          });
        }
      }

      setFormData(initialData);
      
      // In edit mode, mark fields with validation hints and values as "validating"
      // This ensures Save button is disabled until all validation API calls complete
      if (editingElement && fieldsToValidate.size > 0) {
        setValidatingFields(fieldsToValidate);
      }
    }
  }, [elementSchema, editingElement, isOpen]);

  // Re-apply form data when ref options are loaded (for proper pre-selection)
  useEffect(() => {
    if (editingElement?.config && Object.keys(refOptions).length > 0) {
      setFormData((prevData: any) => {
        const updatedData = { ...prevData };

        Object.entries(editingElement.config).forEach(([key, value]) => {
          const fieldSchema = elementSchema?.config_schema.properties[key];
          
          // Skip hidden fields - don't re-apply them
          if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
            return;
          }
          
          if (typeof value === "string" && value.startsWith("$ref:")) {
            const rid = value.substring(5);
            updatedData[key] = rid;
          } else if (Array.isArray(value)) {
            // Handle array of $ref values
            updatedData[key] = value.map((item: any) =>
              typeof item === "string" && item.startsWith("$ref:")
                ? item.substring(5)
                : item,
            );
          }
        });

        return updatedData;
      });
    }
  }, [refOptions, editingElement]);

  // Helper function to check if a field is an array with $ref items
  const isArrayWithRefItems = (fieldSchema: any) => {
    // Direct array type
    if (
      fieldSchema.type === "array" &&
      fieldSchema.items &&
      fieldSchema.items.$ref
    ) {
      return true;
    }
    // anyOf structure (like tools field)
    if (fieldSchema.anyOf && Array.isArray(fieldSchema.anyOf)) {
      return fieldSchema.anyOf.some(
        (option: any) =>
          option.type === "array" && option.items && option.items.$ref,
      );
    }
    return false;
  };

  // Helper function to get array items schema from anyOf or direct structure
  const getArrayItemsSchema = (fieldSchema: any) => {
    if (fieldSchema.type === "array" && fieldSchema.items) {
      return fieldSchema.items;
    }
    if (fieldSchema.anyOf && Array.isArray(fieldSchema.anyOf)) {
      const arrayOption = fieldSchema.anyOf.find(
        (option: any) => option.type === "array" && option.items,
      );
      return arrayOption?.items;
    }
    return null;
  };

  // Helper function to parse JSON path from reference string
  const parseJsonPath = (ref: string): string[] | null => {
    if (!ref || typeof ref !== 'string' || !ref.startsWith('#/')) {
      return null;
    }

    // Remove the '#/' prefix and split by '/'
    const pathString = ref.substring(2);
    if (!pathString) {
      return null;
    }

    return pathString.split('/').filter(segment => segment.length > 0);
  };

  // Generic helper function to resolve JSON path in an object
  const resolveJsonPath = (obj: any, pathSegments: string[]): any | null => {
    if (!obj || !pathSegments || pathSegments.length === 0) {
      return null;
    }

    let current = obj;
    for (const segment of pathSegments) {
      if (!current || typeof current !== 'object' || !(segment in current)) {
        return null;
      }
      current = current[segment];
    }

    return current;
  };

  // Helper function to find definition in schema by reference path
  const findDefinitionByRef = (ref: string): any | null => {
    const pathSegments = parseJsonPath(ref);
    if (!pathSegments || !elementSchema?.config_schema) {
      return null;
    }

    return resolveJsonPath(elementSchema.config_schema, pathSegments);
  };

  // Helper function to resolve $ref to actual definition with full details
  const resolveRef = (ref: string): any | null => {
    const definition = findDefinitionByRef(ref);
    if (definition) {
      console.log(`Resolved $ref ${ref} to:`, definition);
      return definition;
    }

    console.warn(`Could not resolve $ref: ${ref}`);
    return null;
  };

  // Helper function to extract category from resolved definition
  const extractCategoryFromDefinition = (definition: any): string | null => {
    if (!definition || typeof definition !== 'object') {
      return null;
    }

    // Direct category property
    if (definition.category && typeof definition.category === 'string') {
      return definition.category;
    }

    return null;
  };

  // Helper function to extract category from $ref field or anyOf structure
  const extractCategoryFromField = (fieldSchema: any): string | null => {
    // Handle direct $ref by resolving it
    if (fieldSchema.$ref) {
      const resolved = resolveRef(fieldSchema.$ref);
      const category = extractCategoryFromDefinition(resolved);
      if (category) {
        return category;
      }
    }

    // Handle items with $ref (for arrays)
    if (fieldSchema.items && fieldSchema.items.$ref) {
      const resolved = resolveRef(fieldSchema.items.$ref);
      const category = extractCategoryFromDefinition(resolved);
      if (category) {
        return category;
      }
    }

    // Category from anyOf structure
    if (fieldSchema.anyOf && Array.isArray(fieldSchema.anyOf)) {
      // Check for direct $ref in anyOf
      for (const option of fieldSchema.anyOf) {
        if (option.$ref) {
          const resolved = resolveRef(option.$ref);
          const category = extractCategoryFromDefinition(resolved);
          if (category) {
            return category;
          }
        }

        // Check for array with $ref items in anyOf
        if (option.type === "array" && option.items && option.items.$ref) {
          const resolved = resolveRef(option.items.$ref);
          const category = extractCategoryFromDefinition(resolved);
          if (category) {
            return category;
          }
        }
      }
    }
    return null; // Return null if no category is found
  };

  // Load reference options for $ref fields
  useEffect(() => {
    if (elementSchema && isOpen) {
      const refFields = Object.entries(
        elementSchema.config_schema.properties,
      ).filter(
        ([, property]: [string, any]) =>
          property.$ref ||
          (property.items && property.items.$ref) ||
          (property.type === "array" &&
            property.items &&
            property.items.$ref) ||
          isArrayWithRefItems(property) ||
          (property.anyOf && property.anyOf.some((option: any) => option.$ref)),
      );

      const refCategories = new Set<string>();
      refFields.forEach(([, property]: [string, any]) => {
        const category = extractCategoryFromField(property);
        if (category) {
          refCategories.add(category);
        }
      });

      // Fetch actual reference options from Resources API
      const loadRefOptions = async () => {
        const options: { [category: string]: any[] } = {};

        for (const category of Array.from(refCategories)) {
          try {
            const resources = await fetchResourcesForCategory(category);
            options[category] = resources;
          } catch (error) {
            console.error(
              `Failed to load resources for category ${category}:`,
              error,
            );
            options[category] = [];
          }
        }

        setRefOptions(options);
      };

      if (refCategories.size > 0) {
        loadRefOptions();
      }
    }
  }, [elementSchema, isOpen, fetchResourcesForCategory]);

  const handleInputChange = (field: string, value: any) => {
    setFormData((prev: any) => ({
      ...prev,
      [field]: value,
    }));
    // If field has validation hint, mark it as validating immediately
    // This prevents the save button from being enabled during the validation delay
    if (fieldHasValidation(field)) {
      setValidatingFields(prev => new Set(prev).add(field));
    }
  };

  const handleArrayChange = (field: string, index: number, value: any) => {
    setFormData((prev: any) => ({
      ...prev,
      [field]: prev[field].map((item: any, i: number) =>
        i === index ? value : item,
      ),
    }));
  };

  const addArrayItem = (field: string) => {
    setFormData((prev: any) => ({
      ...prev,
      [field]: [...(prev[field] || []), ""],
    }));
  };

  const removeArrayItem = (field: string, index: number) => {
    setFormData((prev: any) => ({
      ...prev,
      [field]: prev[field].filter((_: any, i: number) => i !== index),
    }));
  };

  // Check if all required fields are filled and validated
  const isFormValid = () => {
    if (!elementSchema) return false;

    // If any field is currently being validated, form is not valid yet
    if (validatingFields.size > 0) return false;

    // Check all required fields from combined schema, excluding hidden fields
    const required = elementSchema.config_schema.required || [];
    const allRequiredFieldsValid = required.every((field) => {
      const fieldSchema = elementSchema.config_schema.properties[field];
      
      // Skip validation for hidden fields
      if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
        return true;
      }
      
      const value = formData[field];
      
      // Check if field has validation hint (supports both ActionHint and ApiHint)
      const hasValidationHint = fieldSchema?.hints?.action?.hint_type === 'validate' || 
                                fieldSchema?.hints?.api?.hint_type === 'validate';
      
      // Basic value validation
      let hasValue = false;
      if (Array.isArray(value)) {
        hasValue = value.length > 0;
      } else {
        hasValue = value !== undefined && value !== null && value !== "" && 
                  (typeof value !== "string" || value.trim() !== "");
      }
      
      // If field has validation hint and a value, check validation state
      if (hasValidationHint && hasValue) {
        return fieldValidationStates[field] === true;
      }
      
      // Otherwise, just check if value exists
      return hasValue;
    });

    // Additionally, check that no field validation has returned false
    // This handles both required and non-required fields with validation hints (ActionHint or ApiHint)
    const noFailedValidations = !Object.values(fieldValidationStates).some(isValid => isValid === false);

    return allRequiredFieldsValid && noFailedValidations;
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);

      // Validate all required fields from combined schema, excluding hidden fields
      const required = elementSchema.config_schema.required || [];
      const missing = required.filter((field) => {
        const fieldSchema = elementSchema.config_schema.properties[field];
        
        // Skip validation for hidden fields
        if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
          return false;
        }
        
        const value = formData[field];
        if (Array.isArray(value)) {
          return value.length === 0;
        }
        return !value || (typeof value === "string" && value.trim() === "");
      });

      if (missing.length > 0) {
        alert(`Please fill in required fields: ${missing.join(", ")}`);
        return;
      }

      // Prepare data for saving
      const saveData: any = {};
      const configForSave: any = {};

      // Separate first-level fields and config fields
      Object.entries(formData).forEach(([fieldName, value]) => {
        const fieldSchema = elementSchema.config_schema.properties[fieldName];

        // Skip hidden fields - don't include them in save payload
        if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
          return;
        }

        // Define which fields are first-level fields from resource schema
        const firstLevelResourceFields = ['name', 'category', 'type', 'cfg_dict', 'version', 'created', 'updated', 'nested_refs', 'rid', 'user_id'];

        // Only include 'name' as a first-level field for saving (exclude version and system fields)
        const isFirstLevelField = fieldName === 'name';

        // System fields that should never be included in save payload
        const systemFields = ['version', 'created', 'updated', 'nested_refs', 'rid', 'user_id', 'category', 'type', 'cfg_dict'];

        if (isFirstLevelField) {
          saveData[fieldName] = typeof value === "string" ? value.trim() : value;
        } else if (!systemFields.includes(fieldName)) {
          // This is a config field
          let processedValue = value;

          // Convert reference fields back to $ref:rid format and handle empty values
          if (fieldSchema) {
            // Handle non-ref objects as-is FIRST (before $ref processing)
            if (typeof value === "object" && value !== null && !Array.isArray(value)) {
              processedValue = value;
            }
            // Handle array fields with $ref items
            else if (isArrayWithRefItems(fieldSchema) && Array.isArray(value)) {
              processedValue = value.map((rid: string) => `$ref:${rid}`);
            }
            // Handle single $ref fields - only add $ref: prefix for string values (RIDs)
            else if (fieldSchema.$ref && typeof value === "string" && value !== "") {
              processedValue = `$ref:${value}`;
            }
            // Handle anyOf with $ref (single select) - only add $ref: prefix for string values (RIDs)
            else if (
              fieldSchema.anyOf &&
              fieldSchema.anyOf.some((option: any) => option.$ref) &&
              typeof value === "string" &&
              value !== ""
            ) {
              processedValue = `$ref:${value}`;
            }
            // Handle empty values based on field type
            else {
              // For array fields, ensure empty arrays instead of empty strings or null
              if (fieldSchema.type === "array" || 
                  (fieldSchema.anyOf && fieldSchema.anyOf.some((option: any) => option.type === "array"))) {
                if (!value || value === "" || (Array.isArray(value) && value.length === 0)) {
                  processedValue = [];
                } else if (Array.isArray(value)) {
                  processedValue = value;
                } else {
                  processedValue = [];
                }
              }
              // For string fields, ensure empty strings instead of null
              else if (fieldSchema.type === "string" || 
                       (fieldSchema.anyOf && fieldSchema.anyOf.some((option: any) => option.type === "string"))) {
                if (value === null || value === undefined) {
                  processedValue = "";
                } else {
                  processedValue = value;
                }
              }
              // For other types, keep the original value but handle null/undefined
              else {
                if (value === null || value === undefined) {
                  // Skip this field entirely for null/undefined values in non-string, non-array fields
                  return;
                }
                processedValue = value;
              }
            }
          }

          // Only include the field if it has a meaningful value or is required
          const isRequired = elementSchema.config_schema.required?.includes(fieldName);

          // Always include required fields, even if empty
          if (isRequired) {
            configForSave[fieldName] = processedValue;
          }
          // For non-required fields, only include if they have meaningful values
          else if (processedValue !== "" && processedValue !== null && processedValue !== undefined && 
                   !(Array.isArray(processedValue) && processedValue.length === 0)) {
            configForSave[fieldName] = processedValue;
          }
        }
      });

      // Add cfg_dict to save data
      saveData.cfg_dict = configForSave;

      const result = await onSave(saveData);

      // Only close the dialog if save was successful (result is not null/false)
      if (result !== null) {
        onClose();
      }
    } catch (error) {
      console.error("Error saving element:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const renderFormField = (fieldName: string, fieldSchema: any) => {
    const isRequired = elementSchema.config_schema.required?.includes(fieldName);
    const value = formData[fieldName] || "";
    
    // Check for validation hints - supports both ActionHint and ApiHint
    const actionValidationHint = fieldSchema.hints?.action?.hint_type === 'validate' ? fieldSchema.hints.action : null;
    const apiValidationHint = fieldSchema.hints?.api?.hint_type === 'validate' ? fieldSchema.hints.api : null;
    const validationHint = actionValidationHint || apiValidationHint;

    // Check for populate hints - supports both ActionHint and ApiHint
    const actionPopulateHint = fieldSchema.hints?.action?.hint_type === 'populate' ? fieldSchema.hints.action : null;
    const apiPopulateHint = fieldSchema.hints?.api?.hint_type === 'populate' ? fieldSchema.hints.api : null;
    const populateHint = actionPopulateHint || apiPopulateHint;
    
    const isSecret = fieldSchema?.hints?.secret?.hint_type === "secret";

    return (
      <FieldRenderer
        fieldName={fieldName}
        fieldSchema={fieldSchema}
        value={value}
        isRequired={isRequired}
        validationHint={validationHint}
        populateHint={populateHint}
        editingElement={editingElement}
        elementActions={elementActions}
        elementType={elementType}
        formData={formData}
        refOptions={refOptions}
        fieldType={isSecret ? "secret" : "public"}
        fieldValidationStates={fieldValidationStates}
        itemValidationStates={itemValidationStates}
        isArrayWithRefItems={isArrayWithRefItems}
        getArrayItemsSchema={getArrayItemsSchema}
        extractCategoryFromField={extractCategoryFromField}
        onInputChange={handleInputChange}
        onArrayChange={handleArrayChange}
        onAddArrayItem={addArrayItem}
        onRemoveArrayItem={removeArrayItem}
        onValidationChange={handleValidationChange}
        onPopulateResult={handlePopulateResult}
      />
    );
  };

  if (!elementSchema) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-background-card border-gray-800 text-foreground max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {editingElement ? "Edit" : "Create"} {elementType.name}
          </DialogTitle>
          <DialogDescription>{elementSchema.description}</DialogDescription>
        </DialogHeader>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSave();
          }}
          className="space-y-4"
        >
          {/* Render fields from combined schema */}
          {Object.entries(elementSchema.config_schema.properties)
            .filter(([fieldName, fieldSchema]) => {
              // Always exclude category and type (handled by GUI)
              if (['category', 'type'].includes(fieldName)) {
                return false;
              }

              // Filter out hidden fields - check if field has hints.hidden.hint_type === "hidden"
              if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
                return false;
              }

              // For both Create New and Edit mode: show only first-level required fields (name) + all cfg_dict fields
              // Show first-level required fields (name is required from resource.schema)
              const firstLevelRequiredFields = ['name'];
              if (firstLevelRequiredFields.includes(fieldName)) {
                return true;
              }

              // Show all cfg_dict fields (element-specific config fields)
              // These are fields that are NOT first-level fields from resource.schema
              const firstLevelFields = ['name', 'category', 'type', 'cfg_dict', 'version', 'created', 'updated', 'nested_refs', 'rid', 'user_id'];
              const isCfgDictField = !firstLevelFields.includes(fieldName);
              return isCfgDictField;

              // Comment out the old edit mode logic that showed extra fields
              // // For Edit mode: show all fields (except category/type)
              // if (editingElement) {
              //   return true;
              // }
            })
            .sort(([fieldNameA, fieldSchemaA], [fieldNameB, fieldSchemaB]) => {
              // Sort fields so that fields with dependencies come after their dependency fields
              const populateHintA = fieldSchemaA?.hints?.action?.hint_type === 'populate' ? fieldSchemaA.hints.action : null;
              const populateHintB = fieldSchemaB?.hints?.action?.hint_type === 'populate' ? fieldSchemaB.hints.action : null;
              
              // If A depends on B, A should come after B
              if (populateHintA?.dependencies && Object.keys(populateHintA.dependencies).includes(fieldNameB)) {
                return 1; // A comes after B
              }
              
              // If B depends on A, B should come after A
              if (populateHintB?.dependencies && Object.keys(populateHintB.dependencies).includes(fieldNameA)) {
                return -1; // A comes before B
              }
              
              // Otherwise, maintain original order
              return 0;
            })
            .map(([fieldName, fieldSchema]) => renderFormField(fieldName, fieldSchema))}

          <DialogFooter className="mt-6">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <UmamiTrack 
              event={UmamiEvents.AGENT_REPOSITORY_SAVE_ELEMENT_BUTTON}
            >
              <Button
                type="submit"
                className="bg-primary hover:bg-opacity-80"
                disabled={isSaving || !isFormValid()}
              >
                {isSaving ? "Saving..." : "Save"}
              </Button>
            </UmamiTrack>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};