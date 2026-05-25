import React, { useContext, useEffect, useRef, useState, useCallback, useMemo } from "react";
import { dia } from "@joint/core";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { safeFlushSync } from "@/lib/reactUtils";
import { useTheme } from "@/contexts/ThemeContext";
import { useWorkspaceData } from "@/hooks/use-workspace-data";
import { useGraphDisplay } from "@/hooks/use-graph-display";
import { getCategoryDisplay } from "@/components/shared/helpers";
import type { BuildingBlock } from "@/types/graph";
import ResourceDetailsModal from "@/workspace/ResourceDetailsModal";
import { ValidationResultModal } from "../workspace/ValidationResultModal";
import type { ElementValidationResult } from "@/types/validation";
import { StreamingDataContext } from "../StreamingDataContext";
import {
  SCALE_CONTENT_TO_FIT_OPTS,
  STATUS_STYLES,
  groupBadgesByNode,
} from "./GraphDisplayHelpers";
import { AgentNodeOverlay, NodeStatus } from "./AgentNodeOverlay";
import { ZoomControls } from "./ZoomControls";

// ---------------------------------------------------------------------------
// Extracted sub-components (keep co-located — only used by GraphDisplay)
// ---------------------------------------------------------------------------

/** Bottom status bar showing per-node progress during live execution. */
function ActiveNodesStatusBar({
  nodeStatusMap,
  nodeLabelsMap,
}: {
  nodeStatusMap: Record<string, NodeStatus>;
  nodeLabelsMap: Record<string, string>;
}) {
  return (
    <div className="absolute bottom-2 left-2 right-2 z-50 bg-black bg-opacity-80 text-white px-3 py-2 rounded-lg">
      <div className="flex flex-wrap gap-2 text-xs">
        {Object.entries(nodeStatusMap).map(([nodeId, status]) => {
          if (status === "IDLE") return null;
          const nodeName = nodeLabelsMap[nodeId] || nodeId;
          return (
            <div
              key={nodeId}
              className={`flex items-center gap-1 px-2 py-1 rounded ${
                status === "PROGRESS"
                  ? "bg-blue-500 bg-opacity-50"
                  : status === "CANCELLED"
                    ? "bg-gray-500 bg-opacity-50"
                    : "bg-green-500 bg-opacity-50"
              }`}
            >
              <motion.div
                className={`w-2 h-2 rounded-full ${
                  status === "PROGRESS" ? "bg-blue-400" : status === "CANCELLED" ? "bg-gray-400" : "bg-green-400"
                }`}
                animate={
                  status === "PROGRESS"
                    ? { scale: [1, 1.2, 1], opacity: [1, 0.7, 1] }
                    : undefined
                }
                transition={
                  status === "PROGRESS"
                    ? { duration: 1, repeat: Infinity }
                    : undefined
                }
              />
              <span className="truncate max-w-20">{nodeName}</span>
              <span className="text-xs opacity-75">
                {status === "PROGRESS" ? "Running" : status === "CANCELLED" ? "Stopped" : "Done"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type GraphDisplayProps = {
  blueprintId?: string;
  /** Pre-fetched spec_dict – when provided, skips the network fetch entirely. */
  specDict?: any;
  height?: string;
  showBackground?: boolean;
  interactive?: boolean;
  /** Scale and center the graph in the container. */
  centerInView?: boolean;
  /** Enable subtle link animations. */
  animated?: boolean;
  /** Per-node validation results keyed by node RID. */
  validationResults?: Record<string, ElementValidationResult>;
  /** Whether validation is currently in progress. */
  isValidating?: boolean;
  /** Enable live node status tracking from streaming data. */
  isLiveRequest?: boolean;
  /** Whether the session was cancelled by the user. When true, nodes that
   *  were still in PROGRESS are marked CANCELLED instead of DONE. */
  isCancelled?: boolean;
  /** Whether the graph container is actually visible (not collapsed to zero
   *  width by carousel mode). Drives re-application of node visuals after
   *  the panel becomes visible again. Defaults to `true`. */
  isGraphVisible?: boolean;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function GraphDisplay({
  blueprintId,
  specDict,
  height = "100%",
  showBackground = true,
  interactive = false,
  centerInView = false,
  animated = false,
  validationResults,
  isValidating = false,
  isLiveRequest = false,
  isCancelled = false,
  isGraphVisible = true,
}: GraphDisplayProps): React.ReactElement {
  // ── JointJS graph hook (imperative init, layout, SVG injection) ─────
  const { primaryHex } = useTheme();

  const {
    containerRef,
    graphRef,
    paperRef,
    elementBlockRef,
    loading,
    error,
    overlayBadges,
    overlayHeaders,
    paperTransform,
    setPaperTransform,
    rebuildOverlays,
  } = useGraphDisplay({
    blueprintId,
    primaryHex,
    specDict,
    showBackground,
    interactive,
    centerInView,
    animated,
  });

  // Refs to hold latest validation data - allows accessing current values
  // during async operations. Mirrors the fix from PR #46 (ReactFlowGraph
  // timing issue): when graph loading completes, we can immediately read
  // whatever validation results are available without stale closures.
  const validationResultsRef = useRef(validationResults);
  const isValidatingRef = useRef(isValidating);

  useEffect(() => {
    validationResultsRef.current = validationResults;
    isValidatingRef.current = isValidating;
  }, [validationResults, isValidating]);

  // ── Component-level state ──────────────────────────────────────────
  const [resourceDetailsOpen, setResourceDetailsOpen] = useState(false);
  const [resourceDetailsElement, setResourceDetailsElement] =
    useState<BuildingBlock | null>(null);
  const [loadingResource, setLoadingResource] = useState(false);
  const [selectedValidationResult, setSelectedValidationResult] =
    useState<ElementValidationResult | null>(null);
  const [isValidationModalOpen, setIsValidationModalOpen] = useState(false);
  const [nodeStatusMap, setNodeStatusMap] = useState<Record<string, NodeStatus>>({});
  const nodeStatusMapRef = useRef<Record<string, NodeStatus>>({});

  // ── Hooks / context ─────────────────────────────────────────────────
  const { fetchResourceById } = useWorkspaceData();

  // Safe context access – returns null when no StreamingDataProvider is mounted
  // (e.g. AgenticOverview), avoiding the throw from useStreamingData().
  const streamingContext = useContext(StreamingDataContext);

  // ── Helper: apply status visual to a single JointJS element ────────

  const applyNodeVisual = useCallback(
    (el: dia.Element, status: NodeStatus | undefined) => {
      const s = STATUS_STYLES[status ?? "IDLE"];
      try {
        el.attr("body/stroke", s.stroke);
        el.attr("body/strokeWidth", s.strokeWidth);
        el.attr("body/filter", s.filter);
      } catch (e) {
        console.warn("[GraphDisplay] applyNodeVisual: SVGMatrix non-invertible (container likely collapsed to zero width)", e);
      }
    },
    [],
  );

  // ── Live node status tracking (ported from ReactFlowGraph) ─────────

  const updateNodeStatuses = useCallback(() => {
    if (!streamingContext) return;

    const currentNodeList = streamingContext.nodeListRef.current;
    const newStatusMap: Record<string, NodeStatus> = {};

    currentNodeList.forEach((nodeEntry, nodeId) => {
      if (nodeEntry.stream === "PROGRESS") newStatusMap[nodeId] = "PROGRESS";
      else if (nodeEntry.stream === "DONE") newStatusMap[nodeId] = "DONE";
      else newStatusMap[nodeId] = "IDLE";
    });

    // Shallow-compare against ref to avoid expensive JSON.stringify
    const prevMap = nodeStatusMapRef.current;
    const newKeys = Object.keys(newStatusMap);
    const prevKeys = Object.keys(prevMap);
    const hasChanges =
      newKeys.length !== prevKeys.length ||
      newKeys.some((k) => newStatusMap[k] !== prevMap[k]);

    if (hasChanges) {
      nodeStatusMapRef.current = newStatusMap;
      setNodeStatusMap(newStatusMap);

      const graph = graphRef.current;
      if (graph) {
        for (const el of graph.getElements()) {
          applyNodeVisual(el, newStatusMap[el.id as string] || "IDLE");
        }
      }
    }
  }, [streamingContext, applyNodeVisual, graphRef]);

  // Poll streaming data every 250 ms while live tracking is active
  useEffect(() => {
    if (!isLiveRequest || !streamingContext) return;
    updateNodeStatuses();
    const id = setInterval(updateNodeStatuses, 250);
    return () => clearInterval(id);
  }, [isLiveRequest, streamingContext, updateNodeStatuses]);

  // Track execution lifecycle for persistent completion state.
  // DONE states persist until the user starts a new execution or switches sessions
  // (switching sessions remounts the component via key change).
  const wasLiveRef = useRef(false);
  const [executionComplete, setExecutionComplete] = useState(false);

  // When a NEW execution starts → clear previous completion state and reset nodes
  useEffect(() => {
    if (isLiveRequest) {
      wasLiveRef.current = true;
      setExecutionComplete(false);

      // Reset any lingering DONE states from a previous execution
      const graph = graphRef.current;
      if (graph) {
        for (const el of graph.getElements()) {
          applyNodeVisual(el, "IDLE");
        }
      }
      nodeStatusMapRef.current = {};
      setNodeStatusMap({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLiveRequest]);

  // When execution ends → mark nodes with their final status.
  // On cancellation: PROGRESS → CANCELLED, DONE stays DONE, IDLE stays IDLE.
  // On normal completion: PROGRESS → DONE, DONE stays DONE, IDLE stays IDLE.
  useEffect(() => {
    if (!isLiveRequest && wasLiveRef.current) {
      wasLiveRef.current = false;
      setExecutionComplete(true);

      const graph = graphRef.current;
      if (graph) {
        const prevMap = nodeStatusMapRef.current;
        const finalMap: Record<string, NodeStatus> = {};
        for (const el of graph.getElements()) {
          const id = el.id as string;
          const prev = prevMap[id];
          let finalStatus: NodeStatus;
          if (isCancelled && prev === "PROGRESS") {
            finalStatus = "CANCELLED";
          } else if (prev === "DONE") {
            finalStatus = "DONE";
          } else if (!isCancelled && prev === "PROGRESS") {
            finalStatus = "DONE";
          } else {
            finalStatus = "IDLE";
          }
          applyNodeVisual(el, finalStatus);
          finalMap[id] = finalStatus;
        }
        nodeStatusMapRef.current = finalMap;
        setNodeStatusMap(finalMap);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLiveRequest]);

  // Re-apply node status visuals when the graph transitions from hidden
  // (e.g. chat carousel mode where the panel is collapsed to width:0) back
  // to visible.  While hidden, el.attr() calls silently fail because the
  // SVG transform matrix is non-invertible, so the elements carry stale
  // visuals.  We use the explicit `isGraphVisible` prop from the parent
  // (derived from carouselMode) instead of guessing visibility from pixel
  // widths, which would be fragile if layout thresholds changed.
  //
  // The delay allows the CSS width transition to progress and the
  // ResizeObserver in use-graph-display.ts to re-fit the paper (10ms
  // debounce) before we call el.attr().
  const prevGraphVisibleRef = useRef(isGraphVisible);

  useEffect(() => {
    const wasHidden = !prevGraphVisibleRef.current;
    prevGraphVisibleRef.current = isGraphVisible;

    if (!wasHidden || !isGraphVisible) return;

    const timer = setTimeout(() => {
      const container = containerRef.current;
      const graph = graphRef.current;
      if (!container || !graph || container.clientWidth === 0) return;

      const currentMap = nodeStatusMapRef.current;
      for (const el of graph.getElements()) {
        applyNodeVisual(el, currentMap[el.id as string] || "IDLE");
      }
    }, 150);

    return () => clearTimeout(timer);
  }, [isGraphVisible, graphRef, containerRef, applyNodeVisual]);

  // ── Open resource details modal ────────────────────────────────────

  const openElementDetails = useCallback(
    (elementId: string) => {
      const block = elementBlockRef.current.get(elementId);
      if (block) {
        setResourceDetailsElement(block);
        setResourceDetailsOpen(true);
        return;
      }

      setLoadingResource(true);
      fetchResourceById(elementId)
        .then((resource) => {
          if (!resource) return;
          const display = getCategoryDisplay(resource.category);
          const built: BuildingBlock = {
            id: resource.rid,
            type: resource.type,
            label: resource.name,
            color: display.color,
            description: `${resource.category}/${resource.type} - ${resource.name}`,
            workspaceData: {
              rid: resource.rid,
              name: resource.name,
              category: resource.category,
              type: resource.type,
              config: resource.cfg_dict,
              version: resource.version ?? 1,
              created: resource.created ?? "",
              updated: resource.updated ?? "",
              nested_refs: resource.nested_refs ?? [],
            },
          };
          setResourceDetailsElement(built);
          setResourceDetailsOpen(true);
        })
        .catch((err) => { console.debug("[GraphDisplay] resource fetch failed:", err); })
        .finally(() => setLoadingResource(false));
    },
    [fetchResourceById, elementBlockRef],
  );

  // ── Zoom / fit-to-view handlers ─────────────────────────────────────

  const syncTransform = useCallback(() => {
    const paper = paperRef.current;
    if (!paper) return;
    const scale = paper.scale();
    const translate = paper.translate();
    safeFlushSync(() => {
      setPaperTransform({ sx: scale.sx, sy: scale.sy, tx: translate.tx, ty: translate.ty });
      rebuildOverlays();
    });
  }, [paperRef, setPaperTransform, rebuildOverlays]);

  const handleZoomIn = useCallback(() => {
    const paper = paperRef.current;
    if (!paper) return;
    const { sx } = paper.scale();
    const newScale = sx * 1.2;
    paper.scale(newScale, newScale);
    syncTransform();
  }, [paperRef, syncTransform]);

  const handleZoomOut = useCallback(() => {
    const paper = paperRef.current;
    if (!paper) return;
    const { sx } = paper.scale();
    const newScale = Math.max(sx * (1 / 1.2), 0.1);
    paper.scale(newScale, newScale);
    syncTransform();
  }, [paperRef, syncTransform]);

  const handleFitToView = useCallback(() => {
    const paper = paperRef.current;
    const container = containerRef.current;
    if (!paper) return;
    try {
      // Reset to identity transform first so we don't hit a non-invertible
      // SVGMatrix when the previous scale was degenerate (e.g. after panel collapse).
      paper.scale(1, 1);
      paper.translate(0, 0);
      // Re-set dimensions to current container size
      if (container) {
        const cw = container.clientWidth;
        const ch = container.clientHeight;
        if (cw > 0 && ch > 0) {
          paper.setDimensions(cw, ch);
        }
      }
      paper.transformToFitContent(SCALE_CONTENT_TO_FIT_OPTS);
    } catch (e) {
      console.warn("[GraphDisplay] handleFitToView: SVGMatrix error, user can retry", e);
      return;
    }
    syncTransform();
  }, [paperRef, containerRef, syncTransform]);

  // ── Derived data for render ─────────────────────────────────────────

  const nodeLabelsMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const h of overlayHeaders) map[h.nodeId] = h.label;
    return map;
  }, [overlayHeaders]);

  const badgesByNode = useMemo(
    () => groupBadgesByNode(overlayBadges),
    [overlayBadges],
  );

  // ── JSX ─────────────────────────────────────────────────────────────

  return (
    <>
      <div className="relative overflow-auto" style={{ height }}>
        {/* Live Tracking / Execution Complete Indicator */}
        {streamingContext && (isLiveRequest || executionComplete) && (
          <div className="absolute top-2 left-2 z-50 bg-black bg-opacity-70 text-white px-2 py-1 rounded text-xs flex items-center gap-2">
            {isLiveRequest ? (
              <>
                <motion.div
                  className="w-2 h-2 bg-green-400 rounded-full"
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
                Live Tracking
              </>
            ) : isCancelled ? (
              <>
                <div className="w-2 h-2 bg-gray-400 rounded-full" />
                Session Stopped
              </>
            ) : (
              <>
                <div className="w-2 h-2 bg-green-400 rounded-full" />
                Execution Complete
              </>
            )}
          </div>
        )}

        {/* Zoom Controls */}
        {interactive && (
          <ZoomControls
            onZoomIn={handleZoomIn}
            onZoomOut={handleZoomOut}
            onFitToView={handleFitToView}
          />
        )}

        {/* Active Nodes Status Bar – persists after execution so user sees final state */}
        {streamingContext && (isLiveRequest || executionComplete) && Object.keys(nodeStatusMap).length > 0 && (
          <ActiveNodesStatusBar
            nodeStatusMap={nodeStatusMap}
            nodeLabelsMap={nodeLabelsMap}
          />
        )}

        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background-dark/80 text-gray-400">
            Loading graph...
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center text-gray-400">
            {error}
          </div>
        )}

        <div
          className={`workflow-graph-wrap h-full min-h-[280px] rounded-2xl relative ${
            animated ? "workflow-graph-animated" : ""
          }`}
        >
          <div
            ref={containerRef}
            className="min-h-full min-w-full h-full"
            style={{ height }}
          />

          {/* HTML overlay for node headers + element badges.
              A CSS-transform wrapper mirrors the JointJS paper viewport so
              overlays move in the exact same paint cycle as the SVG elements
              – no React-state lag for zoom, pan, or drag. */}
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
                {overlayHeaders.map((hdr) => (
                  <AgentNodeOverlay
                    key={hdr.nodeId}
                    hdr={hdr}
                    badges={badgesByNode.get(hdr.nodeId) || []}
                    nodeStatus={nodeStatusMap[hdr.nodeId]}
                    sx={paperTransform.sx}
                    validationResult={
                      hdr.nodeRid && validationResults
                        ? validationResults[hdr.nodeRid]
                        : undefined
                    }
                    isValidating={isValidating}
                    interactive={interactive}
                    onValidationClick={(result) => {
                      setSelectedValidationResult(result);
                      setIsValidationModalOpen(true);
                    }}
                    onBadgeClick={openElementDetails}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <ResourceDetailsModal
        isOpen={resourceDetailsOpen}
        onClose={setResourceDetailsOpen}
        element={resourceDetailsElement}
      />

      <ValidationResultModal
        validationResult={selectedValidationResult}
        isOpen={isValidationModalOpen}
        onOpenChange={setIsValidationModalOpen}
        showRefreshButton={false}
      />
    </>
  );
}
