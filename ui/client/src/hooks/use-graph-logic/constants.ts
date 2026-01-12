/**
 * Constants and default values for graph logic
 */

import { YamlFlowState, BuiltinNodeDefinition, NodeType, NodeRid } from './types';

/**
 * Default YAML flow state with required user_question and final_answer nodes
 */
export const DEFAULT_YAML_FLOW_STATE: YamlFlowState = {
  nodes: [
    {
      rid: NodeRid.USER_QUESTION,
      name: "User Question Node",
      type: NodeType.USER_QUESTION,
      config: {
        type: NodeType.USER_QUESTION,
      },
    },
    {
      rid: NodeRid.FINAL_ANSWER,
      name: "Final Answer Node",
      type: NodeType.FINAL_ANSWER,
      config: {
        type: NodeType.FINAL_ANSWER,
      },
    },
  ],
  plan: [
    {
      uid: "user_input",
      node: NodeRid.USER_QUESTION,
    },
    {
      uid: "finalize",
      node: NodeRid.FINAL_ANSWER,
    },
  ],
};

/**
 * Built-in node definitions for required nodes
 */
export const BUILTIN_NODES: Record<string, BuiltinNodeDefinition> = {
  [NodeRid.USER_QUESTION]: {
    label: "User Input",
    color: "#4A90E2",
    workspaceData: {
      rid: NodeRid.USER_QUESTION,
      name: NodeRid.USER_QUESTION,
      category: "nodes",
      type: NodeType.USER_QUESTION,
      config: { name: "User Input", type: NodeType.USER_QUESTION },
      version: 1,
    },
  },
  [NodeRid.FINAL_ANSWER]: {
    label: "Final Answer",
    color: "#50C878",
    workspaceData: {
      rid: NodeRid.FINAL_ANSWER,
      name: NodeRid.FINAL_ANSWER,
      category: "nodes",
      type: NodeType.FINAL_ANSWER,
      config: { name: "Final Answer", type: NodeType.FINAL_ANSWER },
      version: 1,
    },
  },
};

/**
 * Node dimensions for hit-testing during drag & drop
 */
export const NODE_DIMENSIONS = {
  width: 150,
  height: 80,
};

/**
 * Layout spacing constants
 */
export const LAYOUT = {
  horizontalSpacing: 300,
  verticalSpacing: 200,
  startX: 200,
  startY: 100,
};

