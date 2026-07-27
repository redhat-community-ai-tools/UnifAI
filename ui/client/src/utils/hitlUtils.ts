import type { GraphFlow } from "@/components/agentic-ai/graphs/interfaces";

/**
 * Returns true when at least one node in the blueprint spec has
 * `hitl_mode: "dynamic"` in its config.
 */
export function hasHitlDynamicNodes(spec: GraphFlow | null | undefined): boolean {
  if (!spec?.nodes) return false;
  return spec.nodes.some((node) => node.config?.hitl_mode === "dynamic");
}
