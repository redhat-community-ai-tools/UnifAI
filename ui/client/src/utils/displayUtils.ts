/**
 * Shared display utilities for formatting config values and objects for UI display.
 * Used by ElementData, ElementGrid, and ResourceDetailsModal.
 * 
 * DISPLAY OBJECT PROTOCOL:
 * Objects that should be simplified for display must include a `_display` field
 * containing the display string value. This is the explicit marker that identifies
 * a display object. Example: { id: "abc123", name: "My Doc", _display: "My Doc" }
 */

/**
 * Check if an object is marked as a display object.
 * A display object has an explicit `_display` field.
 */
export const isDisplayObject = (obj: any): boolean => {
  if (!obj || typeof obj !== 'object') return false;
  
  // Explicit marker - preferred method
  if ('_display' in obj) return true;
  
  // Backwards compatibility: known display patterns
  // These legacy patterns should be phased out in favor of explicit _display marker.
  const hasLegacyPattern = ('name' in obj && ('id' in obj || 'value' in obj)) ||
                           ('label' in obj && 'value' in obj);
  return hasLegacyPattern;
};

/**
 * Extract display value from an object.
 * Uses explicit _display field.
 */
export const getDisplayValue = (obj: any): string => {
  if (!obj || typeof obj !== 'object') return String(obj || '');
  
  // Explicit _display marker (required protocol)
  if (obj._display != null) return String(obj._display);

  const displayFields = ['name'];
  for (const field of displayFields) {
    if (obj[field] != null) return String(obj[field]);
  }
  
  // Fallback to id/value
  if (obj.id != null) return String(obj.id);
  if (obj.value != null) return String(obj.value);
  
  return '[Unknown]';
};

/**
 * Extract display value from an item, with optional fallback function for strings.
 * Used for arrays that may contain strings (refs) or objects.
 */
export const getDisplayValueFromItem = (
  item: any, 
  fallbackFn?: (ref: string | any) => string
): string => {
  if (!item) return '';
  
  // If it's a string, use the fallback function if provided
  if (typeof item === 'string') {
    return fallbackFn ? fallbackFn(item) : item;
  }
  
  // If it's an object, extract display value
  if (typeof item === 'object' && item !== null) {
    // Explicit _display marker (required protocol)
    if (item._display != null) return String(item._display);
    
    // If object has $ref, use fallback function
    if (item.$ref && fallbackFn) return fallbackFn(item);
    
    // Use getDisplayValue for other objects to extract name/id/value
    if (isDisplayObject(item)) return getDisplayValue(item);
  } 
  
  return String(item);
};

/**
 * Recursively simplify config objects for display.
 * Converts display objects (marked with _display) to just display names.
 * 
 * NOTE: This function uses isDisplayObject() to determine what should be simplified.
 * Only objects with explicit _display field are simplified.
 */
export const simplifyConfigForDisplay = (config: any): any => {
  if (!config || typeof config !== 'object') return config;
  
  if (Array.isArray(config)) {
    return config.map(item => {
      if (typeof item === 'object' && item !== null) {
        // Check if this is a display object using the protocol
        if (isDisplayObject(item)) {
          return getDisplayValue(item);
        }
      }
      return simplifyConfigForDisplay(item);
    });
  }
  
  // For objects, recursively simplify each property
  const result: any = {};
  for (const [key, value] of Object.entries(config)) {
    result[key] = simplifyConfigForDisplay(value);
  }
  return result;
};
