/**
 * Type definitions for graph logic and YAML flow state management
 */

/**
 * Built-in node types for workflow graphs
 * These represent the required start (user input) and end (final answer) nodes
 */
export enum NodeType {
  USER_QUESTION = "user_question_node",
  FINAL_ANSWER = "final_answer_node",
}

/**
 * Built-in node RIDs (resource identifiers)
 * These are the default rids for the required nodes
 */
export enum NodeRid {
  USER_QUESTION = "user_question",
  FINAL_ANSWER = "final_answer",
}

export interface YamlFlowNode {
  rid: string;
  name: string;
  type?: string;
  config?: any;
}

export interface YamlFlowPlanStep {
  uid: string;
  node: string;
  after?: string | string[] | null;
  branches?: Record<string, string>;
  exit_condition?: string;
}

export interface YamlFlowCondition {
  rid: string;
  name: string;
  type?: string;
  config?: any;
}

export interface YamlFlowState {
  name?: string;
  description?: string;
  nodes: YamlFlowNode[];
  plan: YamlFlowPlanStep[];
  conditions?: YamlFlowCondition[];
}

export interface UseGraphLogicOptions {
  /** Blueprint ID for edit mode - if provided, loads existing blueprint */
  editBlueprintId?: string | null;
}

export interface ConditionalEdgeModalState {
  isOpen: boolean;
  sourceNodeId: string;
  targetNodeId: string;
  conditionType: string;
  existingBranches: string[];
}

export interface NodePosition {
  x: number;
  y: number;
}

export interface BuiltinNodeDefinition {
  label: string;
  color: string;
  workspaceData: {
    rid: string;
    name: string;
    category: string;
    type: string;
    config: { name: string; type: string };
    version: number;
  };
}

