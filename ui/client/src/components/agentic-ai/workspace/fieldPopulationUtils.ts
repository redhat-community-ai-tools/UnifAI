/**
 * Utility functions for FieldPopulation component.
 * Handles normalizing API results into a consistent option format.
 */

import { resolvePath } from './arrayFieldHelpers';

export interface OptionItem {
  label: string;         // Display name (e.g., "My Document")
  value: string;         // Internal ID for deduplication (e.g., "abc123")
  originalObject: any;   // Full object from API (preserved but not used for storage)
}

/**
 * Extract the display name from an object.
 * Uses displayField path if provided by the populateHint contract.
 * 
 * IMPORTANT: We strictly follow the BE-GUI protocol - the backend MUST specify
 * display_field/label_field in the populateHint. If not specified, we use the
 * value field as the display (shows the ID/value as-is).
 */
const extractDisplayName = (obj: any, displayField?: string): string => {
  if (!obj) return '';
  if (typeof obj === 'string') return obj;
  if (typeof obj !== 'object') return String(obj);

  // Use displayField path from populateHint contract
  if (displayField) {
    const val = resolvePath(obj, displayField);
    if (val != null) return String(val);
  }

  // No fallbacks - if displayField not specified, return stringified object
  // This ensures backend must properly configure the populateHint
  return JSON.stringify(obj);
};

/**
 * Extract the unique ID/value from an object.
 * Uses valueField path if provided by the populateHint contract.
 * 
 * IMPORTANT: We strictly follow the BE-GUI protocol - the backend MUST specify
 * value_field in the populateHint for object items. If not specified, we
 * use the stringified object as the value (which will likely cause issues,
 * making it obvious the backend needs to configure the hint properly).
 */
const extractId = (obj: any, valueField?: string): string => {
  if (!obj) return '';
  if (typeof obj === 'string') return obj;
  if (typeof obj !== 'object') return String(obj);

  // Use valueField path from populateHint contract
  if (valueField) {
    const val = resolvePath(obj, valueField);
    if (val != null) return String(val);
  }

  // No fallbacks - if valueField not specified, return stringified object
  // This ensures backend must properly configure the populateHint
  return JSON.stringify(obj);
};

/**
 * Normalize raw API results into OptionItem format.
 * Handles both string arrays and object arrays.
 */
export const normalizeOptions = (
  items: any[],
  displayField?: string,
  valueField?: string
): OptionItem[] => {
  if (!items || !Array.isArray(items)) return [];

  return items.map(item => {
    if (typeof item === 'string') {
      return { label: item, value: item, originalObject: item };
    }

    if (typeof item === 'object' && item !== null) {
      return {
        label: extractDisplayName(item, displayField),
        value: extractId(item, valueField),
        originalObject: item
      };
    }

    return { label: String(item), value: String(item), originalObject: item };
  });
};
