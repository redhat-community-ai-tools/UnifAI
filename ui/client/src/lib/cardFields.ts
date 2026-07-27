import { ElementSchema } from "@/types/workspace";
import { formatConfigValue } from "@/utils/maskSecretFields";
import { resolveSchemaRef } from "@/lib/schemaRefs";
import { getStringEnumFromRef } from "@/components/agentic-ai/workspace/FieldRenderer";

export interface CardField {
  /** Config field name, e.g. "mcp_url" */
  key: string;
  /** Human-readable label, e.g. "MCP URL" */
  label: string;
  /** Pre-formatted, display-ready value */
  value: string;
}

const MAX_CARD_VALUE_LENGTH = 60;

/**
 * Words that should render fully upper-cased when humanizing a field name
 * (e.g. `mcp_url` -> "MCP URL" instead of "Mcp Url"). Only used as a
 * fallback when the schema doesn't provide an explicit `title`.
 */
const ACRONYMS = new Set([
  "url", "api", "id", "llm", "mcp", "tls", "ssl", "hitl", "cwd", "ca",
  "a2a", "rag", "ip", "dns", "uid", "uuid", "http", "https",
]);

function isEmptyValue(value: any): boolean {
  if (value === undefined || value === null) return true;
  if (typeof value === "string") return value.trim() === "";
  if (Array.isArray(value)) return value.length === 0;
  return false;
}

function isConditionallyVisible(fieldSchema: any, config: Record<string, any>): boolean {
  const conditions = fieldSchema?.hints?.conditional?.visible_when;
  if (!conditions) return true;
  return Object.entries(conditions).every(([field, requiredValue]) => config?.[field] === requiredValue);
}

function humanizeFieldName(fieldName: string): string {
  return fieldName
    .split("_")
    .filter(Boolean)
    .map((word) => {
      if (ACRONYMS.has(word.toLowerCase())) return word.toUpperCase();
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
}

function resolveLabel(fieldName: string, fieldSchema: any): string {
  return fieldSchema?.title || humanizeFieldName(fieldName);
}

/**
 * Format a single array item for card display. Items that are plain
 * strings/numbers fall through to `formatConfigValue`. Items that are
 * objects (e.g. a selected document `{id, name}` from a populate action)
 * are reduced to their display name instead of the generic `[Object]`
 * placeholder, so multi-select reference fields (docs, etc.) read as a
 * human list rather than opaque blobs.
 */
function formatArrayItem(item: any): string {
  if (item && typeof item === "object" && !Array.isArray(item)) {
    const displayValue = item.name ?? item.title ?? item.label ?? item.id;
    if (displayValue !== undefined && displayValue !== null) {
      return formatConfigValue(String(displayValue), undefined, MAX_CARD_VALUE_LENGTH);
    }
  }
  return formatConfigValue(item, undefined, MAX_CARD_VALUE_LENGTH);
}

function formatValue(value: any, fieldSchema: any, configSchema: any): string {
  if (Array.isArray(value)) {
    const items = value.map(formatArrayItem);
    return items.join(", ");
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  // Named Enum classes (e.g. McpAuthMethod) serialize as a `$ref` to a
  // `$defs` entry rather than an inline `enum` list on the field itself.
  // Confirming the field is actually a string enum (vs. a resource `$ref`)
  // before humanizing avoids mangling arbitrary free-text/URL values that
  // happen to also be strings.
  if (typeof value === "string" && fieldSchema?.$ref) {
    const stringEnum = getStringEnumFromRef(fieldSchema, (ref: string) => resolveSchemaRef(configSchema, ref));
    if (stringEnum) {
      return humanizeFieldName(value);
    }
  }

  return formatConfigValue(value, fieldSchema, MAX_CARD_VALUE_LENGTH);
}

/**
 * Determine which config fields should render on an element's inventory
 * card, and in what display form.
 *
 * Opt-in only: a field is included only when its schema carries
 * `hints.card.contexts` including the current `ownership`. Fields marked
 * `hints.secret` are *never* included, even if also marked with a card
 * hint — that exclusion is a hard rule enforced here, not left to the
 * schema authors. Fields hidden via `hints.hidden`, conditionally hidden
 * via `hints.conditional.visible_when`, or resolving to an empty value are
 * skipped as well — unless the card hint declares `empty_text`, in which
 * case that fallback text is shown instead of dropping the field.
 */
export function getCardFields(
  schema: ElementSchema | null | undefined,
  config: Record<string, any> | null | undefined,
  ownership: "builtin" | "custom",
): CardField[] {
  const properties = schema?.config_schema?.properties;
  if (!properties || !config) return [];

  const fields: CardField[] = [];

  for (const [fieldName, fieldSchema] of Object.entries<any>(properties)) {
    const hints = fieldSchema?.hints || {};

    if (hints.hidden) continue;
    if (hints.secret) continue;

    const cardHint = hints.card;
    const contexts = cardHint?.contexts;
    if (!Array.isArray(contexts) || !contexts.includes(ownership)) continue;

    if (!isConditionallyVisible(fieldSchema, config)) continue;

    const value = config[fieldName];
    if (isEmptyValue(value)) {
      // Some fields have a meaningful "unset" state (e.g. an MCP provider's
      // empty tool_names means "all tools", not "nothing configured") —
      // `empty_text` surfaces that instead of silently dropping the field.
      if (cardHint?.empty_text) {
        fields.push({
          key: fieldName,
          label: resolveLabel(fieldName, fieldSchema),
          value: cardHint.empty_text,
        });
      }
      continue;
    }

    fields.push({
      key: fieldName,
      label: resolveLabel(fieldName, fieldSchema),
      value: formatValue(value, fieldSchema, schema?.config_schema),
    });
  }

  return fields;
}
