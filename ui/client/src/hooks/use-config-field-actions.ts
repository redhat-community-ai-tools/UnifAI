import { useState } from "react";
import { ItemValidationResult } from "@/components/agentic-ai/workspace/FieldValidation";

export interface ConfigFieldActions {
  formData: any;
  setFormData: React.Dispatch<React.SetStateAction<any>>;
  fieldValidationStates: { [fieldName: string]: boolean };
  itemValidationStates: { [fieldName: string]: ItemValidationResult[] };
  actionOutputs: Record<string, any>;
  handleInputChange: (field: string, value: any) => void;
  handleArrayChange: (field: string, index: number, value: any) => void;
  addArrayItem: (field: string) => void;
  removeArrayItem: (field: string, index: number) => void;
  handleValidationChange: (
    fieldName: string,
    isValid: boolean,
    itemResults?: ItemValidationResult[],
  ) => void;
  handlePopulateResult: (fieldName: string, results: any[], multiSelect: boolean) => void;
  handleActionOutput: (fieldName: string, output: any) => void;
  resetTransientState: () => void;
}

/**
 * Shared formData-mutation and per-field validation/populate/action-output
 * state for config forms (`ElementForm`, `BuiltinConfigureModal`) — this was
 * previously duplicated close to byte-for-byte between them.
 *
 * Each form still owns its own formData *initialization* (schema defaults,
 * editing-element merge, per-user overlay handling, etc. all differ
 * meaningfully between "edit the base definition" and "set my personal
 * overlay"), so this hook only covers the mutation/handler surface that
 * kicks in once formData already exists.
 *
 * `schemaProperties` should be the config schema's `properties` map (or
 * `undefined` while the schema hasn't loaded yet) — used to resolve
 * `propagate` hints when a field changes.
 */
export function useConfigFieldActions(
  schemaProperties: Record<string, any> | undefined,
): ConfigFieldActions {
  const [formData, setFormData] = useState<any>({});
  const [fieldValidationStates, setFieldValidationStates] = useState<{
    [fieldName: string]: boolean;
  }>({});
  const [itemValidationStates, setItemValidationStates] = useState<{
    [fieldName: string]: ItemValidationResult[];
  }>({});
  const [actionOutputs, setActionOutputs] = useState<Record<string, any>>({});

  const handleInputChange = (field: string, value: any) => {
    setFormData((prev: any) => {
      const next = { ...prev, [field]: value };

      const fieldSchema = schemaProperties?.[field];
      const propagate = fieldSchema?.hints?.propagate;
      if (propagate?.to) {
        next[propagate.to] =
          propagate.value !== undefined && propagate.value !== null
            ? propagate.value
            : value;
      }

      // Re-propagate from any field that just became visible as a result of
      // this change (e.g. a conditionally-visible field with its own
      // propagate hint) — not just the field the user directly edited.
      if (schemaProperties) {
        Object.entries(schemaProperties).forEach(([name, schema]: [string, any]) => {
          const conditional = schema?.hints?.conditional?.visible_when;
          const prop = schema?.hints?.propagate;
          if (!conditional || !prop?.to) return;
          const isVisible = Object.entries(conditional).every(
            ([f, v]) => next[f] === v,
          );
          if (isVisible && next[name]) {
            next[prop.to] =
              prop.value !== undefined && prop.value !== null ? prop.value : next[name];
          }
        });
      }

      return next;
    });
  };

  const handleArrayChange = (field: string, index: number, value: any) => {
    setFormData((prev: any) => ({
      ...prev,
      [field]: prev[field].map((item: any, i: number) => (i === index ? value : item)),
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

  const handleValidationChange = (
    fieldName: string,
    isValid: boolean,
    itemResults?: ItemValidationResult[],
  ) => {
    setFieldValidationStates((prev) => ({ ...prev, [fieldName]: isValid }));
    if (itemResults) {
      setItemValidationStates((prev) => ({ ...prev, [fieldName]: itemResults }));
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
    setActionOutputs((prev) => ({ ...prev, [fieldName]: output }));
  };

  const resetTransientState = () => {
    setFieldValidationStates({});
    setItemValidationStates({});
    setActionOutputs({});
  };

  return {
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
    resetTransientState,
  };
}
