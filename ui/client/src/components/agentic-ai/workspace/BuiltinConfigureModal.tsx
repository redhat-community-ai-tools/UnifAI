import React, { useState, useEffect, useCallback, useMemo } from "react";
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
import { FieldRenderer, getStringEnumFromRef } from "./FieldRenderer";
import { ItemValidationResult } from "./FieldValidation";
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { useAuth } from "@/contexts/AuthContext";
import { LoaderCircle, Check, Loader2 } from "lucide-react";

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
  const [formData, setFormData] = useState<any>({});
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingSchema, setIsLoadingSchema] = useState(false);
  const [builtinSchema, setBuiltinSchema] = useState<ElementSchema | null>(null);
  const [refOptions, setRefOptions] = useState<{ [category: string]: any[] }>({});
  const [fieldValidationStates, setFieldValidationStates] = useState<{ [fieldName: string]: boolean }>({});
  const [itemValidationStates, setItemValidationStates] = useState<{ [fieldName: string]: ItemValidationResult[] }>({});
  const [actionOutputs, setActionOutputs] = useState<Record<string, any>>({});

  const { fetchBuiltinSchema, fetchBuiltinUserConfig, fetchResourcesForCategory, fetchElementActions } = useWorkspaceData();
  const { user } = useAuth();
  const [elementActions, setElementActions] = useState<any[]>([]);
  const [userOverlay, setUserOverlay] = useState<Record<string, any> | null>(null);

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
    setFieldValidationStates({});
    setItemValidationStates({});
    setActionOutputs({});

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
      } finally {
        if (!cancelled) setIsLoadingSchema(false);
      }
    })();

    return () => { cancelled = true; };
  }, [isOpen, element?.rid]);

  const configurableFields = useMemo(() => {
    if (!builtinSchema?.config_schema?.properties) return {};
    const fields: Record<string, any> = {};
    for (const [name, schema] of Object.entries(builtinSchema.config_schema.properties)) {
      const s = schema as any;
      if (s?.hints?.hidden?.hint_type === "hidden") continue;
      if (s?.hints?.read_only?.read_only === true) continue;
      if (s?.hints?.auth) continue;
      fields[name] = s;
    }
    return fields;
  }, [builtinSchema]);

  useEffect(() => {
    if (!isOpen || Object.keys(configurableFields).length === 0) return;

    const initialData: any = {};

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
    for (const [key, property] of Object.entries(configurableFields) as [string, any][]) {
      const overlayValue = userOverlay?.[key];
      const hasOverlay = overlayValue !== undefined && overlayValue !== null;

      if (hasOverlay) {
        if (typeof overlayValue === "string" && overlayValue.startsWith("$ref:")) {
          initialData[key] = overlayValue.substring(5);
        } else if (Array.isArray(overlayValue)) {
          initialData[key] = overlayValue.map((item: any) =>
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
                 (property.anyOf && property.anyOf.some((o: any) => o.type === "array"))) {
        initialData[key] = [];
      } else if (property.type === "boolean") {
        initialData[key] = false;
      } else {
        initialData[key] = "";
      }
    }
    setFormData(initialData);
  }, [configurableFields, isOpen, element?.config, userOverlay]);

  const isFieldConditionallyVisible = useCallback((fieldSchema: any): boolean => {
    const conditions = fieldSchema?.hints?.conditional?.visible_when;
    if (!conditions) return true;
    return Object.entries(conditions).every(
      ([field, requiredValue]) => formData[field] === requiredValue,
    );
  }, [formData]);

  const isArrayWithRefItems = (fieldSchema: any) => {
    if (fieldSchema.type === "array" && fieldSchema.items?.$ref) return true;
    if (fieldSchema.anyOf && Array.isArray(fieldSchema.anyOf)) {
      return fieldSchema.anyOf.some(
        (option: any) => option.type === "array" && option.items?.$ref,
      );
    }
    return false;
  };

  const getArrayItemsSchema = (fieldSchema: any) => {
    if (fieldSchema.type === "array" && fieldSchema.items) return fieldSchema.items;
    if (fieldSchema.anyOf && Array.isArray(fieldSchema.anyOf)) {
      const arrayOption = fieldSchema.anyOf.find(
        (option: any) => option.type === "array" && option.items,
      );
      return arrayOption?.items;
    }
    return null;
  };

  const resolveRef = (ref: string): any | null => {
    if (!ref || typeof ref !== 'string' || !ref.startsWith('#/')) return null;
    const pathSegments = ref.substring(2).split('/').filter(s => s.length > 0);
    let current: any = builtinSchema?.config_schema;
    for (const segment of pathSegments) {
      if (!current || typeof current !== 'object' || !(segment in current)) return null;
      current = current[segment];
    }
    return current;
  };

  const isStringEnumRef = (fieldSchema: any): boolean => {
    return getStringEnumFromRef(fieldSchema, resolveRef) !== null;
  };

  const extractCategoryFromField = (fieldSchema: any): string | null => {
    const tryResolve = (ref: string) => {
      const resolved = resolveRef(ref);
      return resolved?.category || null;
    };
    if (fieldSchema.$ref) { const c = tryResolve(fieldSchema.$ref); if (c) return c; }
    if (fieldSchema.items?.$ref) { const c = tryResolve(fieldSchema.items.$ref); if (c) return c; }
    if (fieldSchema.anyOf && Array.isArray(fieldSchema.anyOf)) {
      for (const option of fieldSchema.anyOf) {
        if (option.$ref) { const c = tryResolve(option.$ref); if (c) return c; }
        if (option.type === "array" && option.items?.$ref) {
          const c = tryResolve(option.items.$ref); if (c) return c;
        }
      }
    }
    return null;
  };

  useEffect(() => {
    if (!builtinSchema || !isOpen) return;

    const refCategories = new Set<string>();
    for (const [, property] of Object.entries(configurableFields)) {
      const category = extractCategoryFromField(property);
      if (category) refCategories.add(category);
    }

    if (refCategories.size === 0) return;

    const loadRefOptions = async () => {
      const options: { [category: string]: any[] } = {};
      for (const category of Array.from(refCategories)) {
        try {
          const resources = await fetchResourcesForCategory(category);
          options[category] = resources;
        } catch {
          options[category] = [];
        }
      }
      setRefOptions(options);
    };
    loadRefOptions();
  }, [builtinSchema, isOpen, configurableFields, fetchResourcesForCategory]);

  const handleInputChange = (field: string, value: any) => {
    setFormData((prev: any) => {
      const updated = { ...prev, [field]: value };

      const fieldSchema =
        configurableFields[field] ||
        builtinSchema?.config_schema?.properties?.[field];
      const propagateHint = (fieldSchema as any)?.hints?.propagate;
      if (propagateHint?.to) {
        updated[propagateHint.to] =
          propagateHint.value !== undefined && propagateHint.value !== null
            ? propagateHint.value
            : value;
      }

      return updated;
    });
  };

  const handleArrayChange = (field: string, index: number, value: any) => {
    setFormData((prev: any) => ({
      ...prev,
      [field]: prev[field].map((item: any, i: number) => i === index ? value : item),
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

  const handleValidationChange = (fieldName: string, isValid: boolean, itemResults?: ItemValidationResult[]) => {
    setFieldValidationStates(prev => ({ ...prev, [fieldName]: isValid }));
    if (itemResults) {
      setItemValidationStates(prev => ({ ...prev, [fieldName]: itemResults }));
    }
  };

  const handlePopulateResult = (fieldName: string, results: any[], multiSelect: boolean) => {
    if (multiSelect) {
      handleInputChange(fieldName, results);
    } else {
      handleInputChange(fieldName, results.length > 0 ? results[0] : "");
    }
  };

  const handleActionOutput = (fieldName: string, output: any) => {
    setActionOutputs(prev => ({ ...prev, [fieldName]: output }));
  };

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

  const renderFormField = (fieldName: string, fieldSchema: any) => {
    const isRequired = builtinSchema?.config_schema?.required?.includes(fieldName) ?? false;
    const value = formData[fieldName] || "";

    const actionValidationHint = fieldSchema.hints?.action?.hint_type === 'validate' ? fieldSchema.hints.action : null;
    const apiValidationHint = fieldSchema.hints?.api?.hint_type === 'validate' ? fieldSchema.hints.api : null;
    const validationHint = actionValidationHint || apiValidationHint;

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
        editingElement={element}
        elementActions={elementActions}
        elementType={elementType}
        formData={formData}
        refOptions={refOptions}
        fieldType={isSecret ? "secret" : "public"}
        fieldValidationStates={fieldValidationStates}
        itemValidationStates={itemValidationStates}
        actionOutputs={actionOutputs}
        isArrayWithRefItems={isArrayWithRefItems}
        getArrayItemsSchema={getArrayItemsSchema}
        extractCategoryFromField={extractCategoryFromField}
        resolveSchemaRef={resolveRef}
        onInputChange={handleInputChange}
        onArrayChange={handleArrayChange}
        onAddArrayItem={addArrayItem}
        onRemoveArrayItem={removeArrayItem}
        onValidationChange={handleValidationChange}
        onPopulateResult={handlePopulateResult}
        onActionOutput={handleActionOutput}
      />
    );
  };

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
