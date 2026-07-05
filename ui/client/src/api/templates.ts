import axios from '@/http/axiosAgentConfig';
import {
  TemplatesListResponse,
  TemplateDetail,
  TemplateInputSchema,
  ValidationResponse,
  MaterializeResponse
} from '@/types/templates';

// ────────────────────────────────────────────────────────────────────────────────
// Template List & Detail Operations
// ────────────────────────────────────────────────────────────────────────────────

export interface ListTemplatesParams {
  isPublic?: boolean;
  category?: string;
  tags?: string;
  skip?: number;
  limit?: number;
}

/**
 * List available templates with optional filtering
 * GET /templates/templates.list
 */
export async function listTemplates(params?: ListTemplatesParams): Promise<TemplatesListResponse> {
  const response = await axios.get<TemplatesListResponse>('/templates/templates.list', {
    params
  });
  return response.data;
}

/**
 * Get full template details including blueprint draft and placeholders
 * GET /templates/template.get
 */
export async function getTemplate(templateId: string): Promise<TemplateDetail> {
  const response = await axios.get<TemplateDetail>('/templates/template.get', {
    params: { templateId }
  });
  return response.data;
}

/**
 * Get JSON Schema for template input fields
 * GET /templates/template.schema.get
 */
export async function getTemplateSchema(templateId: string): Promise<TemplateInputSchema> {
  const response = await axios.get<TemplateInputSchema>('/templates/template.schema.get', {
    params: { templateId }
  });
  return response.data;
}
export interface CreateTemplateParams {
  draft: Record<string, any>;
  placeholders: Record<string, any>;
  metadata?: Record<string, any>;
}

export interface CreateTemplateResponse {
  status: string;
  template_id: string;
}

/**
 * Create a new template (admin only)
 * POST /templates/template.create
 */
export async function createTemplate(params: CreateTemplateParams, userId: string): Promise<CreateTemplateResponse> {
  const response = await axios.post<CreateTemplateResponse>('/templates/template.create', params, {
    params: { userId },
  });
  return response.data;
}

export interface DeleteTemplateResponse {
  status: string;
  message: string;
}

/**
 * Delete a template by ID (admin only)
 * DELETE /templates/template.delete
 */
export async function deleteTemplate(templateId: string, userId: string): Promise<DeleteTemplateResponse> {
  const response = await axios.delete<DeleteTemplateResponse>('/templates/template.delete', {
    params: { templateId, userId }
  });
  return response.data;
}

// ────────────────────────────────────────────────────────────────────────────────
// Template Validation & Materialization
// ────────────────────────────────────────────────────────────────────────────────

export interface ValidateInputParams {
  templateId: string;
  input: Record<string, Record<string, Record<string, any>>>;
}

/**
 * Validate template input before materialization
 * POST /templates/template.input.validate
 */
export async function validateTemplateInput(params: ValidateInputParams): Promise<ValidationResponse> {
  const response = await axios.post<ValidationResponse>('/templates/template.input.validate', params);
  return response.data;
}

export interface MaterializeParams {
  templateId: string;
  userId: string;
  input: Record<string, Record<string, Record<string, any>>>;
  blueprintName?: string;
  skipValidation?: boolean;
}

/**
 * Materialize a template into a usable blueprint
 * POST /templates/template.materialize
 */
export async function materializeTemplate(params: MaterializeParams): Promise<MaterializeResponse> {
  const response = await axios.post<MaterializeResponse>('/templates/template.materialize', params);
  return response.data;
}

