/**
 * Converts GraphFlow (YAML blueprint spec) to a layout-friendly structure
 * used for display (e.g. JointJS). Keeps node details for element info.
 */

import type {
  GraphFlow,
  NodeDefinition,
  PlanItem,
} from "@/components/agentic-ai/graphs/interfaces";

/** Resolved reference: display name + id for modal/details. */
export interface ResolvedElement {
  type: "llm" | "tool" | "retriever" | "provider" | "sandbox";
  name: string;
  id: string;
}

export interface LayoutNode {
  id: string;
  label: string;
  description: string | null;
  type: string;
  /** Rank/level for hierarchical layout (0 = top) */
  level: number;
  /** Element details for display (config summary) */
  elementDetails: Record<string, unknown>;
  /** Resolved refs as name + id (names for display, ids for details modal) */
  resolvedElements: ResolvedElement[];
  /** Full node definition from YAML for tooltips/details */
  nodeDefinition: NodeDefinition | null;
}

export interface LayoutEdge {
  source: string;
  target: string;
  isConditional?: boolean;
  branchKey?: string;
}

export interface GraphFlowLayoutData {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
}

export function extractUidFromRef(value: string): string {
  if (typeof value === "string" && value.startsWith("$ref:")) {
    return value.substring(5);
  }
  return value;
}

/**
 * Resolve node definition from either draft (`$ref:` string) or resolved
 * (inline object) plan item format.
 */
function resolveNodeDef(
  nodeRef: unknown,
  nodeMap: Record<string, NodeDefinition>,
): NodeDefinition | null {
  if (typeof nodeRef === "object" && nodeRef !== null) {
    return nodeRef as NodeDefinition;
  }
  if (typeof nodeRef === "string") {
    return nodeMap[extractUidFromRef(nodeRef)] || null;
  }
  return null;
}

/**
 * Build a short summary of element config for display (legacy).
 */
function getElementDetails(nodeDef: NodeDefinition): Record<string, unknown> {
  const details: Record<string, unknown> = {};
  const config = nodeDef?.config || {};
  if (config.llm) details.llm = config.llm;
  if (config.retriever) details.retriever = config.retriever;
  if (config.tools && Array.isArray(config.tools)) details.tools = config.tools.length;
  if (config.type) details.type = config.type;
  if (config.system_message != null) details.system_message = true;
  return details;
}

/** Definition-list entry – minimal shape shared by all resource types. */
interface DefEntry { rid: string; name: string; }

/**
 * Recursively extract all $ref: IDs from a config object.
 * Same generic approach used by the graph canvas – future-proof for new resource types.
 */
function extractAllRefs(config: Record<string, unknown>): string[] {
  const refs: string[] = [];
  const seen = new Set<string>();

  const traverse = (obj: unknown) => {
    if (typeof obj === "string" && obj.startsWith("$ref:")) {
      const id = obj.substring(5);
      if (!seen.has(id)) { seen.add(id); refs.push(id); }
    } else if (Array.isArray(obj)) {
      obj.forEach(traverse);
    } else if (obj && typeof obj === "object") {
      Object.values(obj).forEach(traverse);
    }
  };

  traverse(config);
  return refs;
}

/**
 * Build a lookup: refId → { type, name } from every definition list in the
 * GraphFlow spec. Pre-computed once per graph so that per-node resolution is
 * a cheap map lookup rather than a full scan each time.
 */
function buildDefinitionLookup(
  graphFlow: GraphFlow,
): Map<string, { type: ResolvedElement["type"]; name: string }> {
  const lookup = new Map<string, { type: ResolvedElement["type"]; name: string }>();
  const register = (list: unknown[] | undefined, type: ResolvedElement["type"]) => {
    (list || []).forEach((d: any) => {
      if (!d || typeof d !== "object" || !d.rid) return;
      const id = extractUidFromRef(d.rid);
      lookup.set(id, { type, name: d.name || id });
      if (id !== d.rid) lookup.set(d.rid, { type, name: d.name || id });
    });
  };
  register(graphFlow.llms as unknown[] | undefined, "llm");
  register(graphFlow.tools as unknown[] | undefined, "tool");
  register(graphFlow.retrievers as unknown[] | undefined, "retriever");
  register(graphFlow.providers as unknown[] | undefined, "provider");
  register(graphFlow.sandboxes as unknown[] | undefined, "sandbox");
  return lookup;
}

/**
 * Resolve config refs to { type, name, id } by generically extracting every $ref:
 * from the node config and then determining its type via the pre-built definition
 * lookup.
 */
function getResolvedElements(
  lookup: Map<string, { type: ResolvedElement["type"]; name: string }>,
  nodeDef: NodeDefinition | null,
): ResolvedElement[] {
  if (!nodeDef?.config) return [];

  const refIds = extractAllRefs(nodeDef.config as Record<string, unknown>);
  if (refIds.length === 0) return [];

  return refIds.map((id) => {
    const match = lookup.get(id);
    return {
      type: match?.type ?? "tool",
      name: match?.name ?? id,
      id,
    };
  });
}

/**
 * Convert GraphFlow (same YAML structure used by the builder) to nodes and edges
 * with levels for hierarchical layout. Used by the panel graph display.
 */
export function graphFlowToLayoutData(graphFlow: GraphFlow): GraphFlowLayoutData {
  if (!graphFlow?.plan) {
    return { nodes: [], edges: [] };
  }

  const nodeMap: Record<string, NodeDefinition> = {};
  if (graphFlow.nodes) {
    graphFlow.nodes.forEach((node) => {
      nodeMap[extractUidFromRef(node.rid)] = node;
    });
  }

  const nodePredecessors: Record<string, string[]> = {};
  const nodesByLevel: Record<number, string[]> = {};
  const nodeLevel: Record<string, number> = {};

  // First pass: build predecessor map (includes both after- and branch-derived edges)
  graphFlow.plan.forEach((item: PlanItem) => {
    const nodeId = item.uid;
    if (item.after) {
      const predecessors = Array.isArray(item.after) ? item.after : [item.after];
      nodePredecessors[nodeId] = [...(nodePredecessors[nodeId] || []), ...predecessors];
    } else if (!nodePredecessors[nodeId]) {
      nodePredecessors[nodeId] = [];
    }

    // Also register branch targets – they have item.uid as a predecessor
    if (item.branches) {
      Object.values(item.branches).forEach((targetId) => {
        const tid = targetId as string;
        if (!nodePredecessors[tid]) nodePredecessors[tid] = [];
        if (!nodePredecessors[tid].includes(nodeId)) {
          nodePredecessors[tid].push(nodeId);
        }
      });
    }
  });

  // Level 0: user_question_node
  graphFlow.plan.forEach((item: PlanItem) => {
    const nodeId = item.uid;
    const nodeDef = resolveNodeDef(item.node, nodeMap);
    const nodeType = nodeDef?.type || "custom_agent_node";
    if (nodeType === "user_question_node") {
      nodeLevel[nodeId] = 0;
      if (!nodesByLevel[0]) nodesByLevel[0] = [];
      nodesByLevel[0].push(nodeId);
    }
  });

  // Assign levels for non-final nodes
  let allAssigned = false;
  const MAX_LEVEL_ITERATIONS = graphFlow.plan.length * graphFlow.plan.length + 1;
  let iterations = 0;
  while (!allAssigned) {
    allAssigned = true;
    let madeProgress = false;
    iterations++;

    graphFlow.plan.forEach((item: PlanItem) => {
      const nodeId = item.uid;
      const nodeDef = resolveNodeDef(item.node, nodeMap);
      const nodeType = nodeDef?.type || "custom_agent_node";
      if (nodeLevel[nodeId] !== undefined) return;
      if (nodeType === "final_answer_node") return;

      const predecessors = nodePredecessors[nodeId] || [];
      const allPredHaveLevels = predecessors.every((id) => nodeLevel[id] !== undefined);
      if (!allPredHaveLevels) {
        allAssigned = false;
        return;
      }

      let level: number;
      if (predecessors.length === 0) level = 1;
      else level = Math.max(...predecessors.map((id) => nodeLevel[id])) + 1;
      nodeLevel[nodeId] = level;
      if (!nodesByLevel[level]) nodesByLevel[level] = [];
      nodesByLevel[level].push(nodeId);
      madeProgress = true;
    });

    // Safety guard: break if no progress was made (missing predecessors or cycles)
    if (!allAssigned && !madeProgress) {
      console.warn(
        "[graphFlowLayout] Level assignment stuck – unresolved predecessors or cycle detected. " +
        "Assigning fallback levels for remaining nodes.",
      );
      const existingLevels = Object.values(nodeLevel);
      const fallbackLevel = existingLevels.length > 0 ? Math.max(...existingLevels) + 1 : 1;
      graphFlow.plan.forEach((item: PlanItem) => {
        if (nodeLevel[item.uid] === undefined) {
          const nd = resolveNodeDef(item.node, nodeMap);
          if ((nd?.type || "custom_agent_node") !== "final_answer_node") {
            nodeLevel[item.uid] = fallbackLevel;
            if (!nodesByLevel[fallbackLevel]) nodesByLevel[fallbackLevel] = [];
            nodesByLevel[fallbackLevel].push(item.uid);
          }
        }
      });
      break;
    }

    // Hard cap: prevent truly infinite loops even if madeProgress flickers
    if (iterations >= MAX_LEVEL_ITERATIONS) {
      console.warn("[graphFlowLayout] Max iterations reached during level assignment.");
      break;
    }
  }

  // Final layer: final_answer_node
  graphFlow.plan.forEach((item: PlanItem) => {
    const nodeId = item.uid;
    const nodeDef = resolveNodeDef(item.node, nodeMap);
    const nodeType = nodeDef?.type || "custom_agent_node";
    if (nodeType === "final_answer_node") {
      const levels = Object.keys(nodesByLevel).map(Number);
      const maxLevel = levels.length > 0 ? Math.max(...levels) : -1;
      const finalLevel = maxLevel + 1;
      nodeLevel[nodeId] = finalLevel;
      if (!nodesByLevel[finalLevel]) nodesByLevel[finalLevel] = [];
      nodesByLevel[finalLevel].push(nodeId);
    }
  });

  /** Humanize a code-like name: "docs_agent" → "Docs Agent" */
  const humanize = (s: string) =>
    s.replace(/[-_]/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());

  // Pre-build definition lookup once for the entire graph
  const defLookup = buildDefinitionLookup(graphFlow);

  const nodes: LayoutNode[] = graphFlow.plan.map((item: PlanItem) => {
    const nodeDef = resolveNodeDef(item.node, nodeMap);
    const nodeType = nodeDef?.type || "custom_agent_node";
    // Prefer step-level display_name → humanized node def name → humanized UID → fallback
    const label =
      item.meta?.display_name ||
      (nodeDef?.name ? humanize(nodeDef.name) : null) ||
      humanize(item.uid) ||
      "Node";
    const description = item.meta?.description || null;
    const level = nodeLevel[item.uid] ?? 0;
    return {
      id: item.uid,
      label,
      description,
      type: nodeType,
      level,
      elementDetails: nodeDef ? getElementDetails(nodeDef) : {},
      resolvedElements: getResolvedElements(defLookup, nodeDef),
      nodeDefinition: nodeDef,
    };
  });

  const edges: LayoutEdge[] = [];
  graphFlow.plan.forEach((item: PlanItem) => {
    if (item.after) {
      const predecessors = Array.isArray(item.after) ? item.after : [item.after];
      predecessors.forEach((predId) => {
        edges.push({ source: predId, target: item.uid });
      });
    }
    if (item.branches) {
      Object.entries(item.branches).forEach(([branchKey, targetId]) => {
        edges.push({
          source: item.uid,
          target: targetId as string,
          isConditional: true,
          branchKey,
        });
      });
    }
  });

  return { nodes, edges };
}
