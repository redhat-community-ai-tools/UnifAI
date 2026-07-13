import dagre from "@dagrejs/dagre";
import {
  BuildingBlock,
  CanvasNode,
  CanvasEdge,
  YamlFlowState,
  YamlFlowNode,
  YamlFlowPlanStep,
  YamlFlowCondition,
} from "@/types/graph";
import { getCategoryDisplay } from "@/components/shared/helpers";
import { getBlueprintInfo, PromptShortcutInput } from "@/api/blueprints";
import { NODE_WIDTH } from "@/components/agentic-ai/graphs/GraphDisplayHelpers";

export interface ReconstructedGraph {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  yamlFlow: YamlFlowState;
  nextNodeId: number;
  name: string;
  description: string;
  promptShortcuts: PromptShortcutInput[];
}

function stripRef(rid: string): string {
  return rid.startsWith("$ref:") ? rid.slice(5) : rid;
}

function findBlockByRid(rid: string, blocks: BuildingBlock[]): BuildingBlock | null {
  const strippedRid = stripRef(rid);
  return (
    blocks.find(
      (b) => b.workspaceData?.rid === strippedRid || b.id === strippedRid,
    ) || null
  );
}

// Layout sizing constants — will be revisited when the graph library is swapped (GENIE-1246)
const NODE_BASE_HEIGHT = 64;
const CONDITION_HEADER_HEIGHT = 20;
const CONDITION_CARD_HEIGHT = 40;
const REF_HEADER_HEIGHT = 24;
const REF_ROW_HEIGHT = 28;
const REF_COLS = 3;
const RANK_SEP = 80;

function countConfigRefs(config: any): number {
  if (!config || typeof config !== "object") return 0;
  let count = 0;
  const traverse = (obj: unknown) => {
    if (typeof obj === "string" && obj.startsWith("$ref:")) count++;
    else if (Array.isArray(obj)) obj.forEach(traverse);
    else if (obj && typeof obj === "object") Object.values(obj).forEach(traverse);
  };
  traverse(config);
  return count;
}

function estimateNodeHeight(
  conditionCount: number,
  refCount: number,
): number {
  let h = NODE_BASE_HEIGHT;
  if (conditionCount > 0) {
    h += CONDITION_HEADER_HEIGHT + conditionCount * CONDITION_CARD_HEIGHT;
  }
  if (refCount > 0) {
    h += REF_HEADER_HEIGHT + Math.ceil(refCount / REF_COLS) * REF_ROW_HEIGHT;
  }
  return h;
}

interface SpecialNodeConfig {
  id: string;
  label: string;
  color: string;
  style: string;
  description: string;
  rid: string;
  type: string;
}

const SPECIAL_NODES: Record<string, SpecialNodeConfig> = {
  user_input: {
    id: "user_input",
    label: "User Input",
    color: "#4A90E2",
    style: "bg-blue-800 text-white border",
    description: "User question input node",
    rid: "user_question",
    type: "user_question_node",
  },
  finalize: {
    id: "finalize",
    label: "Final Answer",
    color: "#50C878",
    style: "bg-green-800 text-white border",
    description: "Final answer output node",
    rid: "final_answer",
    type: "final_answer_node",
  },
};

function createSpecialNode(
  config: SpecialNodeConfig,
  position: { x: number; y: number },
): CanvasNode {
  const now = new Date().toISOString();
  return {
    id: config.id,
    position,
    data: {
      label: config.label,
      icon: getCategoryDisplay("nodes").icon,
      color: config.color,
      style: config.style,
      description: config.description,
      workspaceData: {
        rid: config.rid,
        name: config.rid,
        category: "nodes",
        type: config.type,
        config: { name: config.label, type: config.type },
        version: 1,
        created: now,
        updated: now,
        nested_refs: [],
      },
      referencedConditions: [],
    },
  };
}

function createRegularNode(
  step: YamlFlowPlanStep,
  position: { x: number; y: number },
  nodeDef: YamlFlowNode | undefined,
  block: BuildingBlock | null,
): CanvasNode {
  const label = block?.label || nodeDef?.name || step.node;
  const category = block?.workspaceData?.category || "nodes";
  const color = block?.color || getCategoryDisplay(category).color;
  const now = new Date().toISOString();

  return {
    id: step.uid,
    position,
    data: {
      label,
      icon: getCategoryDisplay(category).icon,
      color,
      style: "bg-gray-800 text-white border",
      description: block?.description || `${category} - ${label}`,
      workspaceData: block?.workspaceData || {
        rid: step.node,
        name: nodeDef?.name || step.node,
        category: "nodes",
        type: nodeDef?.type || "unknown",
        config: nodeDef?.config || {},
        version: 1,
        created: now,
        updated: now,
        nested_refs: [],
      },
      referencedConditions: [],
    },
  };
}

function attachConditionToNode(
  node: CanvasNode,
  exitConditionRid: string,
  conditionsData: BuildingBlock[],
  specConditions: YamlFlowCondition[],
): void {
  const normalizedRid = stripRef(exitConditionRid);
  const condBlock = findBlockByRid(normalizedRid, conditionsData);
  const condDef = specConditions.find(
    (c) => stripRef(c.rid) === normalizedRid,
  );

  if (condBlock) {
    node.data.referencedConditions = [condBlock];
  } else if (condDef) {
    const now = new Date().toISOString();
    node.data.referencedConditions = [
      {
        id: stripRef(condDef.rid),
        type: condDef.type || "unknown",
        label: condDef.name,
        color: getCategoryDisplay("conditions").color,
        description: `conditions/${condDef.type} - ${condDef.name}`,
        workspaceData: {
          rid: stripRef(condDef.rid),
          name: condDef.name,
          category: "conditions",
          type: condDef.type || "unknown",
          config: condDef.config || {},
          version: 1,
          created: now,
          updated: now,
          nested_refs: [],
        },
      },
    ];
  }
}

interface StepLayoutHints {
  conditionCount: number;
  refCount: number;
  isFinalAnswer: boolean;
}

/**
 * Compute a hierarchical layout for plan steps using dagre,
 * matching the display produced by JointJS DirectedGraph.layout.
 *
 * Mirrors the display-graph behaviour:
 *  - Variable node heights based on conditions & config references.
 *  - final_answer node forced to the bottom rank.
 */
function computeLayout(
  plan: YamlFlowPlanStep[],
  hints: Map<string, StepLayoutHints>,
): Map<string, { x: number; y: number }> {
  const nonFinalSteps = plan.filter((s) => !hints.get(s.uid)?.isFinalAnswer);
  const finalSteps = plan.filter((s) => hints.get(s.uid)?.isFinalAnswer);

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: "TB",
    nodesep: 60,
    edgesep: 40,
    ranksep: RANK_SEP,
    marginx: 32,
    marginy: 32,
  });
  g.setDefaultEdgeLabel(() => ({}));

  for (const step of nonFinalSteps) {
    const h = hints.get(step.uid);
    const height = h
      ? estimateNodeHeight(h.conditionCount, h.refCount)
      : NODE_BASE_HEIGHT;
    g.setNode(step.uid, { width: NODE_WIDTH, height });
  }

  const edgeSet = new Set<string>();
  for (const step of nonFinalSteps) {
    if (step.after) {
      const afters = Array.isArray(step.after) ? step.after : [step.after];
      for (const a of afters) {
        const key = `${a}->${step.uid}`;
        if (!edgeSet.has(key)) { g.setEdge(a, step.uid); edgeSet.add(key); }
      }
    }
    if (step.branches) {
      for (const targetUid of Object.values(step.branches)) {
        const tid = targetUid as string;
        if (hints.get(tid)?.isFinalAnswer) continue;
        const key = `${step.uid}->${tid}`;
        if (!edgeSet.has(key)) { g.setEdge(step.uid, tid); edgeSet.add(key); }
      }
    }
  }

  dagre.layout(g);

  const positions = new Map<string, { x: number; y: number }>();

  let maxBottom = 0;
  for (const step of nonFinalSteps) {
    const n = g.node(step.uid);
    if (n) {
      const pos = { x: n.x - NODE_WIDTH / 2, y: n.y - n.height / 2 };
      positions.set(step.uid, pos);
      maxBottom = Math.max(maxBottom, pos.y + n.height);
    }
  }

  for (const step of finalSteps) {
    const h = hints.get(step.uid);
    const height = h
      ? estimateNodeHeight(h.conditionCount, h.refCount)
      : NODE_BASE_HEIGHT;
    const avgX =
      nonFinalSteps.length > 0
        ? Array.from(positions.values()).reduce((s, p) => s + p.x, 0) / positions.size
        : 200;
    positions.set(step.uid, {
      x: avgX,
      y: maxBottom + RANK_SEP,
    });
  }

  return positions;
}

function collectBranchPairs(plan: YamlFlowPlanStep[]): Set<string> {
  const pairs = new Set<string>();
  for (const step of plan) {
    if (step.branches) {
      for (const targetUid of Object.values(step.branches)) {
        pairs.add(`${step.uid}->${targetUid}`);
      }
    }
  }
  return pairs;
}

function buildEdges(plan: YamlFlowPlanStep[]): CanvasEdge[] {
  const edges: CanvasEdge[] = [];
  const branchPairs = collectBranchPairs(plan);

  for (const step of plan) {
    if (step.after) {
      const afterList = Array.isArray(step.after) ? step.after : [step.after];
      for (const afterUid of afterList) {
        if (!branchPairs.has(`${afterUid}->${step.uid}`)) {
          edges.push({
            id: `${afterUid}-${step.uid}`,
            source: afterUid,
            target: step.uid,
          });
        }
      }
    }

    if (step.branches) {
      for (const [branch, targetUid] of Object.entries(step.branches)) {
        edges.push({
          id: `${step.uid}-${targetUid}-${branch}`,
          source: step.uid,
          target: targetUid as string,
          data: { label: String(branch), isConditional: true },
        });
      }
    }
  }

  return edges;
}

/**
 * Reconstruct a React Flow graph (nodes + edges) and yamlFlow state
 * from a blueprint's spec_dict.
 */
export function reconstructBlueprintGraph(
  specDict: any,
  allBlocksData: BuildingBlock[],
  conditionsData: BuildingBlock[],
): ReconstructedGraph {
  const name: string = specDict.name || "Untitled";
  const description: string = specDict.description || "";
  const specNodes: YamlFlowNode[] = specDict.nodes || [];
  const plan: YamlFlowPlanStep[] = specDict.plan || [];
  const specConditions: YamlFlowCondition[] = specDict.conditions || [];

  const yamlFlow: YamlFlowState = {
    name,
    description,
    nodes: specNodes,
    plan,
    conditions: specConditions,
  };

  const nodeDefByRef = new Map<string, YamlFlowNode>();
  for (const nodeDef of specNodes) {
    const rawRid = stripRef(nodeDef.rid);
    nodeDefByRef.set(rawRid, nodeDef);
    nodeDefByRef.set(nodeDef.rid, nodeDef);
  }

  const layoutHints = new Map<string, StepLayoutHints>();
  for (const step of plan) {
    const nodeDef = nodeDefByRef.get(step.node);
    const block = findBlockByRid(step.node, allBlocksData);
    const nodeType =
      nodeDef?.type || block?.workspaceData?.type || "unknown";
    const config = block?.workspaceData?.config || nodeDef?.config;
    layoutHints.set(step.uid, {
      conditionCount: step.exit_condition ? 1 : 0,
      refCount: countConfigRefs(config),
      isFinalAnswer: nodeType === "final_answer_node" || step.uid === "finalize",
    });
  }

  const positions = computeLayout(plan, layoutHints);

  const canvasNodes: CanvasNode[] = [];
  let maxNodeId = plan.length + 1;

  for (const step of plan) {
    const position = positions.get(step.uid) || { x: 400, y: 200 };
    let node: CanvasNode;

    const specialConfig = SPECIAL_NODES[step.uid];
    if (specialConfig) {
      node = createSpecialNode(specialConfig, position);
    } else {
      const nodeDef = nodeDefByRef.get(step.node);
      const block = findBlockByRid(step.node, allBlocksData);

      const idMatch = step.uid.match(/-(\d+)$/);
      if (idMatch) {
        const num = parseInt(idMatch[1]);
        if (num >= maxNodeId) maxNodeId = num + 1;
      }

      node = createRegularNode(step, position, nodeDef, block);
    }

    if (step.exit_condition) {
      attachConditionToNode(node, step.exit_condition, conditionsData, specConditions);
    }

    canvasNodes.push(node);
  }

  const canvasEdges = buildEdges(plan);

  return {
    nodes: canvasNodes,
    edges: canvasEdges,
    yamlFlow,
    nextNodeId: maxNodeId,
    name,
    description,
    promptShortcuts: [],
  };
}

/**
 * Fetch a blueprint by ID and reconstruct the graph for editing.
 */
export async function loadBlueprintForEditing(
  blueprintId: string,
  allBlocksData: BuildingBlock[],
  conditionsData: BuildingBlock[],
): Promise<ReconstructedGraph> {
  const blueprintInfo = await getBlueprintInfo(blueprintId);
  const specDict = blueprintInfo.spec_dict;
  const graph = reconstructBlueprintGraph(
    specDict,
    allBlocksData,
    conditionsData,
  );
  return {
    ...graph,
    promptShortcuts: Array.isArray(specDict.prompt_shortcuts) ? specDict.prompt_shortcuts : [],
  };
}
