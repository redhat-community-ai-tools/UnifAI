import React from "react";
import { FieldRenderer } from "./FieldRenderer";
import { ElementType, ElementInstance } from "../../../types/workspace";
import { ElementFieldHelpers } from "@/hooks/use-element-field-helpers";
import { ConfigFieldActions } from "@/hooks/use-config-field-actions";

interface ElementConfigFieldProps {
  fieldName: string;
  fieldSchema: any;
  isRequired: boolean;
  editingElement: ElementInstance | null;
  elementActions: any[];
  elementType: ElementType;
  refOptions: { [category: string]: any[] };
  fieldHelpers: Pick<
    ElementFieldHelpers,
    "isArrayWithRefItems" | "getArrayItemsSchema" | "extractCategoryFromField" | "resolveRef"
  >;
  fieldActions: Pick<
    ConfigFieldActions,
    | "formData"
    | "fieldValidationStates"
    | "itemValidationStates"
    | "actionOutputs"
    | "handleInputChange"
    | "handleArrayChange"
    | "addArrayItem"
    | "removeArrayItem"
    | "handleValidationChange"
    | "handlePopulateResult"
    | "handleActionOutput"
  >;
  /** Only relevant for forms that allow editing a $ref'd resource inline (`ElementForm`). */
  onEditRefElement?: (rid: string) => void;
}

/**
 * Wraps `FieldRenderer` with the validation/populate-hint derivation and
 * prop wiring shared by every resource config form (`ElementForm`,
 * `BuiltinConfigureModal`) — keeps that logic in one place instead of
 * reimplementing it per form.
 */
export const ElementConfigField: React.FC<ElementConfigFieldProps> = ({
  fieldName,
  fieldSchema,
  isRequired,
  editingElement,
  elementActions,
  elementType,
  refOptions,
  fieldHelpers,
  fieldActions,
  onEditRefElement,
}) => {
  const value = fieldActions.formData[fieldName] ?? "";

  const actionValidationHint =
    fieldSchema.hints?.action?.hint_type === "validate" ? fieldSchema.hints.action : null;
  const apiValidationHint =
    fieldSchema.hints?.api?.hint_type === "validate" ? fieldSchema.hints.api : null;
  const validationHint = actionValidationHint || apiValidationHint;

  const actionPopulateHint =
    fieldSchema.hints?.action?.hint_type === "populate" ? fieldSchema.hints.action : null;
  const apiPopulateHint =
    fieldSchema.hints?.api?.hint_type === "populate" ? fieldSchema.hints.api : null;
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
      formData={fieldActions.formData}
      refOptions={refOptions}
      fieldType={isSecret ? "secret" : "public"}
      fieldValidationStates={fieldActions.fieldValidationStates}
      itemValidationStates={fieldActions.itemValidationStates}
      actionOutputs={fieldActions.actionOutputs}
      isArrayWithRefItems={fieldHelpers.isArrayWithRefItems}
      getArrayItemsSchema={fieldHelpers.getArrayItemsSchema}
      extractCategoryFromField={fieldHelpers.extractCategoryFromField}
      resolveSchemaRef={fieldHelpers.resolveRef}
      onInputChange={fieldActions.handleInputChange}
      onArrayChange={fieldActions.handleArrayChange}
      onAddArrayItem={fieldActions.addArrayItem}
      onRemoveArrayItem={fieldActions.removeArrayItem}
      onValidationChange={fieldActions.handleValidationChange}
      onPopulateResult={fieldActions.handlePopulateResult}
      onActionOutput={fieldActions.handleActionOutput}
      onEditRefElement={onEditRefElement}
    />
  );
};
