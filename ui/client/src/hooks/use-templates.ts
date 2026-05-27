import { useState, useCallback } from 'react';
import { 
  TemplateListItem,
  TemplateDetail,
  TemplateInputSchema,
  NormalizedField,
  MaterializeResponse,
  InstantiationStatus,
  TemplateCategory,
  TemplateFormData,
  SchemaFieldProperty,
  ValidationError
} from '../types/templates';
import { 
  listTemplates,
  getTemplate,
  getTemplateSchema,
  validateTemplateInput,
  materializeTemplate
} from '../api/templates';
import { useToast } from './use-toast';
import { ElementValidationResult, ValidationMessage } from '../types/validation';

interface UseTemplatesReturn {
  templates: TemplateListItem[];
  selectedTemplate: TemplateListItem | null;
  templateDetail: TemplateDetail | null;
  templateSchema: TemplateInputSchema | null;
  normalizedFields: NormalizedField[];
  isLoading: boolean;
  error: string | null;
  validationErrors: ValidationError[];
  instantiationStatus: InstantiationStatus;
  instantiationResult: MaterializeResponse | null;
  fetchTemplates: (category?: string, tags?: string) => Promise<TemplateListItem[] | null>;
  fetchTemplateDetail: (templateId: string) => Promise<{ detail: TemplateDetail; schema: TemplateInputSchema } | null>;
  materialize: (templateId: string, formData: TemplateFormData, blueprintName?: string) => Promise<MaterializeResponse | null>;
  resetInstantiation: () => void;
  getCategories: () => TemplateCategory[];
  setSelectedTemplate: (template: TemplateListItem | null) => void;
  buildInputPayload: (formData: TemplateFormData) => Record<string, Record<string, Record<string, any>>>;
  getValidationResults: () => ElementValidationResult[];
}

/**
 * Resolves a $ref path in JSON Schema $defs
 */
function resolveRef(ref: string, defs: Record<string, any>): any {
  const path = ref.replace('#/$defs/', '');
  return defs[path];
}

/**
 * Normalize JSON Schema into flat field list for UI rendering
 */
function normalizeSchemaToFields(
  schema: TemplateInputSchema
): NormalizedField[] {
  const fields: NormalizedField[] = [];
  const defs = schema.$defs || {};

  // Iterate over top-level properties (categories like "llms", "tools", "nodes")
  for (const [category, categoryProp] of Object.entries(schema.properties)) {
    // Resolve the category definition
    const categoryDef = categoryProp.$ref 
      ? resolveRef(categoryProp.$ref, defs) 
      : categoryProp;

    if (!categoryDef?.properties) continue;

    // Iterate over resources within the category
    for (const [resourceRid, resourceProp] of Object.entries(categoryDef.properties as Record<string, SchemaFieldProperty>)) {
      // Resolve the resource definition
      const resourceDef = resourceProp.$ref 
        ? resolveRef(resourceProp.$ref, defs) 
        : resourceProp;

      if (!resourceDef?.properties) continue;

      const resourceRequired = resourceDef.required || [];

      // Iterate over fields within the resource
      for (const [fieldPath, fieldProp] of Object.entries(resourceDef.properties as Record<string, SchemaFieldProperty>)) {
        const field = fieldProp as SchemaFieldProperty;
        const isRequired = resourceRequired.includes(fieldPath);
        const hints = field.hints || {};

        // Determine field type based on schema type and hints
        let fieldType: NormalizedField['type'] = 'string';
        if (hints.secret) {
          fieldType = 'secret';
        } else if (field.type === 'boolean') {
          fieldType = 'boolean';
        } else if (field.type === 'number' || field.type === 'integer') {
          fieldType = 'number';
        } else if (field.type === 'array') {
          fieldType = 'array';
        } else if (field.enum && field.enum.length > 0) {
          fieldType = 'enum';
        }

        fields.push({
          category,
          resourceRid,
          fieldPath,
          key: `${category}.${resourceRid}.${fieldPath}`,
          label: field.title || fieldPath,
          description: field.description,
          type: fieldType,
          required: isRequired,
          default: field.default,
          pattern: field.pattern,
          minLength: field.minLength,
          maxLength: field.maxLength,
          minimum: field.minimum,
          maximum: field.maximum,
          enumOptions: field.enum,
          isSecret: hints.secret?.hint_type === 'secret',
          isMultiline: hints.multiline?.hint_type === 'multiline'
        });
      }
    }
  }

  return fields;
}

/**
 * Build the input payload structure required by the backend API
 * Structure: { category: { resourceRid: { fieldPath: value } } }
 */
function buildInputPayloadFromFields(
  formData: TemplateFormData,
  normalizedFields: NormalizedField[]
): Record<string, Record<string, Record<string, any>>> {
  const input: Record<string, Record<string, Record<string, any>>> = {};

  for (const field of normalizedFields) {
    const value = formData[field.key];
    
    // Skip only undefined/null values; empty string may be intentional
    if (value === undefined || value === null) {
      continue;
    }
    
    // Skip empty arrays
    if (Array.isArray(value) && value.length === 0) {
      continue;
    }

    // Initialize nested structure if needed
    if (!input[field.category]) {
      input[field.category] = {};
    }
    if (!input[field.category][field.resourceRid]) {
      input[field.category][field.resourceRid] = {};
    }

    input[field.category][field.resourceRid][field.fieldPath] = value;
  }

  return input;
}

export const useTemplates = (): UseTemplatesReturn => {
  const [templates, setTemplates] = useState<TemplateListItem[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateListItem | null>(null);
  const [templateDetail, setTemplateDetail] = useState<TemplateDetail | null>(null);
  const [templateSchema, setTemplateSchema] = useState<TemplateInputSchema | null>(null);
  const [normalizedFields, setNormalizedFields] = useState<NormalizedField[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [elementValidationResults, setElementValidationResults] = useState<ElementValidationResult[]>([]);
  const [instantiationStatus, setInstantiationStatus] = useState<InstantiationStatus>('idle');
  const [instantiationResult, setInstantiationResult] = useState<MaterializeResponse | null>(null);
  const { toast } = useToast();

  /**
   * Get validation results for display in the UI
   * Returns ElementValidationResult[] from various error sources
   */
  const getValidationResults = useCallback((): ElementValidationResult[] => {
    if (elementValidationResults.length > 0) {
      return elementValidationResults;
    }

    // Handle structured validation errors (from template.input.validate)
    if (validationErrors.length > 0) {
      return [{
        is_valid: false,
        element_rid: selectedTemplate?.template_id || 'unknown',
        element_type: 'template_input',
        name: selectedTemplate?.name || 'Template Input',
        messages: validationErrors.map(err => ({
          severity: 'error' as const,
          code: 'MISSING_REQUIRED_FIELD' as const,
          message: err.message,
          field: err.field
        })),
        dependency_results: {}
      }];
    }

    // If we have a generic error but no structured validation errors
    if (error) {
      return [{
        is_valid: false,
        element_rid: selectedTemplate?.template_id || 'unknown',
        element_type: 'template',
        name: selectedTemplate?.name || 'Template',
        messages: [{
          severity: 'error' as const,
          code: 'NETWORK_ERROR' as const,
          message: error,
          field: null
        }],
        dependency_results: {}
      }];
    }

    return [];
  }, [error, validationErrors, elementValidationResults, selectedTemplate]);

  const fetchTemplates = useCallback(async (category?: string, tags?: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await listTemplates({ category, tags });
      setTemplates(response.templates);
      return response.templates;
    } catch (err: any) {
      const errorMessage = err.response?.data?.error || 'Failed to fetch templates';
      setError(errorMessage);
      toast({
        title: 'Error',
        description: errorMessage,
        variant: 'destructive'
      });
      console.error('Error fetching templates:', err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  const fetchTemplateDetail = useCallback(async (templateId: string) => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch both template detail and schema in parallel
      const [detail, schema] = await Promise.all([
        getTemplate(templateId),
        getTemplateSchema(templateId)
      ]);

      setTemplateDetail(detail);
      setTemplateSchema(schema);

      // Normalize schema fields for UI rendering
      const fields = normalizeSchemaToFields(schema);
      setNormalizedFields(fields);

      // Update selected template with detail info
      setSelectedTemplate({
        template_id: detail.template_id,
        name: detail.draft.name || detail.template_id,
        description: detail.draft.description || '',
        category: detail.metadata.category,
        version: detail.metadata.version,
        tags: detail.metadata.tags,
        output_capabilities: detail.metadata.output_capabilities,
        author: detail.metadata.author,
        placeholder_count: fields.length
      });

      return { detail, schema };
    } catch (err: any) {
      const errorMessage = err.response?.data?.error || 'Failed to fetch template details';
      setError(errorMessage);
      toast({
        title: 'Error',
        description: errorMessage,
        variant: 'destructive'
      });
      console.error('Error fetching template details:', err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  const buildInputPayload = useCallback((formData: TemplateFormData) => {
    return buildInputPayloadFromFields(formData, normalizedFields);
  }, [normalizedFields]);

  const materialize = useCallback(async (
    templateId: string,
    formData: TemplateFormData,
    blueprintName?: string
  ): Promise<MaterializeResponse | null> => {
    try {
      setInstantiationStatus('validating');
      setError(null);

      // Build the input payload in the correct structure
      const input = buildInputPayloadFromFields(formData, normalizedFields);

      // First validate the input
      const validationResult = await validateTemplateInput({
        templateId,
        input
      });

      if (!validationResult.is_valid) {
        const errorMessages = validationResult.errors
          .map(e => `${e.field}: ${e.message}`)
          .join('\n');
        
        setError(errorMessages);
        setValidationErrors(validationResult.errors);
        setInstantiationStatus('failed');
        
        toast({
          title: 'Validation Failed',
          description: validationResult.errors[0]?.message || 'Please check your input',
          variant: 'destructive'
        });
        
        return null;
      }

      setInstantiationStatus('submitting');

      const result = await materializeTemplate({
        templateId,
        input,
        blueprintName
      });

      setInstantiationStatus('completed');
      setInstantiationResult(result);

      toast({
        title: 'Success',
        description: `Blueprint "${result.name}" created successfully!`
      });

      return result;
    } catch (err: any) {
      const errorMessage = err.response?.data?.error || 'Failed to materialize template';
      const errorData = err.response?.data;
      
      setError(errorMessage);
      setInstantiationStatus('failed');
      
      // Capture element validation results directly (already in ElementValidationResult format)
      if (errorData?.errors && Array.isArray(errorData.errors)) {
        setElementValidationResults(errorData.errors as ElementValidationResult[]);
      }
      
      toast({
        title: 'Error',
        description: errorMessage,
        variant: 'destructive'
      });
      
      console.error('Error materializing template:', err);
      return null;
    }
  }, [normalizedFields, toast]);

  const resetInstantiation = useCallback(() => {
    setInstantiationStatus('idle');
    setInstantiationResult(null);
    setError(null);
    setValidationErrors([]);
    setElementValidationResults([]);
  }, []);

  const getCategories = useCallback((): TemplateCategory[] => {
    const categoryMap = new Map<string, number>();
    templates.forEach(template => {
      const count = categoryMap.get(template.category) || 0;
      categoryMap.set(template.category, count + 1);
    });
    return Array.from(categoryMap.entries()).map(([name, count]) => ({ name, count }));
  }, [templates]);

  return {
    templates,
    selectedTemplate,
    templateDetail,
    templateSchema,
    normalizedFields,
    isLoading,
    error,
    validationErrors,
    instantiationStatus,
    instantiationResult,
    fetchTemplates,
    fetchTemplateDetail,
    materialize,
    resetInstantiation,
    getCategories,
    setSelectedTemplate,
    buildInputPayload,
    getValidationResults
  };
};

export default useTemplates;
