/**
 * Type definitions for graph logic and YAML flow state management
 */

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

