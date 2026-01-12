/**
 * Layout and positioning helpers for graph nodes and edges
 */

import { Edge } from 'reactflow';
import { YamlFlowPlanStep, NodePosition, NodeType, NodeRid } from './types';
import { LAYOUT } from './constants';

/**
 * Check if a node type is user_question
 */
const isUserQuestionNode = (nodeType: string | undefined, nodeRid: string): boolean => {
  return nodeType === NodeType.USER_QUESTION || nodeRid === NodeRid.USER_QUESTION;
};

/**
 * Check if a node type is final_answer
 */
const isFinalAnswerNode = (nodeType: string | undefined, nodeRid: string): boolean => {
  return nodeType === NodeType.FINAL_ANSWER || nodeRid === NodeRid.FINAL_ANSWER;
};

/**
 * Calculate node positions based on plan dependencies
 * Positions nodes in a top-to-bottom layout based on their dependency levels
 */
export function calculateNodePositions(
  plan: YamlFlowPlanStep[],
  nodeDefMap: Record<string, any>
): Record<string, NodePosition> {
  const positions: Record<string, NodePosition> = {};
  const nodeLevel: Record<string, number> = {};
  const nodesByLevel: Record<number, string[]> = {};

  // First pass: identify predecessors and assign levels
  plan.forEach((step) => {
    const nodeType = nodeDefMap[step.node]?.type || nodeDefMap[step.node]?.config?.type;

    if (isUserQuestionNode(nodeType, step.node)) {
      nodeLevel[step.uid] = 0;
      nodesByLevel[0] = nodesByLevel[0] || [];
      nodesByLevel[0].push(step.uid);
    } else if (!isFinalAnswerNode(nodeType, step.node)) {
      // Calculate level based on predecessors
      const preds = step.after
        ? (Array.isArray(step.after) ? step.after : [step.after])
        : [];

      if (preds.length === 0) {
        nodeLevel[step.uid] = 1;
      } else {
        const maxPredLevel = Math.max(...preds.map((p) => nodeLevel[p] ?? 0));
        nodeLevel[step.uid] = maxPredLevel + 1;
      }
      const level = nodeLevel[step.uid];
      nodesByLevel[level] = nodesByLevel[level] || [];
      nodesByLevel[level].push(step.uid);
    }
  });

  // Final answer gets last level
  const maxLevel = Math.max(...Object.keys(nodesByLevel).map(Number), 0) + 1;
  plan.forEach((step) => {
    const nodeType = nodeDefMap[step.node]?.type || nodeDefMap[step.node]?.config?.type;
    if (isFinalAnswerNode(nodeType, step.node)) {
      nodeLevel[step.uid] = maxLevel;
      nodesByLevel[maxLevel] = nodesByLevel[maxLevel] || [];
      nodesByLevel[maxLevel].push(step.uid);
    }
  });

  // Calculate positions
  plan.forEach((step) => {
    const level = nodeLevel[step.uid] ?? 0;
    const nodesInLevel = nodesByLevel[level] || [step.uid];
    const idx = nodesInLevel.indexOf(step.uid);
    const total = nodesInLevel.length;
    
    positions[step.uid] = {
      x: LAYOUT.startX + (idx - (total - 1) / 2) * LAYOUT.horizontalSpacing,
      y: LAYOUT.startY + level * LAYOUT.verticalSpacing,
    };
  });

  return positions;
}

/**
 * Create ReactFlow edges from plan step dependencies
 */
export function createEdgesFromPlan(plan: YamlFlowPlanStep[]): Edge[] {
  const edges: Edge[] = [];

  plan.forEach((step) => {
    // Regular edges from 'after' dependencies
    if (step.after) {
      const sources = Array.isArray(step.after) ? step.after : [step.after];
      sources.forEach((source) => {
        edges.push({
          id: `${source}-${step.uid}`,
          source,
          target: step.uid,
          type: "custom",
        });
      });
    }

    // Conditional edges from 'branches'
    if (step.branches) {
      Object.entries(step.branches).forEach(([branchKey, targetUid]) => {
        edges.push({
          id: `${step.uid}-${targetUid}-${branchKey}`,
          source: step.uid,
          target: targetUid as string,
          type: "custom",
          style: { strokeDasharray: "5,5", stroke: "#10b981" },
          label: String(branchKey),
          data: { branch: branchKey, isConditional: true },
        });
      });
    }
  });

  return edges;
}

/**
 * Extract rid without $ref: prefix
 */
export function extractRid(rid: string): string {
  return rid?.startsWith('$ref:') ? rid.slice(5) : rid;
}

/**
 * Build lookup maps from blueprint spec
 */
export function buildLookupMaps(specDict: any): {
  nodeDefMap: Record<string, any>;
  condDefMap: Record<string, any>;
} {
  const nodeDefMap: Record<string, any> = {};
  (specDict.nodes || []).forEach((n: any) => {
    nodeDefMap[extractRid(n.rid)] = n;
  });

  const condDefMap: Record<string, any> = {};
  (specDict.conditions || []).forEach((c: any) => {
    condDefMap[extractRid(c.rid)] = c;
  });

  return { nodeDefMap, condDefMap };
}

