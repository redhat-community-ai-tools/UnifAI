import React, { useState } from "react";
import {
  ReactFlowProvider,
  ReactFlow,
  Node,
  Edge,
  Connection,
  Background,
  Controls,
  NodeTypes,
  EdgeTypes,
  MarkerType,
  ConnectionLineType,
} from "reactflow";
import "reactflow/dist/style.css";
import { Card, CardContent } from "@/components/ui/card";
import { Plus } from "lucide-react";
import CustomNode from "./CustomNode";
import CustomEdge from "./CustomEdge";
import BidirectionalOffsetEdge from "./BidirectionalOffsetEdge";
import GraphHeader from "./GraphHeader";
import * as yaml from 'js-yaml';

const nodeTypes: NodeTypes = {
  custom: CustomNode,
};

const edgeTypes: EdgeTypes = {
  custom: CustomEdge,
  bidirectionalOffset: BidirectionalOffsetEdge,
};

// Helper function to detect and mark bidirectional edge pairs
const processBidirectionalEdges = (edges: Edge[]): Edge[] => {
  const edgeMap = new Map<string, Edge[]>();
  const processedEdges: Edge[] = [];

  // Group edges by node pairs (regardless of direction)
  edges.forEach(edge => {
    const key1 = `${edge.source}-${edge.target}`;
    const key2 = `${edge.target}-${edge.source}`;
    
    // Check if reverse edge already exists
    const existingKey = edgeMap.has(key1) ? key1 : edgeMap.has(key2) ? key2 : key1;
    
    if (!edgeMap.has(existingKey)) {
      edgeMap.set(existingKey, []);
    }
    edgeMap.get(existingKey)!.push(edge);
  });

  // Process each edge group
  edgeMap.forEach((edgeGroup, key) => {
    if (edgeGroup.length === 2) {
      // Bidirectional pair detected - keep both edges but mark them
      const [edge1, edge2] = edgeGroup;
      
      // Determine which edge goes "up" and which goes "down" based on node positions
      // For now, we'll use a simple rule: first edge gets offset to the right, second to the left
      
      const offsetEdge1: Edge = {
        ...edge1,
        type: 'bidirectionalOffset',
        data: {
          ...edge1.data,
          bidirectionalPair: true,
          offsetDirection: 'right', // Offset to the right
          pairId: edge2.id,
        },
        style: {
          stroke: '#10B981',
          strokeWidth: 2.5,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 20,
          height: 20,
          color: '#10B981',
        },
      };
      
      const offsetEdge2: Edge = {
        ...edge2,
        type: 'bidirectionalOffset',
        data: {
          ...edge2.data,
          bidirectionalPair: true,
          offsetDirection: 'left', // Offset to the left
          pairId: edge1.id,
        },
        style: {
          stroke: '#10B981',
          strokeWidth: 2.5,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 20,
          height: 20,
          color: '#10B981',
        },
      };
      
      processedEdges.push(offsetEdge1, offsetEdge2);
    } else if (edgeGroup.length === 1) {
      // Single directional edge - keep as is
      processedEdges.push(edgeGroup[0]);
    }
  });

  return processedEdges;
};

interface GraphCanvasProps {
  nodes: Node[];
  edges: Edge[];
  yamlFlow?: any;
  onNodesChange: (changes: any[]) => void;
  onEdgesChange: (changes: any[]) => void;
  onConnect: (params: Connection) => void;
  onDrop: (event: React.DragEvent) => void;
  onDragOver: (event: React.DragEvent) => void;
  onClearGraph: () => void;
  onSaveGraph: () => void;
  onDeleteEdge?: (edgeId: string) => void;
  onBack?: () => void;
  onAttachCondition?: (nodeId: string, condition: any) => void;
  onRemoveCondition?: (nodeId: string, conditionRid: string) => void;
  isGraphValid?: boolean;
}

const GraphCanvas: React.FC<GraphCanvasProps> = ({
  nodes,
  edges,
  yamlFlow,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onDrop,
  onDragOver,
  onClearGraph,
  onSaveGraph,
  onDeleteEdge,
  onBack,
  onAttachCondition,
  onRemoveCondition,
  isGraphValid = false,
}) => {
  const [showYamlDebug, setShowYamlDebug] = useState(false);
  
  // Process edges to detect and transform bidirectional connections
  const processedEdges = processBidirectionalEdges(edges);

  return (
    <div className="flex-1 relative">
      <Card className="bg-background-card shadow-card border-gray-800 h-full">
        <GraphHeader
          onClearGraph={onClearGraph}
          onSaveGraph={onSaveGraph}
          onBack={onBack}
          isGraphValid={isGraphValid}
        />
        <CardContent className="p-0 h-full relative">
          {/* YAML Debug Panel */}
          {showYamlDebug && yamlFlow && (
            <div className="absolute top-4 right-4 z-50 bg-gray-900 border border-gray-700 rounded-lg p-4 max-w-md max-h-96 overflow-auto">
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-sm font-medium text-white">YAML Flow State</h3>
                <button
                  onClick={() => setShowYamlDebug(false)}
                  className="text-gray-400 hover:text-white"
                >
                  ×
                </button>
              </div>
              <pre className="text-xs text-gray-300 overflow-auto">
                {yaml.dump(yamlFlow, { indent: 2, lineWidth: -1 })}
              </pre>
            </div>
          )}

          {/* YAML Debug Toggle Button */}
          <button
            onClick={() => setShowYamlDebug(!showYamlDebug)}
            className="absolute top-4 right-4 z-40 bg-gray-800 hover:bg-gray-700 text-white px-3 py-1 text-xs rounded border border-gray-600"
          >
            {showYamlDebug ? 'Hide' : 'Show'} YAML
          </button>

          <div className="h-full" style={{ height: "calc(100vh - 180px)" }}>
            <ReactFlowProvider>
              <ReactFlow
                nodes={nodes}
                edges={processedEdges.map(edge => ({
                  ...edge,
                  type: edge.type || 'custom',
                  data: {
                    ...edge.data,
                    onDelete: onDeleteEdge,
                  }
                }))}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onDrop={onDrop}
                onDragOver={onDragOver}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
                defaultViewport={{ x: 0, y: 0, zoom: 0.33 }}
                connectionLineType={ConnectionLineType.SmoothStep}
                defaultEdgeOptions={{
                  type: "custom",
                  animated: true,
                  style: { stroke: "#8A2BE2", strokeWidth: 2 },
                  markerEnd: {
                    type: MarkerType.ArrowClosed,
                    width: 20,
                    height: 20,
                    color: "#8A2BE2",
                  },
                }}
              >
                <Background color="#aaa" gap={16} />
                <Controls />
              </ReactFlow>
            </ReactFlowProvider>

            {/* Drop zone overlay when empty */}
            {nodes.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="text-center">
                  <Plus className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                  <h3 className="mt-2 text-sm font-medium text-gray-300">
                    No nodes yet
                  </h3>
                  <p className="mt-1 text-sm text-gray-400">
                    Drag building blocks from the sidebar to get started
                  </p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default GraphCanvas;