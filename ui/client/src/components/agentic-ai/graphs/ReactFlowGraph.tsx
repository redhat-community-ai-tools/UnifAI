import React, { useState, useEffect, useRef, useCallback } from "react";
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  NodeTypes,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  NodeProps,
  Handle,
  useReactFlow,
} from "reactflow";
import "reactflow/dist/style.css";
import { motion } from "framer-motion";
import {
  NodeData,
  GraphFlow,
  FlowObject,
  NodeDefinition,
  PlanItem,
} from "./interfaces";
import { useAuth } from "@/contexts/AuthContext";
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { useStreamingData } from "../StreamingDataContext";
import { BuildingBlock } from "../../../types/graph";
import InnerRefElement from "./InnerRefElement";
import NodeValidationIndicator from "./NodeValidationIndicator";
import { ValidationResultModal } from "../workspace/ValidationResultModal";
import { ElementValidationResult } from "@/types/validation";
import axios from "../../../http/axiosAgentConfig";

// Node status enum
type NodeStatus = "IDLE" | "PROGRESS" | "DONE";

// Enhanced NodeData interface
interface EnhancedNodeData extends NodeData {
  status: NodeStatus;
  allBlocks?: any[];
  workspaceData?: any;
  fetchResourceById?: (refId: string) => Promise<any>;
  validationResult?: ElementValidationResult;
  isValidating?: boolean;
  onShowValidationDetails?: (result: ElementValidationResult) => void;
}

// Custom node components with status-aware styling
const AgentNode: React.FC<NodeProps<EnhancedNodeData>> = ({
  data,
  selected,
}) => {
  // Match the hex color code inside bg-[#...]
  const bgmatcher = data.style.match(/bg-\[#([0-9A-Fa-f]{6})\]/);
  const bgcolor = bgmatcher ? bgmatcher[1] : null;

  const isInProgress = data.status === "PROGRESS";
  const isDone = data.status === "DONE";

  // Shared function to extract reference IDs from configuration
  const extractReferences = useCallback((config: any): { [key: string]: string } => {
    const refs: { [key: string]: string } = {};

    if (!config || typeof config !== "object") {
      return refs;
    }

    const traverse = (obj: any, path: string = "") => {
      for (const [key, value] of Object.entries(obj)) {
        if (typeof value === "string" && value.startsWith("$ref:")) {
          // Extract the actual reference ID after $ref:
          const refId = value.substring(5);
          refs[key] = refId;
        } else if (Array.isArray(value)) {
          // Handle arrays that might contain $ref values
          value.forEach((item, index) => {
            if (typeof item === "string" && item.startsWith("$ref:")) {
              const refId = item.substring(5);
              refs[`${key}[${index}]`] = refId;
            }
          });
        } else if (typeof value === "object" && value !== null) {
          traverse(value, path ? `${path}.${key}` : key);
        }
      }
    };

    traverse(config);
    return refs;
  }, []);

  // Extract reference IDs from the node configuration and fetch them
  const extractAndFetchReferences = useCallback(async (config: any, allBlocks: any[], fetchResourceByIdFn: (refId: string) => Promise<any>): Promise<BuildingBlock[]> => {
    const refs = extractReferences(config);

    // Fetch all referenced resources
    const fetchedBlocks: BuildingBlock[] = [];
    for (const [key, refId] of Object.entries(refs)) {
      // Check if we already have this resource in allBlocks
      const existingBlock = allBlocks.find(block => 
        block.workspaceData?.rid === refId || block.id === refId
      );

      if (!existingBlock) {
        try {
          const resourceData = await fetchResourceByIdFn(refId);
          if (resourceData) {
            const buildingBlock: BuildingBlock = {
              id: resourceData.rid || refId,
              type: resourceData.type || 'unknown',
              label: resourceData.name || refId,
              color: "#FFB300", // Default color
              description: "",
              workspaceData: {
                rid: resourceData.rid,
                name: resourceData.name,
                category: resourceData.category,
                type: resourceData.type,
                config: resourceData.cfg_dict,
                version: resourceData.version,
                created: resourceData.created,
                updated: resourceData.updated,
                nested_refs: resourceData.nested_refs,
              }
            };
            fetchedBlocks.push(buildingBlock);
          }
        } catch (error) {
          console.error(`Failed to fetch referenced resource ${refId}:`, error);
        }
      }
    }

    return fetchedBlocks;
  }, [extractReferences]);

  // State to manage fetched references
  const [enhancedAllBlocks, setEnhancedAllBlocks] = useState<BuildingBlock[]>([]);
  const [referencesLoaded, setReferencesLoaded] = useState(false);

  // Load references when component mounts
  useEffect(() => {
    if (data.workspaceData?.config && !referencesLoaded && data.fetchResourceById) {
      extractAndFetchReferences(data.workspaceData.config, data.allBlocks || [], data.fetchResourceById)
        .then(fetchedBlocks => {
          // Combine original blocks with fetched references
          const originalBlocks = (data.allBlocks || []).map(block => ({
            id: block.id || '',
            type: block.workspaceData?.type || 'unknown',
            label: block.workspaceData?.name || block.label || '',
            color: "#FFB300",
            description: block.description || "",
            workspaceData: block.workspaceData
          }));
          
          setEnhancedAllBlocks([...originalBlocks, ...fetchedBlocks]);
          setReferencesLoaded(true);
        })
        .catch(error => {
          console.error('Failed to fetch references:', error);
          setReferencesLoaded(true);
        });
    }
  }, [data.workspaceData?.config, data.allBlocks, referencesLoaded, data.fetchResourceById, extractAndFetchReferences]);

  const references = data.workspaceData?.config 
    ? extractReferences(data.workspaceData.config)
    : {};
  const hasReferences = Object.keys(references).length > 0;

  // Dynamic styling based on status
  const getStatusStyles = () => {
    if (isInProgress) {
      return {
        containerClass: `${data.style} border-2 border-blue-500 border-opacity-80`,
        pulseEffect: true,
        borderGlow: "shadow-lg shadow-blue-500/20",
      };
    } else if (isDone) {
      return {
        containerClass: `${data.style} border-2 border-[hsl(var(--success))] border-opacity-60`,
        pulseEffect: false,
        borderGlow: "shadow-md shadow-green-500/15",
      };
    } else {
      return {
        containerClass: data.style,
        pulseEffect: false,
        borderGlow: "shadow-md",
      };
    }
  };

  const statusStyles = getStatusStyles();

  return (
    <>
      {/* Explicit top handle using ReactFlow's Handle component */}
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: `#${bgcolor}`,
          width: 10,
          height: 10,
        }}
      />

      <motion.div
        className={`relative rounded-lg ${statusStyles.containerClass} ${statusStyles.borderGlow} transition-all duration-300 px-4 py-2`}
        initial={{ opacity: 0 }}
        animate={{
          opacity: 1,
          scale: selected ? 1.05 : 1,
          boxShadow: isInProgress
            ? [
                "0 0 0 0 rgba(96, 165, 250, 0.7)",
                "0 0 0 10px rgba(96, 165, 250, 0)",
                "0 0 0 0 rgba(96, 165, 250, 0.7)",
              ]
            : undefined,
        }}
        transition={{
          duration: 0.3,
          boxShadow: {
            repeat: isInProgress ? Infinity : 0,
            duration: 2,
            ease: "easeInOut",
          },
        }}
      >
        {/* Validation indicator - top right corner (only shown for invalid nodes) */}
        {(data.isValidating || (data.validationResult && !data.validationResult.is_valid)) && (
          <div className="absolute -top-1 -right-1 z-10">
            <NodeValidationIndicator
              validationResult={data.validationResult}
              isValidating={data.isValidating}
              onClick={() => {
                if (data.validationResult && data.onShowValidationDetails) {
                  data.onShowValidationDetails(data.validationResult);
                }
              }}
            />
          </div>
        )}

        {/* Main node content */}
        <div className="flex items-center relative">
          <div className="mr-2">{data.icon}</div>
          <div className="flex-1">
            <div className="font-medium text-sm flex items-center gap-2">
              {data.label}
              {isInProgress && (
                <div className="flex items-center gap-1.5 px-2 py-0.5 bg-blue-500 bg-opacity-20 rounded-full">
                  <motion.div
                    className="w-1.5 h-1.5 bg-blue-500 rounded-full"
                    animate={{ opacity: [1, 0.3, 1] }}
                    transition={{
                      duration: 1,
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                  />
                  <span className="text-xs font-medium text-white-600">
                    Processing
                  </span>
                </div>
              )}
              {isDone && (
                <div className="flex items-center gap-1.5 px-2 py-0.5 bg-green-500 bg-opacity-20 rounded-full">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                  <span className="text-xs font-medium text-white-600">
                    Complete
                  </span>
                </div>
              )}
            </div>
            {data.description && (
              <div
                className={`text-xs ${data.style.includes("text-white") ? "text-gray-400" : "text-white"}`}
              >
                {data.description}
              </div>
            )}
          </div>
        </div>

        {/* References section */}
        {hasReferences && (
          <div className="px-4 py-2">
            <div className={`text-xs text-gray-400 mb-1`}>
              Resources:
            </div>
            <div className="flex flex-wrap gap-1">
              {Object.entries(references).map(([key, refId]) => (
                <InnerRefElement
                  key={`${key}-${refId}`}
                  refId={refId}
                  refData={{ key, value: refId }}
                  allBlocks={enhancedAllBlocks}
                />
              ))}
            </div>
          </div>
        )}
      </motion.div>

      {/* Explicit bottom handle using ReactFlow's Handle component */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: `#${bgcolor}`,
          width: 10,
          height: 10,
        }}
      />
    </>
  );
};

const nodeTypes: NodeTypes = {
  agent: AgentNode,
};

// Helper function to extract UID from $ref: format
const extractUidFromRef = (value: string): string => {
  if (typeof value === 'string' && value.startsWith('$ref:')) {
    return value.substring(5); // Remove '$ref:' prefix
  }
  return value;
};

// Function to generate a random icon
const getRandomIcon = (nodeType: string): React.ReactNode => {
  // Handle specific node types with consistent icons
  if (nodeType === "user_question_node") {
    return (
      <div className="w-6 h-6 rounded-full bg-white bg-opacity-30 flex items-center justify-center text-xs">
        💬
      </div>
    );
  } else if (nodeType === "final_answer_node") {
    return (
      <div className="w-6 h-6 rounded-full bg-white bg-opacity-30 flex items-center justify-center text-xs">
        🤖
      </div>
    );
  }

  // For other node types, select from a predefined set of icons
  const icons: React.ReactNode[] = [
    <div className="w-6 h-6 rounded-full bg-white bg-opacity-30 flex items-center justify-center text-xs">
      🔍
    </div>,
    <div className="w-6 h-6 rounded-full bg-white bg-opacity-30 flex items-center justify-center text-xs">
      📚
    </div>,
    <div className="w-6 h-6 rounded-full bg-white bg-opacity-30 flex items-center justify-center text-xs">
      🧠
    </div>,
    <div className="w-6 h-6 rounded-full bg-white bg-opacity-30 flex items-center justify-center text-xs">
      🔎
    </div>,
    <div className="w-6 h-6 rounded-full bg-white bg-opacity-30 flex items-center justify-center text-xs">
      🔧
    </div>,
    <div className="w-6 h-6 rounded-full bg-white bg-opacity-30 flex items-center justify-center text-xs">
      ✍️
    </div>,
  ];

  // Generate a deterministic index based on the node type
  const hash = nodeType
    .split("")
    .reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return icons[hash % icons.length];
};

// Get node style based on node type
const getNodeStyle = (nodeType: string): string => {
  if (nodeType === "user_question_node") {
    return "bg-gradient-to-r from-accent to-[#003f5c] text-white";
  } else if (nodeType === "final_answer_node") {
    return "bg-gradient-to-r from-accent to-[#003f5c] text-white";
  } else {
    return "bg-gradient-to-r from-accent to-primary text-gray-300";
  }
};

// Function to generate edge color based on source node type
const getEdgeStyle = (
  sourceNodeType: string,
): { stroke: string; color: string } => {
  if (sourceNodeType === "user_question_node") {
    return { stroke: "#003f5c", color: "#003f5c" };
  } else if (sourceNodeType === "final_answer_node") {
    return { stroke: "#003f5c", color: "#003f5c" };
  } else {
    return { stroke: "hsl(var(--primary))", color: "hsl(var(--primary))" };
  }
};

// Function to generate conditional edge styling - matches node gradient colors
const getConditionalEdgeStyle = (
  sourceNodeType: string,
): { stroke: string; color: string; strokeDasharray: string } => {
  if (sourceNodeType === "user_question_node") {
    return { stroke: "hsl(var(--accent))", color: "hsl(var(--accent))", strokeDasharray: "5,5" };
  } else if (sourceNodeType === "final_answer_node") {
    return { stroke: "hsl(var(--accent))", color: "hsl(var(--accent))", strokeDasharray: "5,5" };
  } else {
    return { stroke: "hsl(var(--primary))", color: "hsl(var(--primary))", strokeDasharray: "5,5" };
  }
};

// Function to parse the JSON graph flow into ReactFlow nodes and edges
const parseGraphFlow = (
  graphFlow: GraphFlow,
  fetchResourceByIdFn?: (refId: string) => Promise<any>
): { nodes: Node<EnhancedNodeData>[]; edges: Edge[] } => {
  if (!graphFlow || !graphFlow.plan) {
    return { nodes: [], edges: [] };
  }

  // Create a map of node RIDs to node definitions for quick lookup
  const nodeMap: Record<string, NodeDefinition> = {};
  if (graphFlow.nodes) {
    graphFlow.nodes.forEach((node) => {
      nodeMap[extractUidFromRef(node.rid)] = node;
    });
  }

  // Create a map to store node types for edge styling
  const nodeTypeMap: Record<string, string> = {};

  // Create maps to build the layout
  const nodesByLevel: Record<number, string[]> = {}; // Level -> Node UIDs
  const nodeLevel: Record<string, number> = {}; // Node UID -> Level
  const nodePredecessors: Record<string, string[]> = {}; // Node UID -> Predecessor UIDs
  const nodeSuccessors: Record<string, string[]> = {}; // Node UID -> Successor UIDs

  // First pass: Identify predecessors and successors
  graphFlow.plan.forEach((item) => {
    const nodeId = item.uid;
    const nodeDefinition = nodeMap[item.node];
    const nodeType = nodeDefinition?.type || "custom_agent_node";
    nodeTypeMap[nodeId] = nodeType;

    if (item.after) {
      // Handle both string and array 'after' properties
      const predecessors = Array.isArray(item.after)
        ? item.after
        : [item.after];
      nodePredecessors[nodeId] = predecessors;

      // Record this node as a successor to each predecessor
      predecessors.forEach((predecessorId) => {
        if (!nodeSuccessors[predecessorId]) {
          nodeSuccessors[predecessorId] = [];
        }
        nodeSuccessors[predecessorId].push(nodeId);
      });
    } else {
      // No predecessors, this is a root node
      nodePredecessors[nodeId] = [];
    }
  });

  // Force user_question_node to level 0 (first layer)
  graphFlow.plan.forEach((item) => {
    const nodeId = item.uid;
    const nodeDefinition = nodeMap[item.node];
    const nodeType = nodeDefinition?.type || "custom_agent_node";
    
    if (nodeType === "user_question_node") {
      nodeLevel[nodeId] = 0;
      if (!nodesByLevel[0]) {
        nodesByLevel[0] = [];
      }
      nodesByLevel[0].push(nodeId);
    }
  });


  // Second pass: Determine node levels for all nodes except final_answer_node
  let allNodesAssigned = false;
  while (!allNodesAssigned) {
    allNodesAssigned = true;
    graphFlow.plan.forEach((item) => {
      const nodeId = item.uid;
      const nodeDefinition = nodeMap[item.node];
      const nodeType = nodeDefinition?.type || "custom_agent_node";

      // Skip nodes that already have a level assigned
      if (nodeLevel[nodeId] !== undefined) {
        return;
      }

      // Skip final_answer_node for now - we'll handle it separately
      if (nodeType === "final_answer_node") {
        return;
      }

      const predecessors = nodePredecessors[nodeId] || [];

      // Check if all predecessors have levels assigned
      const allPredecessorsHaveLevels = predecessors.every(
        (predId) => nodeLevel[predId] !== undefined,
      );

      if (allPredecessorsHaveLevels) {
        let level;
        if (predecessors.length === 0) {
          // Node has no predecessors - assign to level 1 (not level 0, which is reserved for user_question_node)
          level = 1;
        } else {
          // Find the maximum level among predecessors
          const maxPredLevel = Math.max(
            ...predecessors.map((predId) => nodeLevel[predId]),
          );
          level = maxPredLevel + 1;
        }

        // Assign this node to the calculated level
        nodeLevel[nodeId] = level;
        if (!nodesByLevel[level]) {
          nodesByLevel[level] = [];
        }
        nodesByLevel[level].push(nodeId);
      } else {
        allNodesAssigned = false;
      }
    });
  }

  // Third pass: Force final_answer_node to the highest level + 1 (last layer)
  graphFlow.plan.forEach((item) => {
    const nodeId = item.uid;
    const nodeDefinition = nodeMap[item.node];
    const nodeType = nodeDefinition?.type || "custom_agent_node";
    
    if (nodeType === "final_answer_node") {
      // Find the current highest level
      const existingLevels = Object.keys(nodesByLevel).map(level => parseInt(level));
      const maxLevel = existingLevels.length > 0 ? Math.max(...existingLevels) : -1;
      const finalLevel = maxLevel + 1;
      
      nodeLevel[nodeId] = finalLevel;
      if (!nodesByLevel[finalLevel]) {
        nodesByLevel[finalLevel] = [];
      }
      nodesByLevel[finalLevel].push(nodeId);
    }
  });

  // Create nodes with the calculated positions
  const nodes: Node<EnhancedNodeData>[] = graphFlow.plan.map((item) => {
    const nodeId = item.uid;
    const nodeDefinition = nodeMap[item.node];
    const nodeType = nodeDefinition?.type || "custom_agent_node";
    const nodeLabel =
      nodeDefinition?.name || item.meta?.display_name || "General Node";
    const nodeDescription = item.meta?.description || null;
    const nodeTools = nodeDefinition?.config?.tools || [];

    // Get level information
    const level = nodeLevel[nodeId];
    const nodesInSameLevel = nodesByLevel[level] || [];
    const indexInLevel = nodesInSameLevel.indexOf(nodeId);
    const totalInLevel = nodesInSameLevel.length;

    // Calculate position
    // Horizontal spacing increases with the number of nodes in the level
    const levelWidth = Math.max(totalInLevel * 600, 800);
    const xSpacing = levelWidth / totalInLevel;
    const xOffset = xSpacing / 2 + indexInLevel * xSpacing;
    const yOffset = level * 150;

    // Determine node style and icon
    const style = getNodeStyle(nodeType);
    const icon = getRandomIcon(nodeType);

    // Always set sourcePosition and targetPosition to ensure edges connect properly
    const sourcePosition = Position.Bottom;
    const targetPosition = Position.Top;

    return {
      id: nodeId,
      type: "agent",
      data: {
        label: nodeLabel,
        description: nodeDescription,
        style: style,
        icon: icon,
        tools: nodeTools || [],
        status: "IDLE" as NodeStatus,
        workspaceData: nodeDefinition,
        allBlocks: graphFlow.nodes || [],
        fetchResourceById: fetchResourceByIdFn,
      },
      position: { x: xOffset, y: yOffset },
      sourcePosition,
      targetPosition,
    };
  });

  // Create edges between nodes
  const edges: Edge[] = [];

  graphFlow.plan.forEach((item) => {
    // Handle regular sequential edges (after dependencies)
    if (item.after) {
      // Handle both string and array 'after' properties
      const predecessors = Array.isArray(item.after)
        ? item.after
        : [item.after];

      predecessors.forEach((predecessorId) => {
        const sourceNodeType =
          nodeTypeMap[predecessorId] || "custom_agent_node";
        const edgeStyle = getEdgeStyle(sourceNodeType);

        edges.push({
          id: `${predecessorId}-to-${item.uid}`,
          source: predecessorId,
          target: item.uid,
          animated: true,
          type: "default", // Will be updated to smoothstep for bidirectional edges
          style: {
            stroke: edgeStyle.stroke,
            strokeWidth: 2,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: edgeStyle.color,
            width: 10,
            height: 10,
          },
          zIndex: 1000, // Ensure edges are on top
        });
      });
    }

    // Handle conditional edges (branches)
    if (item.branches) {
      const sourceNodeType = nodeTypeMap[item.uid] || "custom_agent_node";
      const conditionalEdgeStyle = getConditionalEdgeStyle(sourceNodeType);

      // Create edges for each branch target
      Object.entries(item.branches).forEach(([branchKey, targetNodeId]) => {
        edges.push({
          id: `${item.uid}-branch-${branchKey}-to-${targetNodeId}`,
          source: item.uid,
          target: targetNodeId as string,
          animated: true,
          type: "default",
          style: {
            stroke: conditionalEdgeStyle.stroke,
            strokeWidth: 2,
            strokeDasharray: conditionalEdgeStyle.strokeDasharray,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: conditionalEdgeStyle.color,
            width: 10,
            height: 10,
          },
          // label: branchKey, // Show the branch condition as edge label
          labelStyle: {
            fontSize: 10,
            fontWeight: 'bold',
            fill: conditionalEdgeStyle.color,
          },
          labelBgStyle: {
            fill: 'rgba(0, 0, 0, 0.7)',
            fillOpacity: 0.8,
          },
          zIndex: 1001, // Conditional edges slightly higher than regular edges
        });
      });
    }
  });

  // Detect and update bidirectional edges to use smoothstep type
  const edgeMap = new Map<string, Edge>();
  const bidirectionalPairs = new Set<string>();

  // Create a map of edges by their connection pair
  edges.forEach(edge => {
    const key1 = `${edge.source}-${edge.target}`;
    const key2 = `${edge.target}-${edge.source}`;
    
    edgeMap.set(key1, edge);
    
    // Check if reverse edge exists
    if (edgeMap.has(key2)) {
      bidirectionalPairs.add(key1);
      bidirectionalPairs.add(key2);
    }
  });

  // Update bidirectional edges to use smoothstep type
  const updatedEdges = edges.map(edge => {
    const edgeKey = `${edge.source}-${edge.target}`;
    if (bidirectionalPairs.has(edgeKey)) {
      return {
        ...edge,
        type: "smoothstep",
      };
    }
    return edge;
  });

  return { nodes, edges: updatedEdges };
};

type ReactFlowGraphProps = {
  blueprintId?: string;
  height?: string;
  showControls?: boolean;
  showMiniMap?: boolean;
  showBackground?: boolean;
  interactive?: boolean;
  streamingDataContext?: any;
  isLiveRequest?: boolean; // Optional parameter for live tracking
  validationResults?: Record<string, ElementValidationResult>;
  isValidating?: boolean;
};

export default function ReactFlowGraph({
  blueprintId,
  height = "400px",
  showControls = true,
  showMiniMap = true,
  showBackground = true,
  interactive = true,
  streamingDataContext = null,
  isLiveRequest = false,
  validationResults,
  isValidating = false,
}: ReactFlowGraphProps): React.ReactElement {
  const [nodes, setNodes, onNodesChange] = useNodesState<EnhancedNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [nodeStatusMap, setNodeStatusMap] = useState<
    Record<string, NodeStatus>
  >({});
  
  // Validation modal state
  const [selectedValidationResult, setSelectedValidationResult] = useState<ElementValidationResult | null>(null);
  const [isValidationModalOpen, setIsValidationModalOpen] = useState(false);
  
  // Handler to show validation details for a node
  const handleShowValidationDetails = useCallback((result: ElementValidationResult) => {
    setSelectedValidationResult(result);
    setIsValidationModalOpen(true);
  }, []);

  const { fitView, zoomOut } = useReactFlow();
  const initializedRef = useRef(false);
  const streamingContext = isLiveRequest ? useStreamingData() : null;
  const prevNodeListRef = useRef<Map<string, any>>(new Map());
  const { user } = useAuth();
  const { fetchResourceById } = useWorkspaceData();

  // Function to update node status based on streaming data
  const updateNodeStatuses = useCallback(() => {
    if (!streamingContext) return;

    const currentNodeList = streamingContext.nodeListRef.current;
    const newStatusMap: Record<string, NodeStatus> = {};

    // Process current streaming data
    currentNodeList.forEach((nodeEntry, nodeId) => {
      if (nodeEntry.stream === "PROGRESS") {
        newStatusMap[nodeId] = "PROGRESS";
      } else if (nodeEntry.stream === "DONE") {
        newStatusMap[nodeId] = "DONE";
      } else {
        newStatusMap[nodeId] = "IDLE";
      }
    });

    // Check if there are any changes from previous state
    const hasChanges =
      JSON.stringify(newStatusMap) !== JSON.stringify(nodeStatusMap);

    if (hasChanges) {
      setNodeStatusMap(newStatusMap);

      // Update nodes with new status
      setNodes((currentNodes) =>
        currentNodes.map((node) => ({
          ...node,
          data: {
            ...node.data,
            status: newStatusMap[node.id] || "IDLE",
          },
        })),
      );
    }

    // Store current state for next comparison
    prevNodeListRef.current = new Map(currentNodeList);
  }, [streamingContext, nodeStatusMap, setNodes]);

  // Effect to monitor streaming data changes when live tracking is enabled
  useEffect(() => {
    if (!isLiveRequest || !streamingContext) return;

    // Initial status update
    updateNodeStatuses();

    // Set up interval to check for changes
    const intervalId = setInterval(() => {
      updateNodeStatuses();
    }, 100); // Check every 100ms for responsiveness

    return () => {
      clearInterval(intervalId);
    };
  }, [isLiveRequest, streamingContext, updateNodeStatuses]);

  // Reset node statuses when live tracking is disabled
  useEffect(() => {
    if (!isLiveRequest) {
      setNodes((currentNodes) =>
        currentNodes.map((node) => ({
          ...node,
          data: {
            ...node.data,
            // TODO: Due to time sync issues, some of the nodes might still hold "PROGRESS" status once reaching over here
            // status: (nodeStatusMap[node.id] == "DONE") ? nodeStatusMap[node.id] : 'IDLE' as NodeStatus
            status:
              nodeStatusMap[node.id] != "IDLE"
                ? "DONE"
                : ("IDLE" as NodeStatus),
          },
        })),
      );
      setNodeStatusMap({});
    }
  }, [isLiveRequest, setNodes]);

  // Function to convert graph flow JSON to ReactFlow format
  const convertGraphFlowToReactFlow = async (graphId: string) => {
    try {
      setIsLoading(true);
      const response = await axios.get(
        `/blueprints/available.blueprints.resolved.get?userId=${user?.username || "default"}`,
      );
      const blueprintObjects = response.data;

      // Find the specific graph flow by blueprint_id
      const targetBlueprintObj = blueprintObjects.find(
        (blueprintObj: any) =>
          blueprintObj.blueprint_id === graphId
      );

      if (targetBlueprintObj) {
        const { nodes: newNodes, edges: newEdges } =
          parseGraphFlow(targetBlueprintObj.spec_dict, fetchResourceById);

        setNodes(newNodes);
        setEdges(newEdges);

        // Auto-fit and zoom after loading
        setTimeout(() => {
          fitView({ padding: 0.2 });
          setTimeout(() => {
            zoomOut();
          }, 200);
        }, 100);
      } else {
        console.warn(`Graph flow with ID ${graphId} not found`);
      }
    } catch (error) {
      console.error("Error loading graph flow:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // Load graph when blueprintId changes
  useEffect(() => {
    if (blueprintId) {
      convertGraphFlowToReactFlow(blueprintId);
    }
  }, [blueprintId]);

  // Auto-fit view when nodes/edges are loaded
  useEffect(() => {
    if (
      !initializedRef.current &&
      nodes.length > 0 &&
      edges.length > 0 &&
      !isLoading
    ) {
      initializedRef.current = true;

      setTimeout(() => {
        fitView({ padding: 0.2 });
        setTimeout(() => {
          zoomOut();
        }, 200);
      }, 100);
    }
  }, [nodes, edges, isLoading, fitView, zoomOut]);

  // Update nodes with validation data when validationResults, isValidating, or nodes length changes
  // Using nodes.length as dependency ensures this runs after nodes are loaded
  useEffect(() => {
    if (nodes.length === 0) return;
    
    // Skip if there's no validation data to apply
    if (!isValidating && Object.keys(validationResults || {}).length === 0) return;
    
    setNodes((currentNodes) =>
      currentNodes.map((node) => {
        // Look up validation result by node's workspaceData.rid (element_rid)
        const nodeRid = node.data.workspaceData?.rid;;
        const validationResult = nodeRid && validationResults ? validationResults[nodeRid] : undefined;
        
        return {
          ...node,
          data: {
            ...node.data,
            validationResult,
            isValidating,
            onShowValidationDetails: handleShowValidationDetails,
          },
        };
      })
    );
  }, [validationResults, isValidating, handleShowValidationDetails, nodes.length]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <div className="text-gray-400">Loading graph...</div>
      </div>
    );
  }

  return (
    <div className="relative" style={{ height }}>
      {/* Live Status Indicator */}
      {isLiveRequest && (
        <div className="absolute top-2 right-2 z-50 bg-black bg-opacity-70 text-white px-2 py-1 rounded text-xs flex items-center gap-2">
          <motion.div
            className="w-2 h-2 bg-green-400 rounded-full"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          Live Tracking
        </div>
      )}

      {/* Active Nodes Status Bar */}
      {isLiveRequest && Object.keys(nodeStatusMap).length > 0 && (
        <div className="absolute bottom-2 left-2 right-2 z-50 bg-black bg-opacity-80 text-white px-3 py-2 rounded-lg">
          <div className="flex flex-wrap gap-2 text-xs">
            {Object.entries(nodeStatusMap).map(([nodeId, status]) => {
              if (status === "IDLE") return null;

              const node = nodes.find((n) => n.id === nodeId);
              const nodeName = node?.data?.label || nodeId;

              return (
                <div
                  key={nodeId}
                  className={`flex items-center gap-1 px-2 py-1 rounded ${
                    status === "PROGRESS"
                      ? "bg-blue-500 bg-opacity-50"
                      : "bg-green-500 bg-opacity-50"
                  }`}
                >
                  <motion.div
                    className={`w-2 h-2 rounded-full ${
                      status === "PROGRESS" ? "bg-blue-400" : "bg-green-400"
                    }`}
                    animate={
                      status === "PROGRESS"
                        ? {
                            scale: [1, 1.2, 1],
                            opacity: [1, 0.7, 1],
                          }
                        : undefined
                    }
                    transition={
                      status === "PROGRESS"
                        ? {
                            duration: 1,
                            repeat: Infinity,
                          }
                        : undefined
                    }
                  />
                  <span className="truncate max-w-20">{nodeName}</span>
                  <span className="text-xs opacity-75">
                    {status === "PROGRESS" ? "Running" : "Done"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={interactive ? onNodesChange : undefined}
        onEdgesChange={interactive ? onEdgesChange : undefined}
        nodeTypes={nodeTypes}
        fitView
        elementsSelectable={interactive}
        nodesConnectable={interactive}
        nodesDraggable={interactive}
        edgesFocusable={interactive}
        defaultEdgeOptions={{
          type: "smoothstep",
          animated: true,
          style: { stroke: "#8A2BE2", strokeWidth: 3 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 20,
            height: 20,
            color: "#8A2BE2",
          },
        }}
        proOptions={{ hideAttribution: true }}
      >
        {showControls && <Controls />}
        {showMiniMap && <MiniMap />}
        {showBackground && <Background color="#aaa" gap={16} />}
      </ReactFlow>

      {/* Validation Result Modal */}
      <ValidationResultModal
        validationResult={selectedValidationResult}
        isOpen={isValidationModalOpen}
        onOpenChange={setIsValidationModalOpen}
        showRefreshButton={false}
      />
    </div>
  );
}
