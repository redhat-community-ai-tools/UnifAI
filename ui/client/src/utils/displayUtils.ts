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

/**
 * Strip fields marked `hints.hidden` (see `field_hints.py#HiddenHint`) out of
 * a config object before it's rendered in a "Full Configuration" details
 * dump. These are internal/auth-flow bookkeeping fields (e.g.
 * `server_identifier`, `scheme_type`, `credential_token`) that every other
 * config-consuming surface (form population, validation, save payloads —
 * see `ElementForm.tsx`, `BuiltinConfigureModal.tsx`) already treats as
 * "never shown to the user", so the raw JSON dump must honor the same
 * contract instead of leaking them back in.
 */
export const filterHiddenFieldsInConfig = (
  config: any,
  schema?: { properties?: { [key: string]: any } },
): any => {
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    return config;
  }

  const filtered: any = {};
  for (const [key, value] of Object.entries(config)) {
    const fieldSchema = schema?.properties?.[key];
    if (fieldSchema?.hints?.hidden?.hint_type === 'hidden') continue;

    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      filtered[key] = filterHiddenFieldsInConfig(value, schema);
    } else {
      filtered[key] = value;
    }
  }
  return filtered;
};

/**
 * Keep only the given top-level field names on a config object. Used
 * alongside `getBuiltinVisibleFieldNames` to reduce a built-in element's
 * "Full Configuration" dump down to just its configurable + card-visible
 * fields, dropping locked admin-only setup (e.g. an MCP server's
 * `mcp_url`) that a regular user was never meant to see.
 */
export const filterToFieldNames = (config: any, allowed: Set<string>): any => {
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    return config;
  }

  const filtered: any = {};
  for (const key of Object.keys(config)) {
    if (allowed.has(key)) filtered[key] = config[key];
  }
  return filtered;
};
