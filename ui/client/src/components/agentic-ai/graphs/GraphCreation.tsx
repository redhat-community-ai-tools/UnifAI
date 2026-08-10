import React, { useState, useMemo, useEffect, useCallback } from "react";
import { dia, linkTools } from "@joint/core";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus, Link2, X, GitBranch, Trash2, Loader2 } from "lucide-react";
import GraphHeader from "./GraphHeader";
import * as yaml from "js-yaml";
import { useTheme } from "@/contexts/ThemeContext";
import { deriveThemeColors } from "@/lib/colorUtils";
import { usePrimaryLightColor } from "@/hooks/use-primary-light-color";
import { useGraphCreationCanvas } from "@/hooks/use-graph-creation-canvas";
import { NODE_WIDTH, NODE_HEADER_HEIGHT, groupBadgesByNode } from "./GraphDisplayHelpers";
import { AgentNodeOverlay } from "./AgentNodeOverlay";
import { ZoomControls } from "./ZoomControls";
import ResourceDetailsModal from "@/workspace/ResourceDetailsModal";
import type { CanvasNode, CanvasEdge, BuildingBlock, YamlFlowState } from "@/types/graph";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface GraphCreationProps {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  yamlFlow?: YamlFlowState;
  onDrop: (event: React.DragEvent, localPosition?: { x: number; y: number }) => void;
  onDragOver: (event: React.DragEvent) => void;
  onClearGraph: () => void;
  onSaveGraph: () => void;
  onDeleteNode?: (nodeId: string) => void;
  onDeleteEdge?: (edgeId: string) => void;
  onBack?: () => void;
  isGraphValid?: boolean;
  onNodeClick?: (nodeId: string) => void;
  onPaneClick?: () => void;
  onNodePositionChange?: (nodeId: string, pos: { x: number; y: number }) => void;
  pendingConnectionSource?: string | null;
  onCancelConnection?: () => void;
  onAttachCondition?: (nodeId: string, condition: BuildingBlock) => void;
  onDragEnd?: () => void;
  isEditMode?: boolean;
  isLoadingBlueprint?: boolean;
}

// ---------------------------------------------------------------------------
// Connection banner
// ---------------------------------------------------------------------------

function ConnectionBanner({
  pendingConnectionSource,
  nodes,
  paperTransform,
  edgeColor,
  accentColor,
  onCancel,
}: {
  pendingConnectionSource: string;
  nodes: CanvasNode[];
  paperTransform: { sx: number; sy: number; tx: number; ty: number };
  edgeColor: string;
  accentColor: string;
  onCancel?: () => void;
}) {
  const sourceNode = nodes.find((n) => n.id === pendingConnectionSource);
  if (!sourceNode) return null;

  const centerX =
    (sourceNode.position.x + NODE_WIDTH / 2) * paperTransform.sx +
    paperTransform.tx;
  const topY = sourceNode.position.y * paperTransform.sy + paperTransform.ty;
  const sourceLabel = sourceNode.data?.label || pendingConnectionSource;

  return (
    <div
      className="absolute z-40 flex items-center gap-3 text-white px-4 py-2.5 rounded-xl shadow-xl backdrop-blur-md border whitespace-nowrap"
      style={{
        left: centerX,
        top: Math.max(topY - 56, 8),
        transform: "translateX(-50%)",
        background: `linear-gradient(to right, ${edgeColor}F2, ${edgeColor}CC)`,
        borderColor: `${accentColor}60`,
        pointerEvents: "auto",
      }}
    >
      <div
        className="flex items-center justify-center w-7 h-7 rounded-full border"
        style={{
          backgroundColor: `${edgeColor}30`,
          borderColor: `${accentColor}40`,
        }}
      >
        <Link2
          className="w-3.5 h-3.5 animate-pulse"
          style={{ color: accentColor }}
        />
      </div>
      <span className="text-sm font-medium">
        Select a target to connect{" "}
        <span className="font-semibold" style={{ color: accentColor }}>
          {sourceLabel}
        </span>
      </span>
      <button
        onClick={onCancel}
        className="ml-1 p-1 rounded-md text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
        title="Cancel (ESC)"
        aria-label="Cancel connection"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Creation-specific overlays (delete button, glow, conditions, drop zone)
//
// ONLY interactive controls get pointer-events-auto — everything else stays
// pointer-events-none so JointJS receives clicks and drags directly.
// ---------------------------------------------------------------------------

function CreationControls({
  nodeId,
  node,
  x,
  y,
  width,
  nodeHeight,
  selected,
  isConnectionSource,
  primaryHex,
  conditionAccent,
  conditionCardBg,
  conditionCardBorder,
  onDelete,
  onAttachCondition,
  isDraggingCondition,
}: {
  nodeId: string;
  node: CanvasNode;
  x: number;
  y: number;
  width: number;
  nodeHeight: number;
  selected: boolean;
  isConnectionSource: boolean;
  primaryHex: string;
  conditionAccent: string;
  conditionCardBg: string;
  conditionCardBorder: string;
  onDelete?: (nodeId: string) => void;
  onAttachCondition?: (nodeId: string, condition: BuildingBlock) => void;
  isDraggingCondition: boolean;
}) {
  const isProtected = nodeId === "user_input" || nodeId === "finalize";
  const conditions: BuildingBlock[] = node.data.referencedConditions || [];
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
    e.dataTransfer.dropEffect = "copy";
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const blockData = e.dataTransfer.getData("application/unifai-block");
      if (blockData && onAttachCondition) {
        try {
          const condition = JSON.parse(blockData);
          if (condition.workspaceData?.category === "conditions") {
            onAttachCondition(nodeId, condition);
          }
        } catch {
          // Ignore malformed drag data
        }
      }
    },
    [nodeId, onAttachCondition],
  );

  return (
    <>
      {/* Pulsing glow ring for connection source node */}
      {isConnectionSource && (
        <div
          className="absolute node-glow-animation"
          style={{
            left: x - 4,
            top: y - 4,
            width: width + 8,
            height: nodeHeight + 8,
            borderRadius: 14,
            pointerEvents: "none",
            animation: "node-connection-glow 2s ease-in-out infinite",
            "--node-glow-color": `${primaryHex}80`,
          } as React.CSSProperties}
        />
      )}

      {/* Source badge – positioned on the left so it doesn't overlap the delete button */}
      {isConnectionSource && (
        <div
          className="absolute"
          style={{
            left: x + 4,
            top: y + 4,
            pointerEvents: "none",
          }}
        >
          <span
            className="text-xs font-medium px-2 py-0.5 rounded-full"
            style={{
              background: "rgba(255,255,255,0.15)",
              color: "rgba(255,255,255,0.9)",
            }}
          >
            Source
          </span>
        </div>
      )}

      {/* Delete button */}
      {(selected || isConnectionSource) && !isProtected && (
        <button
          className="absolute pointer-events-auto w-5 h-5 text-gray-400 hover:text-red-400 transition-colors flex items-center justify-center"
          style={{
            left: x + width - 24,
            top: y + (NODE_HEADER_HEIGHT - 20) / 2,
          }}
          title="Delete node"
          aria-label="Delete node"
          onClick={(e) => {
            e.stopPropagation();
            onDelete?.(nodeId);
          }}
        >
          <X className="w-4 h-4" />
        </button>
      )}

      {/* Condition drop zone – activates only during condition drags */}
      {isDraggingCondition && (
        <div
          className="absolute pointer-events-auto"
          style={{
            left: x,
            top: y,
            width,
            height: nodeHeight,
            borderRadius: 12,
            border: isDragOver
              ? `2px dashed ${conditionAccent}`
              : "2px dashed transparent",
            background: isDragOver ? `${conditionAccent}20` : "transparent",
            transition: "border-color 150ms, background 150ms",
            zIndex: 5,
          }}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        />
      )}

      {/* Conditions section */}
      {conditions.length > 0 && (
        <div
          className="absolute"
          style={{
            left: x + 8,
            top: y + NODE_HEADER_HEIGHT + 4,
            width: width - 16,
            pointerEvents: "none",
          }}
        >
          <div
            className="flex items-center gap-2 text-xs font-medium mb-1"
            style={{ color: conditionAccent }}
          >
            <GitBranch className="w-3 h-3" />
            Conditions
          </div>
          {conditions.map((cond) => (
            <div
              key={cond.id}
              className="rounded px-2 py-1 mb-1 flex items-center justify-between border"
              style={{
                backgroundColor: conditionCardBg,
                borderColor: conditionCardBorder,
              }}
            >
              <div className="flex items-center gap-2">
                <div
                  className="w-4 h-4 rounded flex items-center justify-center"
                  style={{ backgroundColor: conditionAccent }}
                >
                  <GitBranch className="w-2 h-2 text-white" />
                </div>
                <span className="text-xs text-white">{cond.label}</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                aria-label="Remove condition"
                className="h-5 w-5 p-0 text-red-400 hover:text-red-300 pointer-events-auto"
                onClick={(e) => {
                  e.stopPropagation();
                  node.data.onRemoveCondition?.(
                    nodeId,
                    cond.workspaceData?.rid || cond.id,
                  );
                }}
              >
                <Trash2 className="w-3 h-3" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const GraphCreation: React.FC<GraphCreationProps> = ({
  nodes,
  edges,
  yamlFlow,
  onDrop,
  onDragOver,
  onClearGraph,
  onSaveGraph,
  onDeleteNode,
  onDeleteEdge,
  onBack,
  isGraphValid = false,
  onNodeClick,
  onPaneClick,
  onNodePositionChange,
  pendingConnectionSource = null,
  onCancelConnection,
  onAttachCondition,
  onDragEnd,  
  isEditMode,
  isLoadingBlueprint = false,
}) => {
  const [showYamlDebug, setShowYamlDebug] = useState(false);
  const [isDraggingCondition, setIsDraggingCondition] = useState(false);
  const [resourceDetailsOpen, setResourceDetailsOpen] = useState(false);
  const [resourceDetailsElement, setResourceDetailsElement] = useState<BuildingBlock | null>(null);
  const { primaryHex } = useTheme();

  // Reset condition-drag state when any drag operation finishes.
  // Without this, a drop intercepted by CreationControls (which calls
  // stopPropagation) would leave isDraggingCondition=true, keeping a
  // pointer-events-auto overlay over the node and blocking interaction.
  useEffect(() => {
    const reset = () => setIsDraggingCondition(false);
    document.addEventListener("dragend", reset);
    return () => document.removeEventListener("dragend", reset);
  }, []);

  const accentColor = usePrimaryLightColor();
  const {
    primary: edgeColor,
    conditionAccent,
    conditionCardBg,
    conditionCardBorder,
  } = useMemo(() => deriveThemeColors(primaryHex), [primaryHex]);

  const {
    containerRef,
    paperRef,
    graphRef,
    overlayHeaders,
    overlayBadges,
    paperTransform,
    handleZoomIn,
    handleZoomOut,
    handleFitToView,
    clientToLocalPoint,
  } = useGraphCreationCanvas({
    nodes,
    edges,
    primaryHex,
    onNodeClick,
    onPaneClick,
    onNodePositionChange,
  });

  // Fit to view once after initial nodes are placed
  const didInitialFitRef = React.useRef(false);
  useEffect(() => {
    if (nodes.length < 2) {
      didInitialFitRef.current = false;
      return;
    }
    if (didInitialFitRef.current) return;
    didInitialFitRef.current = true;
    const t = setTimeout(() => handleFitToView(), 80);
    return () => clearTimeout(t);
  }, [nodes.length, handleFitToView]);

  // ── Edge delete tools via JointJS link tools ──
  useEffect(() => {
    const paper = paperRef.current;
    if (!paper || !onDeleteEdge) return;

    const onLinkEnter = (linkView: dia.LinkView) => {
      const edgeId = linkView.model.id as string;
      const removeButton = new linkTools.Remove({
        distance: "50%",
        action: () => {
          onDeleteEdge(edgeId);
        },
      });
      const tools = new dia.ToolsView({ tools: [removeButton] });
      linkView.addTools(tools);
    };

    const onLinkLeave = (linkView: dia.LinkView) => {
      linkView.removeTools();
    };

    paper.on("link:mouseenter", onLinkEnter);
    paper.on("link:mouseleave", onLinkLeave);

    return () => {
      paper.off("link:mouseenter", onLinkEnter);
      paper.off("link:mouseleave", onLinkLeave);
    };
  }, [paperRef, onDeleteEdge]);

  // ── Wrapped drop handler – converts coordinates to paper-local space
  //    and handles condition drops via JointJS hit-testing ──
  const handleCanvasDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const blockData = event.dataTransfer.getData("application/unifai-block");
      if (!blockData) return;

      let block: any;
      try {
        block = JSON.parse(blockData);
      } catch {
        return;
      }
      const isCondition = block.workspaceData?.category === "conditions";

      if (isCondition) {
        const graph = graphRef.current;
        const paper = paperRef.current;
        if (graph && paper) {
          const localPoint = paper.clientToLocalPoint({
            x: event.clientX,
            y: event.clientY,
          });

          const targetEl = graph.getElements().find((el) => {
            const bbox = el.getBBox();
            return (
              localPoint.x >= bbox.x &&
              localPoint.x <= bbox.x + bbox.width &&
              localPoint.y >= bbox.y &&
              localPoint.y <= bbox.y + bbox.height
            );
          });

          if (targetEl && onAttachCondition) {
            onAttachCondition(targetEl.id as string, block);
            setIsDraggingCondition(false);
            onDragEnd?.();
            return;
          }
        }

        setIsDraggingCondition(false);
        onDrop(event);
        return;
      }

      // Convert screen coordinates to paper-local space and pass directly
      // to onDrop so it doesn't need to read event.currentTarget.
      const localPoint = clientToLocalPoint(event.clientX, event.clientY);
      const position = { x: localPoint.x - 75, y: localPoint.y - 25 };

      onDrop(event, position);
    },
    [onDrop, onAttachCondition, onDragEnd, graphRef, paperRef, clientToLocalPoint],
  );

  // Track condition drag state from dragover events
  const handleCanvasDragOver = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      // Peek at the data to detect condition drags.
      // During dragover the data isn't readable (security), so we infer from
      // the drag effect set by onDragStart in use-graph-creation-logic:
      // conditions get effectAllowed="copy", nodes get "move".
      const isCond = event.dataTransfer.effectAllowed === "copy";
      if (isCond !== isDraggingCondition) {
        setIsDraggingCondition(isCond);
      }
      onDragOver(event);
    },
    [onDragOver, isDraggingCondition],
  );

  // Build quick lookups
  const nodeById = useMemo(() => {
    const map = new Map<string, CanvasNode>();
    for (const n of nodes) map.set(n.id, n);
    return map;
  }, [nodes]);

  const badgesByNode = useMemo(
    () => groupBadgesByNode(overlayBadges),
    [overlayBadges],
  );

  const openElementDetails = useCallback(
    (elementId: string) => {
      for (const n of nodes) {
        const blocks = n.data.allBlocks || [];
        const block = blocks.find(
          (b) => b.id === elementId || b.workspaceData?.rid === elementId,
        );
        if (block) {
          setResourceDetailsElement(block);
          setResourceDetailsOpen(true);
          return;
        }
      }
    },
    [nodes],
  );

  return (
    <>
    <div className="flex-1 relative">
      <Card className="bg-background-card shadow-card border-gray-800 h-full">
        <GraphHeader
          onClearGraph={onClearGraph}
          onSaveGraph={onSaveGraph}
          onBack={onBack}
          isGraphValid={isGraphValid}
          isEditMode={isEditMode}
        />
        <CardContent className="p-0 h-full relative">
          {/* YAML debug panel */}
          {showYamlDebug && yamlFlow && (
            <div className="absolute top-4 right-4 z-50 bg-gray-900 border border-gray-700 rounded-lg max-w-md max-h-96 flex flex-col overflow-hidden">
              <div className="flex justify-between items-center px-4 pt-4 pb-2 flex-shrink-0 border-b border-gray-700">
                <h3 className="text-sm font-medium text-white">
                  YAML Flow State
                </h3>
                <button
                  type="button"
                  onClick={() => setShowYamlDebug(false)}
                  className="text-gray-400 hover:text-white"
                  aria-label="Close YAML panel"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <pre className="text-xs text-gray-300 overflow-auto p-4 flex-1 min-h-0">
                {yaml.dump(yamlFlow, { indent: 2, lineWidth: -1 })}
              </pre>
            </div>
          )}

          <button
            onClick={() => setShowYamlDebug(!showYamlDebug)}
            className="absolute top-4 right-4 z-40 bg-gray-800 hover:bg-gray-700 text-white px-3 py-1 text-xs rounded border border-gray-600"
          >
            {showYamlDebug ? "Hide" : "Show"} YAML
          </button>

          {/* Main canvas area */}
          <div
            className="h-full relative"
            style={{ height: "calc(100vh - 180px)" }}
            onDrop={handleCanvasDrop}
            onDragOver={handleCanvasDragOver}
          >
            {/* Connection banner */}
            {pendingConnectionSource && (
              <ConnectionBanner
                pendingConnectionSource={pendingConnectionSource}
                nodes={nodes}
                paperTransform={paperTransform}
                edgeColor={edgeColor}
                accentColor={accentColor}
                onCancel={onCancelConnection}
              />
            )}

            {/* Zoom controls */}
            <ZoomControls
              onZoomIn={handleZoomIn}
              onZoomOut={handleZoomOut}
              onFitToView={handleFitToView}
            />

            {/* JointJS paper container */}
            <div
              ref={containerRef}
              className="min-h-full min-w-full h-full"
              style={{ height: "100%" }}
            />

            {/* HTML overlay layer – mirrors the paper transform.
                pointer-events-none on the wrapper lets JointJS receive
                all clicks and drags. Only specific interactive controls
                inside CreationControls get pointer-events-auto. */}
            {(overlayHeaders.length > 0 || overlayBadges.length > 0) && (
              <div
                className="absolute inset-0 pointer-events-none"
                style={{ overflow: "hidden" }}
              >
                <div
                  style={{
                    transformOrigin: "0 0",
                    transform: `matrix(${paperTransform.sx}, 0, 0, ${paperTransform.sy}, ${paperTransform.tx}, ${paperTransform.ty})`,
                  }}
                >
                  {overlayHeaders.map((hdr) => {
                    const node = nodeById.get(hdr.nodeId);
                    if (!node) return null;
                    return (
                      <React.Fragment key={hdr.nodeId}>
                        <AgentNodeOverlay
                          hdr={hdr}
                          badges={badgesByNode.get(hdr.nodeId) || []}
                          nodeStatus={undefined}
                          sx={paperTransform.sx}
                          isValidating={false}
                          interactive={false}
                          previewMode
                          onValidationClick={() => {}}
                          onBadgeClick={openElementDetails}
                        />
                        <CreationControls
                          nodeId={hdr.nodeId}
                          node={node}
                          x={hdr.x}
                          y={hdr.y}
                          width={hdr.width}
                          nodeHeight={hdr.nodeHeight}
                          selected={!!node.selected}
                          isConnectionSource={!!node.data.isConnectionSource}
                          primaryHex={primaryHex}
                          conditionAccent={conditionAccent}
                          conditionCardBg={conditionCardBg}
                          conditionCardBorder={conditionCardBorder}
                          onDelete={onDeleteNode}
                          onAttachCondition={onAttachCondition}
                          isDraggingCondition={isDraggingCondition}
                        />
                      </React.Fragment>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Loading state for blueprint editing */}
            {isLoadingBlueprint && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-30">
                <div className="text-center">
                  <Loader2 className="mx-auto h-10 w-10 text-primary animate-spin mb-4" />
                  <h3 className="text-sm font-medium text-gray-300">
                    Loading workflow...
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Reconstructing nodes and connections
                  </p>
                </div>
              </div>
            )}

            {/* Empty state */}
            {nodes.length === 0 && !isLoadingBlueprint && (
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

      <ResourceDetailsModal
        isOpen={resourceDetailsOpen}
        onClose={() => setResourceDetailsOpen(false)}
        element={resourceDetailsElement}
      />
    </>
  );
};

export default GraphCreation;
