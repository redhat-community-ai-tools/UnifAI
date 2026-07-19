import {
  Brain,
  Bot,
  Server,
  Wrench,
  Search,
  GitBranch,
  Lock,
  Layers,
} from "lucide-react";

export const DROPDOWN_BG = "bg-[#1a1a2e] border-gray-700";

// Kept in sync with the backend's builtin-disabled category list
// (mas.core.enums.ResourceCategory.builtin_disabled_categories) — retrievers
// aren't currently supported as built-in resources.
export const BUILTIN_DISABLED_CATEGORIES = new Set(["retrievers"]);

export const CATEGORY_META: Record<
  string,
  { label: string; icon: React.ReactNode; description: string }
> = {
  nodes: {
    label: "Agents",
    icon: <Bot className="h-4 w-4" />,
    description: "Custom node agents, orchestrators, and AI agent types",
  },
  llms: {
    label: "LLMs",
    icon: <Brain className="h-4 w-4" />,
    description: "Large Language Model providers and configurations",
  },
  providers: {
    label: "Providers",
    icon: <Server className="h-4 w-4" />,
    description: "MCP servers, RAG clients, and external service connectors",
  },
  tools: {
    label: "Tools",
    icon: <Wrench className="h-4 w-4" />,
    description: "Web fetch, SSH exec, MCP proxy, and other tool integrations",
  },
  retrievers: {
    label: "Retrievers",
    icon: <Search className="h-4 w-4" />,
    description: "Document retrieval and search integrations",
  },
  conditions: {
    label: "Conditions",
    icon: <GitBranch className="h-4 w-4" />,
    description: "Routing conditions and branching logic",
  },
  auths: {
    label: "Auths",
    icon: <Lock className="h-4 w-4" />,
    description: "Authentication strategies and credential stores",
  },
};

export function getCategoryMeta(key: string) {
  return (
    CATEGORY_META[key] ?? {
      label: key.charAt(0).toUpperCase() + key.slice(1),
      icon: <Layers className="h-4 w-4" />,
      description: "",
    }
  );
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

export type WizardStep = "idle" | "select-category" | "configure" | "configure-builtin";
