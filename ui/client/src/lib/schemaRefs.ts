/**
 * Resolve a JSON Schema `$ref` pointer (e.g. "#/$defs/McpAuthMethod") against
 * a root schema object (typically an `ElementSchema.config_schema`, which
 * carries its own `$defs`).
 *
 * `ElementForm.tsx` and `BuiltinConfigureModal.tsx` each keep their own
 * closure-scoped `resolveRef` for this because they resolve against
 * component state (`elementSchema` / `builtinSchema`) and layer on extra
 * form-editing concerns (category extraction for $ref dropdowns, etc.).
 * This standalone version is for read-only consumers — like card field
 * rendering — that just need to look up a `$defs` entry from an explicit
 * schema object, without pulling in that machinery.
 */
export function resolveSchemaRef(rootSchema: any, ref: string): any | null {
  if (!ref || typeof ref !== "string" || !ref.startsWith("#/")) return null;
  const segments = ref.substring(2).split("/").filter((s) => s.length > 0);
  let current: any = rootSchema;
  for (const segment of segments) {
    if (!current || typeof current !== "object" || !Object.prototype.hasOwnProperty.call(current, segment)) {
      return null;
    }
    current = current[segment];
  }
  return current;
}

/**
 * Evaluates a single `visible_when` entry. `requiredValue` is either a plain
 * scalar (exact match) or an operator object — `{"in": [...]}` / `{"not_in":
 * [...]}` — as documented on the backend's `ConditionalHint` (see
 * `mas/core/field_hints.py`). Open-ended fields like A2A's `auth_method`
 * (populated dynamically from the auth server registry) can't be gated with
 * a scalar match, hence `not_in`.
 */
export function matchesCondition(actualValue: any, requiredValue: any): boolean {
  if (requiredValue && typeof requiredValue === "object" && !Array.isArray(requiredValue)) {
    if (Array.isArray(requiredValue.in)) return requiredValue.in.includes(actualValue);
    if (Array.isArray(requiredValue.not_in)) return !requiredValue.not_in.includes(actualValue);
    return false;
  }
  return actualValue === requiredValue;
}

/**
 * Evaluates a field's `hints.conditional.visible_when` against the current
 * form/config values. A field with no conditional hint is always visible.
 * Shared by `use-element-field-helpers.ts` (form rendering) and
 * `cardFields.ts` (read-only card rendering) so both agree on what
 * "conditionally visible" means.
 */
export function isFieldConditionallyVisible(
  fieldSchema: any,
  values: Record<string, any>,
): boolean {
  const conditions = fieldSchema?.hints?.conditional?.visible_when;
  if (!conditions) return true;
  return Object.entries(conditions).every(
    ([field, requiredValue]) => matchesCondition(values?.[field], requiredValue),
  );
}

/** Resolved string enum definition from `$defs`. */
export interface ResolvedStringEnum {
  type: "string";
  enum: string[];
  title?: string;
  description?: string;
}

/**
 * Checks if a $ref (pydantic mode) resolves to a string enum definition.
 * Returns the resolved enum definition if found, null otherwise.
 */
export const getStringEnumFromRef = (
  fieldSchema: any,
  resolveRef?: (ref: string) => any | null,
): ResolvedStringEnum | null => {
  if (!resolveRef || !fieldSchema?.$ref) {
    return null;
  }

  const resolved = resolveRef(fieldSchema.$ref);
  if (!resolved) {
    return null;
  }

  if (resolved.type === "string" && Array.isArray(resolved.enum) && resolved.enum.length > 0) {
    return {
      type: "string",
      enum: resolved.enum,
      title: resolved.title,
      description: resolved.description,
    };
  }

  return null;
};
