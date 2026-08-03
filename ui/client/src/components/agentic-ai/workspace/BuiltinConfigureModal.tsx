import React, { useState, useEffect, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  ElementType,
  ElementSchema,
  ElementInstance,
} from "../../../types/workspace";
import { ElementConfigField } from "./ElementConfigField";
import { isUserConfigurable } from "@/lib/cardFields";
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { useElementFieldHelpers } from "@/hooks/use-element-field-helpers";
import { useConfigFieldActions } from "@/hooks/use-config-field-actions";
import { useResourceRefOptions } from "@/hooks/use-resource-ref-options";
import { LoaderCircle, Check, Loader2 } from "lucide-react";

/** Subset of JSON Schema property fields used in the builtin configure UI. */
interface SchemaProperty {
  type?: string;
  default?: unknown;
  anyOf?: { type?: string }[];
  hints?: {
    hidden?: boolean;
    auth?: boolean;
    read_only?: boolean;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

interface BuiltinConfigureModalProps {
  isOpen: boolean;
  onClose: () => void;
  element: ElementInstance;
  elementType: ElementType;
  elementSchema?: ElementSchema | null;
  onSave: (config: Record<string, any>) => Promise<any>;
}

export const BuiltinConfigureModal: React.FC<BuiltinConfigureModalProps> = ({
  isOpen,
  onClose,
  element,
  elementType,
  elementSchema: parentSchema,
  onSave,
}) => {
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingSchema, setIsLoadingSchema] = useState(false);
  const [builtinSchema, setBuiltinSchema] = useState<ElementSchema | null>(null);

  const { fetchBuiltinSchema, fetchBuiltinUserConfig, fetchResourcesForCategory, fetchElementActions } = useWorkspaceData();
  const [elementActions, setElementActions] = useState<any[]>([]);
  const [userOverlay, setUserOverlay] = useState<Record<string, any> | null>(null);

  const fieldActions = useConfigFieldActions(builtinSchema?.config_schema?.properties);
  const { formData, setFormData, fieldValidationStates, resetTransientState } = fieldActions;

  useEffect(() => {
    if (!isOpen || !element) return;

    let cancelled = false;
    setIsLoadingSchema(true);
    setUserOverlay(null);
    // This component stays mounted across dialog open/close (Radix only
    // toggles visibility), so without this, stale per-field validation
    // results from a previous session would leak in and could let Save
    // stay enabled — or stay wrongly disabled — before anything in the
    // freshly-opened form has actually been (re)validated.
    resetTransientState();

    (async () => {
      try {
        const [schema, overlay] = await Promise.all([
          fetchBuiltinSchema(element.rid),
          fetchBuiltinUserConfig(element.rid),
        ]);
        if (cancelled) return;

        setUserOverlay(overlay);

        if (schema) {
          const combined: ElementSchema = {
            category: element.category || "",
            name: element.name || "",
            type: element.type || "",
            description: `Configure ${element.name || elementType.name}`,
            tags: [],
            config_schema: schema,
          };
          setBuiltinSchema(combined);
        }

        if (element.category && element.type) {
          const actions = await fetchElementActions(element.category, element.type);
          if (!cancelled) setElementActions(actions || []);
        }
      } catch (error) {
        console.error('Error loading builtin schema/config:', error);
      } finally {
        if (!cancelled) setIsLoadingSchema(false);
      }
    })();

    return () => { cancelled = true; };
  }, [isOpen, element?.rid]);

  const configurableFields = useMemo(() => {
    if (!builtinSchema?.config_schema?.properties) return {};
    const fields: Record<string, SchemaProperty> = {};
    for (const [name, schema] of Object.entries(builtinSchema.config_schema.properties)) {
      if (!isUserConfigurable(schema)) continue;
      fields[name] = schema as SchemaProperty;
    }
    return fields;
  }, [builtinSchema]);

  useEffect(() => {
    if (!isOpen || Object.keys(configurableFields).length === 0) return;

    const initialData: Record<string, unknown> = {};

    // Seed formData with ALL config values from the element so that
    // read-only fields (mcp_url, auth_method, transport_type, etc.) are
    // available for conditional-visibility checks and populate-action
    // dependency mappings, even though they aren't rendered as editable.
    if (element.config) {
      for (const [key, value] of Object.entries(element.config)) {
        if (value !== undefined && value !== null) {
          initialData[key] = value;
        }
      }
    }

    // For configurable fields, prefer the user's own overlay over the base
    // config.  When no overlay exists the field starts at its schema default
    // so that users never see the admin's base values (e.g. bearer tokens)
    // leaking through.
    for (const [key, property] of Object.entries(configurableFields)) {
      const overlayValue = userOverlay?.[key];
      const hasOverlay = overlayValue !== undefined && overlayValue !== null;

      if (hasOverlay) {
        if (typeof overlayValue === "string" && overlayValue.startsWith("$ref:")) {
          initialData[key] = overlayValue.substring(5);
        } else if (Array.isArray(overlayValue)) {
          initialData[key] = overlayValue.map((item: unknown) =>
            typeof item === "string" && item.startsWith("$ref:")
              ? item.substring(5)
              : item,
          );
        } else {
          initialData[key] = overlayValue;
        }
      } else if (property.default !== undefined) {
        initialData[key] = property.default;
      } else if (property.type === "array" ||
                 (property.anyOf && property.anyOf.some((o) => o.type === "array"))) {
        initialData[key] = [];
      } else if (property.type === "boolean") {
        initialData[key] = false;
      } else {
        initialData[key] = "";
      }
    }
    setFormData(initialData);
  }, [configurableFields, isOpen, element?.config, userOverlay]);

  const {
    isFieldConditionallyVisible,
    isArrayWithRefItems,
    getArrayItemsSchema,
    resolveRef,
    isStringEnumRef,
    extractCategoryFromField,
  } = useElementFieldHelpers(builtinSchema?.config_schema, formData);

  const refCategories = useMemo(() => {
    const categories = new Set<string>();
    if (!isOpen) return categories;
    for (const property of Object.values(configurableFields)) {
      const category = extractCategoryFromField(property);
      if (category) categories.add(category);
    }
    return categories;
  }, [configurableFields, isOpen, extractCategoryFromField]);

  const [refOptions] = useResourceRefOptions(refCategories, fetchResourcesForCategory);

  const handleSave = async () => {
    // Guard against native form submission (e.g. pressing Enter in a text
    // field) bypassing the disabled Save button — same invariant enforced
    // by the button's `disabled` prop below.
    if (!allValidationsPassed) return;

    setIsSaving(true);
    try {
      const config: Record<string, any> = {};
      for (const [fieldName, value] of Object.entries(formData)) {
        const fieldSchema = configurableFields[fieldName];
        if (!fieldSchema) continue;
        if (!isFieldConditionallyVisible(fieldSchema)) continue;

        let processedValue = value;

        if (isArrayWithRefItems(fieldSchema) && Array.isArray(value)) {
          processedValue = value.map((rid: string) => `$ref:${rid}`);
        } else if (fieldSchema.$ref && typeof value === "string" && value !== "" && !isStringEnumRef(fieldSchema)) {
          processedValue = `$ref:${value}`;
        } else if (
          fieldSchema.anyOf &&
          fieldSchema.anyOf.some((option: any) => option.$ref) &&
          typeof value === "string" && value !== ""
        ) {
          processedValue = `$ref:${value}`;
        }

        const isEmpty = processedValue === "" || processedValue === null || processedValue === undefined ||
            (Array.isArray(processedValue) && processedValue.length === 0) ||
            (typeof processedValue === "object" && !Array.isArray(processedValue) && Object.keys(processedValue).length === 0);

        if (!isEmpty) {
          config[fieldName] = processedValue;
        } else if (userOverlay && Object.prototype.hasOwnProperty.call(userOverlay, fieldName)) {
          // Previously configured but now cleared by the user — send an
          // explicit `null` so the backend overlay clears the stored value,
          // instead of omitting the key (which would leave the old value in
          // place). Fields that were never configured stay omitted.
          config[fieldName] = null;
        }
      }

      if (Object.keys(config).length > 0) {
        await onSave(config);
      }
      onClose();
    } catch (error) {
      console.error("Error saving built-in configuration:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const renderFormField = (fieldName: string, fieldSchema: any) => (
    <ElementConfigField
      fieldName={fieldName}
      fieldSchema={fieldSchema}
      isRequired={builtinSchema?.config_schema?.required?.includes(fieldName) ?? false}
      editingElement={element}
      elementActions={elementActions}
      elementType={elementType}
      refOptions={refOptions}
      fieldHelpers={{ isArrayWithRefItems, getArrayItemsSchema, extractCategoryFromField, resolveRef }}
      fieldActions={fieldActions}
    />
  );

  const fieldEntries = Object.entries(configurableFields).filter(
    ([, schema]) => isFieldConditionallyVisible(schema as any)
  );

  const allValidationsPassed = useMemo(() => {
    for (const [fieldName, fieldSchema] of fieldEntries) {
      const s = fieldSchema as any;
      const hasValidation =
        s.hints?.action?.hint_type === "validate" ||
        s.hints?.api?.hint_type === "validate";
      if (!hasValidation) continue;
      if (fieldValidationStates[fieldName] !== true) return false;
    }
    return true;
  }, [fieldEntries, fieldValidationStates]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent
        className="bg-background-card border-gray-800 text-foreground max-w-lg max-h-[80vh] flex flex-col overflow-hidden p-0 gap-0"
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader className="px-6 pt-6 pb-4 flex-shrink-0 border-b border-gray-800">
          <DialogTitle>
            Configure {element.name || elementType.name}
          </DialogTitle>
          <DialogDescription>
            Set your personal configuration for this built-in resource.
          </DialogDescription>
        </DialogHeader>

        {isLoadingSchema ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2 text-gray-400">
            <LoaderCircle className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm">Loading configuration...</p>
          </div>
        ) : fieldEntries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2 text-gray-400">
            <p className="text-sm">No configurable fields for this element.</p>
          </div>
        ) : (
          <form
            onSubmit={(e) => { e.preventDefault(); handleSave(); }}
            className="flex flex-col flex-1 min-h-0"
          >
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
              {fieldEntries.map(([fieldName, fieldSchema]) => (
                <div key={fieldName}>
                  {renderFormField(fieldName, fieldSchema as any)}
                </div>
              ))}
            </div>

            <DialogFooter className="px-6 pb-6 pt-4 flex-shrink-0 border-t border-gray-800">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="submit"
                className="bg-primary hover:bg-opacity-80"
                disabled={isSaving || !allValidationsPassed}
              >
                {isSaving ? (
                  <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Saving...</>
                ) : (
                  <><Check className="h-4 w-4 mr-1" /> Save</>
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};
