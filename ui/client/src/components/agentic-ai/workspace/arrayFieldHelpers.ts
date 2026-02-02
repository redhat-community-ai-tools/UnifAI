/**
 * Helper utilities for array field rendering in FieldRenderer.
 * Extracts display logic and helper functions for cleaner code organization.
 */

/**
 * Resolve dot-notation path on an object (e.g., "name.x" -> obj.name.x)
 */
export const resolvePath = (obj: any, path: string): any => {
  if (!obj || !path) return undefined;
  const parts = path.split('.');
  let current = obj;
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined;
    current = current[part];
  }
  return current;
};

/**
 * Get display label for an array item based on populateHint display_field
 */
export const getItemLabel = (item: any, displayFieldPath: string | undefined): string => {
  if (item == null) return '';
  if (typeof item === 'string') return item;
  if (typeof item === 'object') {
    // Use display_field path from populateHint contract (supports dot-notation)
    // IMPORTANT: We strictly follow the BE-GUI protocol - backend MUST specify display_field
    if (displayFieldPath) {
      const val = resolvePath(item, displayFieldPath);
      if (val != null && typeof val !== 'object') {
        return String(val);
      }
    }
    // No fallbacks - if display_field not configured, show stringified object
    // This makes it obvious the backend needs to configure the hint properly
    return JSON.stringify(item);
  }
  return String(item);
};

/**
 * Get display text for array values (comma-separated labels)
 */
export const getArrayDisplayText = (value: any, displayFieldPath: string | undefined): string => {
  if (!value) return '';
  if (Array.isArray(value)) {
    if (value.length === 0) return '';
    return value.map(item => getItemLabel(item, displayFieldPath)).join(', ');
  }
  return getItemLabel(value, displayFieldPath);
};

/**
 * Array field mode types, with dynamic meaning the array can contain different types
 */
export type ArrayFieldMode = 'refItems' | 'dynamic' | 'regular';

/**
 * Determine the array field rendering mode based on schema and hints
 */
export const getArrayFieldMode = (
  isArrayWithRefItems: boolean,
  hasDynamicHint: boolean,
  isDirectArrayType: boolean
): ArrayFieldMode | null => {
  if (isArrayWithRefItems) return 'refItems';
  if (hasDynamicHint) return 'dynamic';
  if (isDirectArrayType) return 'regular';
  return null;
};

/**
 * Get valid options for ref-based array fields
 */
export const getValidRefOptions = (
  refOptions: { [category: string]: any[] },
  category: string | null
): any[] => {
  if (!category) return [];
  return (refOptions[category] || []).filter(
    (option: any) => option.rid && option.rid.trim() !== "",
  );
};

