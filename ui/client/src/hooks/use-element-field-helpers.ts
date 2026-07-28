import { useCallback, useMemo } from "react";
import { getStringEnumFromRef } from "@/components/agentic-ai/workspace/FieldRenderer";

export interface ElementFieldHelpers {
  isFieldConditionallyVisible: (fieldSchema: any) => boolean;
  isArrayWithRefItems: (fieldSchema: any) => boolean;
  getArrayItemsSchema: (fieldSchema: any) => any;
  resolveRef: (ref: string) => any | null;
  isStringEnumRef: (fieldSchema: any) => boolean;
  extractCategoryFromField: (fieldSchema: any) => string | null;
}

/**
 * Shared JSON-schema field helpers for rendering element/resource config
 * forms (`ElementForm`, `BuiltinConfigureModal`). Both forms walk the same
 * Pydantic-derived JSON schema shape (`$ref`/`anyOf`/`hints`), so the
 * $ref-resolution, array-of-ref detection, string-enum, and conditional
 * visibility logic is kept here once rather than duplicated per form.
 */
export function useElementFieldHelpers(
  configSchema: any,
  formData: Record<string, any>,
): ElementFieldHelpers {
  const isFieldConditionallyVisible = useCallback(
    (fieldSchema: any): boolean => {
      const conditions = fieldSchema?.hints?.conditional?.visible_when;
      if (!conditions) return true;
      return Object.entries(conditions).every(
        ([field, requiredValue]) => formData[field] === requiredValue,
      );
    },
    [formData],
  );

  const isArrayWithRefItems = useCallback((fieldSchema: any): boolean => {
    if (fieldSchema?.type === "array" && fieldSchema.items?.$ref) return true;
    if (fieldSchema?.anyOf && Array.isArray(fieldSchema.anyOf)) {
      return fieldSchema.anyOf.some(
        (option: any) => option.type === "array" && option.items?.$ref,
      );
    }
    return false;
  }, []);

  const getArrayItemsSchema = useCallback((fieldSchema: any): any => {
    if (fieldSchema?.type === "array" && fieldSchema.items) return fieldSchema.items;
    if (fieldSchema?.anyOf && Array.isArray(fieldSchema.anyOf)) {
      const arrayOption = fieldSchema.anyOf.find(
        (option: any) => option.type === "array" && option.items,
      );
      return arrayOption?.items ?? null;
    }
    return null;
  }, []);

  const resolveRef = useCallback(
    (ref: string): any | null => {
      if (!ref || typeof ref !== "string" || !ref.startsWith("#/")) return null;
      const pathSegments = ref
        .substring(2)
        .split("/")
        .filter((segment) => segment.length > 0);

      let current: any = configSchema;
      for (const segment of pathSegments) {
        if (!current || typeof current !== "object" || !(segment in current)) {
          return null;
        }
        current = current[segment];
      }
      return current ?? null;
    },
    [configSchema],
  );

  const isStringEnumRef = useCallback(
    (fieldSchema: any): boolean => getStringEnumFromRef(fieldSchema, resolveRef) !== null,
    [resolveRef],
  );

  const extractCategoryFromField = useCallback(
    (fieldSchema: any): string | null => {
      const tryResolve = (ref: string): string | null => {
        const resolved = resolveRef(ref);
        return resolved?.category || null;
      };

      if (fieldSchema?.$ref) {
        const category = tryResolve(fieldSchema.$ref);
        if (category) return category;
      }
      if (fieldSchema?.items?.$ref) {
        const category = tryResolve(fieldSchema.items.$ref);
        if (category) return category;
      }
      if (fieldSchema?.anyOf && Array.isArray(fieldSchema.anyOf)) {
        for (const option of fieldSchema.anyOf) {
          if (option.$ref) {
            const category = tryResolve(option.$ref);
            if (category) return category;
          }
          if (option.type === "array" && option.items?.$ref) {
            const category = tryResolve(option.items.$ref);
            if (category) return category;
          }
        }
      }
      return null;
    },
    [resolveRef],
  );

  return useMemo(
    () => ({
      isFieldConditionallyVisible,
      isArrayWithRefItems,
      getArrayItemsSchema,
      resolveRef,
      isStringEnumRef,
      extractCategoryFromField,
    }),
    [
      isFieldConditionallyVisible,
      isArrayWithRefItems,
      getArrayItemsSchema,
      resolveRef,
      isStringEnumRef,
      extractCategoryFromField,
    ],
  );
}
