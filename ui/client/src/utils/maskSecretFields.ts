export const maskSecretValue = (value: any, fieldSchema: any): string => {
  const maskChar = fieldSchema?.hints?.secret?.mask_char || "•";
  
  if (typeof value === 'string') {
    return maskChar.repeat(value.length);
  }
  
  return maskChar.repeat(8);
};


export const maskSecretFieldsInConfig = (config: any, schema?: { properties?: { [key: string]: any } }): any => {
  if (!config || typeof config !== 'object') {
    return config;
  }

  const masked: any = {};
  
  for (const [key, value] of Object.entries(config)) {
    const fieldSchema = schema?.properties?.[key];
    
    // Only mask if explicitly marked as secret in schema
    if (fieldSchema?.hints?.secret?.hint_type === "secret") {
      masked[key] = maskSecretValue(value, fieldSchema);
    } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      // Recursively mask nested objects
      masked[key] = maskSecretFieldsInConfig(value, schema);
    } else {
      masked[key] = value;
    }
  }
  
  return masked;
};

export const formatConfigValue = (
  value: any,
  fieldSchema?: any,
  maxLength: number = 15
): string => {
  // Only mask if explicitly marked as secret in schema
  if (fieldSchema?.hints?.secret?.hint_type === "secret") {
    return maskSecretValue(value, fieldSchema);
  }
  
  if (typeof value === 'string') {
    if (value.length > maxLength) {
      return value.slice(0, maxLength) + '...';
    }
    return value;
  }
  
  if (typeof value === 'object' && value !== null) {
    return '[Object]';
  }
  
  return String(value);
};

