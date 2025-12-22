/**
 * Constants and default values for graph logic
 */

import { YamlFlowState, BuiltinNodeDefinition } from './types';

/**
 * Default YAML flow state with required user_question and final_answer nodes
 */
export const DEFAULT_YAML_FLOW_STATE: YamlFlowState = {
  nodes: [
    {
      rid: "user_question",
      name: "User Question Node",
      type: "user_question_node",
      config: {
        type: "user_question_node",
      },
    },
    {
      rid: "final_answer",
      name: "Final Answer Node",
      type: "final_answer_node",
      config: {
        type: "final_answer_node",
      },
    },
  ],
  plan: [
    {
      uid: "user_input",
      node: "user_question",
    },
    {
      uid: "finalize",
      node: "final_answer",
    },
  ],
};

/**
 * Built-in node definitions for required nodes
 */
export const BUILTIN_NODES: Record<string, BuiltinNodeDefinition> = {
  user_question: {
    label: "User Input",
    color: "#4A90E2",
    workspaceData: {
      rid: "user_question",
      name: "user_question",
      category: "nodes",
      type: "user_question_node",
      config: { name: "User Input", type: "user_question_node" },
      version: 1,
    },
  },
  final_answer: {
    label: "Final Answer",
    color: "#50C878",
    workspaceData: {
      rid: "final_answer",
      name: "final_answer",
      category: "nodes",
      type: "final_answer_node",
      config: { name: "Final Answer", type: "final_answer_node" },
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

