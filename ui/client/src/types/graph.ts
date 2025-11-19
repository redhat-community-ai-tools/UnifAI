import { Node, Edge } from "reactflow";

export interface CurrentGraph {
  id: string;
  name: string;
  nodes: Node[];
  edges: Edge[];
  metadata: {
    created: Date;
    lastModified: Date;
    nodeCount: number;
    edgeCount: number;
  };
}

export interface BuildingBlock {
  id: string;
  type: string;
  label: string;
  color: string;
  description: string;
  workspaceData?: {
    rid: string;
    name: string;
    category: string;
    type: string;
    config: any;
    version: number;
    created: string;
    updated: string;
    nested_refs: string[];
  };
}

export interface CustomNodeData {
  label: string;
  icon: React.ReactNode;
  color: string;
  style: string;
  description: string;
  workspaceData?: {
    rid: string;
    name: string;
    category: string;
    type: string;
    config: any;
    version: number;
    created: string;
    updated: string;
    nested_refs: string[];
  };
  onDelete?: (id: string) => void;
  allBlocks?: BuildingBlock[];
  referencedConditions?: BuildingBlock[];
  onAttachCondition?: (nodeId: string, condition: BuildingBlock) => void;
  onRemoveCondition?: (nodeId: string, conditionRid: string) => void;
}
