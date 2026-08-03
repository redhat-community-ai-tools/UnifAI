import React, { useState, useEffect, useCallback, useMemo } from "react";
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
import { ElementConfigField } from "./ElementConfigField";

import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import { useAuth } from "@/contexts/AuthContext";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";
import { useToast } from "@/hooks/use-toast";
import { useElementFieldHelpers } from "@/hooks/use-element-field-helpers";
import { useConfigFieldActions } from "@/hooks/use-config-field-actions";
import { useResourceRefOptions } from "@/hooks/use-resource-ref-options";
import {
  acquireTeamEditLock,
  heartbeatTeamEditLock,
  releaseTeamEditLock,
} from "@/api/collaborationEditLock";
import { LoaderCircle } from "lucide-react";
import OpenShellSandboxGuidelines from "./OpenShellSandboxGuidelines";

function normalizeElementName(v: string): string {
  return v.trim().toLowerCase();
}

interface ElementFormProps {
  isOpen: boolean;
  onClose: () => void;
  elementType: ElementType;
  elementSchema: ElementSchema;
  elementActions?: any[];
  editingElement: ElementInstance | null;
  /** Names of other instances of this element type (used for duplicate name checks). */
  existingNames?: string[];
  onSave: (data: any) => Promise<unknown>;
  /** When true, $ref dropdowns only show built-in resources. */
  builtinOnly?: boolean;
}

export const ElementForm: React.FC<ElementFormProps> = ({
  isOpen,
  onClose,
  elementType,
  elementSchema,
  elementActions = [],
  editingElement,
  existingNames = [],
  onSave,
  builtinOnly = false,
}) => {
  const [isSaving, setIsSaving] = useState(false);
  const fieldActions = useConfigFieldActions(elementSchema?.config_schema?.properties);
  const {
    formData,
    setFormData,
    fieldValidationStates,
    itemValidationStates,
    actionOutputs,
    handleInputChange,
    handleArrayChange,
    addArrayItem,
    removeArrayItem,
    handleValidationChange,
    handlePopulateResult,
    handleActionOutput,
  } = fieldActions;
  const [refEditState, setRefEditState] = useState<{
    element: ElementInstance;
    schema: ElementSchema;
    actions: any[];
    elementType: ElementType;
    existingNames: string[];
  } | null>(null);

  const {
    fetchResourcesForCategory,
    fetchResourceById,
    fetchElementSchema: fetchSchemaForRef,
    fetchElementActions: fetchActionsForRef,
    saveElement: saveRefElement,
  } = useWorkspaceData();
  const { user } = useAuth();
  const { isTeam: isTeamWorkspace, userId: teamId } = useWorkspaceIdentity();
  const { toast } = useToast();
  const needsResourceEditLock =
    isOpen && isTeamWorkspace && !!editingElement?.rid && !!user?.username;
  const [resourceEditLockReady, setResourceEditLockReady] = useState(true);
  const [resourceLockHeld, setResourceLockHeld] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setResourceEditLockReady(true);
      setResourceLockHeld(false);
      return;
    }
    if (!needsResourceEditLock || !user?.username) {
      setResourceEditLockReady(true);
      setResourceLockHeld(false);
      return;
    }

    setResourceEditLockReady(false);
    setResourceLockHeld(false);
    let cancelled = false;
    let lockTaken = false;
    const rid = editingElement!.rid;
    const displayName = user.name?.trim() || user.username;

    (async () => {
      try {
        const result = await acquireTeamEditLock({
          teamId,
          entityKind: "resource",
          entityId: rid,
          userId: user.username,
          displayName,
        });
        if (cancelled) return;
        if (!result.acquired) {
          toast({
            title: "Someone else is editing this element",
            description: `Currently being edited by ${result.lockedBy.displayName || result.lockedBy.userId}.`,
            variant: "destructive",
          });
          onClose();
          return;
        }
        lockTaken = true;
        setResourceLockHeld(true);
        setResourceEditLockReady(true);
      } catch {
        if (cancelled) return;
        toast({
          title: "Could not start editing",
          description: "Failed to acquire edit lock. Try again.",
          variant: "destructive",
        });
        onClose();
      }
    })();

    return () => {
      cancelled = true;
      if (lockTaken) {
        void releaseTeamEditLock({
          teamId,
          entityKind: "resource",
          entityId: rid,
          userId: user.username,
        });
        setResourceLockHeld(false);
      }
    };
  }, [
    isOpen,
    needsResourceEditLock,
    teamId,
    editingElement?.rid,
    user?.username,
    user?.name,
    onClose,
    toast,
  ]);

  useEffect(() => {
    if (!resourceLockHeld || !needsResourceEditLock || !user?.username || !editingElement?.rid) {
      return;
    }
    const rid = editingElement.rid;
    const displayName = user.name?.trim() || user.username;
    let interval: ReturnType<typeof setInterval> | undefined;
    interval = window.setInterval(() => {
      void heartbeatTeamEditLock({
        teamId,
        entityKind: "resource",
        entityId: rid,
        userId: user.username,
        displayName,
      }).catch((err: unknown) => {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 501) return;
        if (interval != null) window.clearInterval(interval);
        interval = undefined;
        setResourceLockHeld(false);
        toast({
          title: "Edit lock lost",
          description: "We could not renew the team edit lock. The editor will close.",
          variant: "destructive",
        });
        onClose();
      });
    }, 45_000);
    return () => {
      if (interval != null) window.clearInterval(interval);
    };
  }, [
    resourceLockHeld,
    needsResourceEditLock,
    teamId,
    editingElement?.rid,
    user?.username,
    user?.name,
    toast,
    onClose,
  ]);

  const existingNamesSet = useMemo(
    () =>
      new Set(
        existingNames
          .map((n) => normalizeElementName(n))
          .filter((n) => n.length > 0),
      ),
    [existingNames],
  );

  const nameError = useMemo(() => {
    const raw = formData.name;
    if (typeof raw !== "string") return null;
    const trimmed = raw.trim();
    if (!trimmed) return null;

    if (
      editingElement?.name &&
      normalizeElementName(editingElement.name) === normalizeElementName(raw)
    ) {
      return null;
    }

    if (existingNamesSet.has(normalizeElementName(raw))) {
      return `A ${elementType.name} named "${trimmed}" already exists. Please choose a different name.`;
    }
    return null;
  }, [formData.name, existingNamesSet, editingElement?.name, elementType.name]);

  const {
    isFieldConditionallyVisible,
    isArrayWithRefItems,
    getArrayItemsSchema,
    resolveRef,
    isStringEnumRef,
    extractCategoryFromField,
  } = useElementFieldHelpers(elementSchema?.config_schema, formData);

  // Initialize form data
  useEffect(() => {
    if (elementSchema && isOpen) {
      const initialData: any = {};

      // Set default values from combined schema, excluding hidden fields
      Object.entries(elementSchema.config_schema.properties).forEach(
        ([key, property]: [string, any]) => {
          // Skip hidden fields - don't initialize them (except auth-flow fields)
          if (property?.hints?.hidden?.hint_type === "hidden") {
            if (key === "server_identifier" || key === "scheme_type" || key === "credential_token") {
              initialData[key] = property.default ?? "";
            }
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
            
            // Skip hidden fields - don't populate them in edit mode (except auth-flow fields)
            if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
              if (key === "server_identifier" || key === "scheme_type" || key === "credential_token") {
                initialData[key] = value;
              }
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
          });
        }
      }

      setFormData(initialData);
    }
  }, [elementSchema, editingElement, isOpen]);

  // Fields whose $ref (or array-of-$ref) resolves to a resource category —
  // drives which categories `useResourceRefOptions` needs to fetch.
  const refCategories = useMemo(() => {
    const categories = new Set<string>();
    if (!elementSchema || !isOpen) return categories;
    for (const property of Object.values(elementSchema.config_schema.properties)) {
      const category = extractCategoryFromField(property);
      if (category) categories.add(category);
    }
    return categories;
  }, [elementSchema, isOpen, extractCategoryFromField]);

  const [refOptions, setRefOptions] = useResourceRefOptions(
    refCategories,
    fetchResourcesForCategory,
    builtinOnly ? "builtin" : undefined,
  );

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

  const handleEditRefElement = useCallback(async (rid: string) => {
    let foundCategory: string | null = null;
    let foundOption: any = null;

    for (const [category, options] of Object.entries(refOptions)) {
      const option = options.find((opt: any) => opt.rid === rid);
      if (option) {
        foundCategory = category;
        foundOption = option;
        break;
      }
    }

    if (!foundCategory || !foundOption) return;

    try {
      const [resource, schema, actions] = await Promise.all([
        fetchResourceById(rid),
        fetchSchemaForRef(foundCategory, foundOption.type),
        fetchActionsForRef(foundCategory, foundOption.type),
      ]);

      if (!resource || !schema) return;

      setRefEditState({
        element: {
          rid: resource.rid,
          name: resource.name,
          config: resource.cfg_dict,
          category: resource.category,
          type: resource.type,
          version: resource.version,
          created: resource.created,
          updated: resource.updated,
          nested_refs: resource.nested_refs,
        },
        schema,
        actions: actions || [],
        elementType: {
          category: foundCategory,
          name: schema.name,
          type: foundOption.type,
        },
        existingNames: (refOptions[foundCategory] || [])
          .filter((opt: any) => opt.rid !== rid)
          .map((opt: any) => opt.name)
          .filter(Boolean),
      });
    } catch (error) {
      console.error('Error loading ref element for editing:', error);
    }
  }, [refOptions, fetchResourceById, fetchSchemaForRef, fetchActionsForRef]);

  const handleSaveRefElement = useCallback(async (elementData: any) => {
    if (!refEditState) return null;

    const { element, elementType: refElementType } = refEditState;
    const result = await saveRefElement(
      refElementType.category,
      refElementType.type,
      elementData,
      element.rid,
    );

    if (result) {
      try {
        const updatedOptions = await fetchResourcesForCategory(
          refElementType.category,
          builtinOnly ? "builtin" : undefined,
        );
        setRefOptions(prev => ({
          ...prev,
          [refElementType.category]: updatedOptions,
        }));
      } catch (error) {
        console.error('Error refreshing ref options:', error);
      }
    }

    return result;
  }, [refEditState, saveRefElement, fetchResourcesForCategory, builtinOnly]);

  // Check if all required fields are filled.
  // Validation hints (connection checks, ref validation) are informational —
  // they show status visually but do NOT block saving.
  const isFormValid = () => {
    if (!elementSchema) return false;

    // Check all required fields from combined schema, excluding hidden fields
    const required = elementSchema.config_schema.required || [];
    const allRequiredFieldsValid = required.every((field) => {
      const fieldSchema = elementSchema.config_schema.properties[field];
      
      // Skip validation for hidden fields
      if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
        return true;
      }

      // Skip validation for conditionally hidden fields
      if (!isFieldConditionallyVisible(fieldSchema)) {
        return true;
      }
      
      const value = formData[field];
      
      // Basic value validation — just check if value exists
      if (Array.isArray(value)) {
        return value.length > 0;
      }
      return value !== undefined && value !== null && value !== "" && 
                (typeof value !== "string" || value.trim() !== "");
    });

    return allRequiredFieldsValid && !nameError;
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);

      if (nameError) {
        return;
      }

      // Validate all required fields from combined schema, excluding hidden and conditionally hidden fields
      const required = elementSchema.config_schema.required || [];
      const missing = required.filter((field) => {
        const fieldSchema = elementSchema.config_schema.properties[field];
        
        // Skip validation for hidden fields
        if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
          return false;
        }

        // Skip validation for conditionally hidden fields
        if (!isFieldConditionallyVisible(fieldSchema)) {
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
        // EXCEPT server_identifier and scheme_type which are needed for auth credential lookup
        if (fieldSchema?.hints?.hidden?.hint_type === "hidden") {
          if (fieldName === "server_identifier" || fieldName === "scheme_type") {
            configForSave[fieldName] = value ?? "";
          }
          return;
        }

        // Skip conditionally hidden fields
        if (!isFieldConditionallyVisible(fieldSchema)) {
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
            // Handle single $ref fields - only add $ref: prefix for resource references (RIDs), exclude string enums
            else if (fieldSchema.$ref && typeof value === "string" && value !== "" && !isStringEnumRef(fieldSchema)) {
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

      if (result) {
        onClose();
      }
    } catch (error) {
      console.error("Error saving element:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const renderFormField = (fieldName: string, fieldSchema: any, configurabilityBadge?: React.ReactNode) => (
    <ElementConfigField
      fieldName={fieldName}
      fieldSchema={fieldSchema}
      isRequired={elementSchema.config_schema.required?.includes(fieldName) ?? false}
      editingElement={editingElement}
      elementActions={elementActions}
      elementType={elementType}
      refOptions={refOptions}
      fieldHelpers={{ isArrayWithRefItems, getArrayItemsSchema, extractCategoryFromField, resolveRef }}
      fieldActions={fieldActions}
      onEditRefElement={handleEditRefElement}
      labelBadge={configurabilityBadge}
    />
  );

  const renderConfigurabilityLabel = (fieldSchema: any): React.ReactNode => {
    if (!builtinOnly) return null;
    if (fieldSchema?.hints?.hidden) return null;
    if (fieldSchema?.hints?.auth) return null;
    const isConfigurable = fieldSchema?.hints?.read_only?.read_only === false;
    return (
      <span className={`inline-flex items-center text-[10px] px-1.5 py-0.5 rounded font-medium ${
        isConfigurable
          ? "bg-primary/10 text-primary border border-primary/20"
          : "bg-gray-500/10 text-gray-400 border border-gray-500/20"
      }`}>
        {isConfigurable ? "User-configurable" : "Admin-only"}
      </span>
    );
  };

  const renderFormGuidelines = (): React.ReactNode => {
    switch (elementType.type) {
      case "openshell_sandbox":
        return <OpenShellSandboxGuidelines />;
      default:
        return null;
    }
  };

  if (!elementSchema) return null;

  return (
    <>
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent
        className="bg-background-card border-gray-800 text-foreground max-w-3xl max-h-[90vh] flex flex-col overflow-hidden p-0 gap-0"
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader className="px-6 pt-6 pb-4 flex-shrink-0 border-b border-gray-800">
          <DialogTitle>
            {editingElement ? "Edit" : "Create"} {elementType.name}
          </DialogTitle>
          <DialogDescription>{elementSchema.description}</DialogDescription>
          {renderFormGuidelines()}
        </DialogHeader>

        {needsResourceEditLock && !resourceEditLockReady ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2 text-gray-400">
            <LoaderCircle className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm">Reserving edit access…</p>
          </div>
        ) : null}

        {!(needsResourceEditLock && !resourceEditLockReady) ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSave();
          }}
          className="flex flex-col flex-1 min-h-0"
        >
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
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

                // Filter out conditionally hidden fields
                if (!isFieldConditionallyVisible(fieldSchema)) {
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
              .map(([fieldName, fieldSchema]) => {
                const firstLevelFields = ['name', 'category', 'type', 'cfg_dict', 'version', 'created', 'updated', 'nested_refs', 'rid', 'user_id'];
                const configurabilityLabel = firstLevelFields.includes(fieldName)
                  ? null
                  : renderConfigurabilityLabel(fieldSchema);
                return (
                  <div key={fieldName}>
                    {renderFormField(fieldName, fieldSchema, configurabilityLabel)}
                    {fieldName === "name" && nameError ? (
                      <p className="text-destructive text-sm mt-1">{nameError}</p>
                    ) : null}
                  </div>
                );
              })}
          </div>

          <DialogFooter className="px-6 pb-6 pt-4 flex-shrink-0 border-t border-gray-800">
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
        ) : null}
      </DialogContent>
    </Dialog>
    {refEditState && (
      <ElementForm
        isOpen={!!refEditState}
        onClose={() => setRefEditState(null)}
        elementType={refEditState.elementType}
        elementSchema={refEditState.schema}
        elementActions={refEditState.actions}
        editingElement={refEditState.element}
        existingNames={refEditState.existingNames}
        onSave={handleSaveRefElement}
        builtinOnly={builtinOnly}
      />
    )}
    </>
  );
};