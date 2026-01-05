/**
 * Validation API Response Types
 */

// Severity levels for validation messages
export type ValidationSeverity = 'error' | 'warning' | 'info';

// All possible validation codes
export type ValidationCode =
  // Network codes
  | 'CONNECTION_OK'
  | 'ENDPOINT_UNREACHABLE'
  | 'NETWORK_TIMEOUT'
  | 'NETWORK_ERROR'
  // Dependency codes
  | 'ALL_DEPENDENCIES_VALID'
  | 'DEPENDENCY_INVALID'
  | 'DEPENDENCY_NOT_FOUND'
  | 'DEPENDENCY_NOT_VALIDATED'
  | 'NO_DEPENDENCIES'
  | 'DEPENDENCIES_NOT_RESOLVED'
  // Configuration codes
  | 'INVALID_CREDENTIALS'
  | 'MISSING_REQUIRED_FIELD'
  // Status codes
  | 'NO_VALIDATOR'
  | 'VALIDATION_SKIPPED';

/**
 * A single validation message within an element result
 */
export interface ValidationMessage {
  /** Severity level: error, warning, or info */
  severity: ValidationSeverity;
  /** Machine-readable code for the validation finding */
  code: ValidationCode;
  /** Human-readable description suitable for display */
  message: string;
  /** Config field that triggered this message (optional) */
  field: string | null;
}

/**
 * The result of validating a single element (resource)
 */
export interface ElementValidationResult {
  /** true if no ERROR messages, false otherwise */
  is_valid: boolean;
  /** Unique identifier of the resource */
  element_rid: string;
  /** Type of element (e.g., mcp_server, custom_agent_node) */
  element_type: string;
  /** Display name for the resource (user-provided) */
  name: string | null;
  /** Array of validation findings */
  messages: ValidationMessage[];
  /** Map of rid → ElementValidationResult for checked dependencies */
  dependency_results: Record<string, ElementValidationResult>;
}

/**
 * The result of validating an entire blueprint
 */
export interface BlueprintValidationResult {
  /** The validated blueprint's ID */
  blueprint_id: string;
  /** true only if ALL elements passed validation */
  is_valid: boolean;
  /** Map of element rid → ElementValidationResult */
  element_results: Record<string, ElementValidationResult>;
}

/**
 * Request payload for resource validation
 */
export interface ResourceValidationRequest {
  resourceId: string;
  skipNetworkChecks?: boolean;
  timeoutSeconds?: number;
}

/**
 * Request payload for blueprint validation
 */
export interface BlueprintValidationRequest {
  blueprintId: string;
  skipNetworkChecks?: boolean;
  timeoutSeconds?: number;
}

/**
 * Cached validation entry with timestamp for potential TTL usage
 */
export interface CachedValidationResult {
  result: ElementValidationResult;
  timestamp: number;
}

