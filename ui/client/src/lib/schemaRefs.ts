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
    if (!current || typeof current !== "object" || !(segment in current)) return null;
    current = current[segment];
  }
  return current;
}
