// Define types for node data
import {
  Node,
  Edge,
} from 'reactflow';

export interface NodeData {
  label: string;
  description: string | null;
  style: string;
  icon: React.ReactNode;
  tools: string[];
  workspaceData?: any;
  onDelete?: (nodeId: string) => void;
}

// Define types for GraphFlow structure
export interface NodeDefinition {
  config: {
    retries?: number;
    type: string;
    llm?: string;
    retriever?: string;
    system_message?: string;
    tools?: string[];
    [key: string]: any; // For additional config properties
  };
  name: string;
  rid: string;
  type: string;
}

export interface LLMDefinition {
  config: {
    api_key?: string;
    base_url?: string;
    extra?: { [key: string]: any };
    max_tokens?: number;
    model_name?: string;
    temperature?: number;
    type: string;
    [key: string]: any;
  };
  name: string;
  rid: string;
  type: string;
}

export interface RetrieverDefinition {
  config: {
    api_url?: string;
    threshold?: number;
    top_k_results?: number;
    type: string;
    [key: string]: any;
  };
  name: string;
  rid: string;
  type: string;
}

export interface ToolDefinition {
  config: {
    provider?: string;
    tool_name?: string;
    type: string;
    [key: string]: any;
  };
  name: string;
  rid: string;
  type: string;
}

export interface ProviderDefinition {
  config: {
    sse_endpoint?: string;
    type: string;
    [key: string]: any;
  };
  name: string;
  rid: string;
  type: string;
}

export interface PlanItem {
  after?: string | string[] | null;
  branches?: { [key: string]: string } | null; // Conditional branches: condition -> target node uid
  exit_condition: null;
  meta: {
    description: string;
    display_name: string;
    tags: string[];
  };
  node: string; // Reference to the node's rid
  uid: string;
}

export interface GraphFlow {
  conditions?: any[];
  description: string;
  name: string;
  nodes: NodeDefinition[];
  plan: PlanItem[];
  llms?: LLMDefinition[];
  retrievers?: RetrieverDefinition[];
  tools?: ToolDefinition[];
  providers?: ProviderDefinition[];
}

export interface FlowObject {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  flow: {
    nodes: Node<NodeData>[];
    edges: Edge[];
  };
}

// Additional interfaces for the graph builder
export interface EnhancedNodeData extends NodeData {
  status?: 'IDLE' | 'PROGRESS' | 'DONE';
  timestamp?: string;
  execution_data?: any;
}