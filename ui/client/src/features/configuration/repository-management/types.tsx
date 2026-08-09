import { getCategoryDisplay, getCategoryDisplayName } from "@/components/shared/helpers";

export const DROPDOWN_BG = "bg-[#1a1a2e] border-gray-700";

// Kept in sync with the backend's builtin-disabled category list
// (mas.core.enums.ResourceCategory.builtin_disabled_categories) — retrievers
// aren't currently supported as built-in resources.
export const BUILTIN_DISABLED_CATEGORIES = new Set(["retrievers"]);

// Only the description text is specific to this admin browser — icon/label
// come from the app-wide `getCategoryDisplay`/`getCategoryDisplayName`
// (shared with the graph canvas and building-blocks sidebar).
const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  nodes: "Custom node agents, orchestrators, and AI agent types",
  llms: "Large Language Model providers and configurations",
  providers: "MCP servers, and external service connectors",
  tools: "Web fetch, SSH exec, MCP proxy, and other tool integrations",
  retrievers: "Document retrieval and search integrations",
  conditions: "Routing conditions and branching logic",
  auths: "Authentication strategies and credential stores",
};

export function getCategoryMeta(key: string) {
  return {
    label: getCategoryDisplayName(key),
    icon: getCategoryDisplay(key).icon,
    description: CATEGORY_DESCRIPTIONS[key] ?? "",
  };
}

export interface ResourceItem {
  rid: string;
  name: string;
  type: string;
  config: any;
  category?: string;
  ownership?: "builtin" | "custom";
  visibility?: "draft" | "public";
}

export type WizardStep = "idle" | "select-category" | "configure";
