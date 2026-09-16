/**
 * useGraphCreationCanvas – JointJS paper hook for the graph *creation* canvas.
 *
 * Unlike `useGraphDisplay` (which loads a saved blueprint), this hook takes
 * live `CanvasNode[]` / `CanvasEdge[]` arrays from `useGraphCreationLogic`
 * and keeps the JointJS graph imperatively synchronised with them.
 *
 * Provides: pan, zoom, node drag, overlay data, and paper coordinate helpers.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { dia, shapes } from "@joint/core";
import { DirectedGraph } from "@joint/layout-directed-graph";
import type { CanvasNode, CanvasEdge, BuildingBlock } from "@/types/graph";
import { safeFlushSync } from "@/lib/reactUtils";
import {
  NODE_WIDTH,
  NODE_HEADER_HEIGHT,
  ELEMENT_BADGE_HEIGHT,
  ELEMENT_GAP,
  NODE_BODY_PADDING,
  LAYOUT_OPTS,
  SCALE_CONTENT_TO_FIT_OPTS,
  STATUS_STYLES,
  nodeFillForType,
  injectSvgDefs,
  injectStatusGlowFilters,
  injectLinkAnimations,
  removeLinkAnimations,
} from "@/components/agentic-ai/graphs/GraphDisplayHelpers";
import type {
  OverlayHeader,
  OverlayBadge,
} from "@/components/agentic-ai/graphs/GraphDisplayHelpers";
import type { ResolvedElement } from "@/utils/graphFlowLayout";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseGraphCreationCanvasOptions {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  primaryHex?: string;
  onNodeClick?: (nodeId: string) => void;
  onPaneClick?: () => void;
  onNodePositionChange?: (nodeId: string, position: { x: number; y: number }) => void;
}

export interface UseGraphCreationCanvasReturn {
  containerRef: React.RefObject<HTMLDivElement>;
  paperRef: React.MutableRefObject<dia.Paper | null>;
  graphRef: React.MutableRefObject<dia.Graph | null>;
  overlayHeaders: OverlayHeader[];
  overlayBadges: OverlayBadge[];
  paperTransform: { sx: number; sy: number; tx: number; ty: number };
  handleZoomIn: () => void;
  handleZoomOut: () => void;
  handleFitToView: () => void;
  runAutoLayout: () => void;
  clientToLocalPoint: (clientX: number, clientY: number) => { x: number; y: number };
}

function normalizePrimaryHex(raw: string | undefined | null): string {
  if (!raw) return "#8b5cf6";
  return raw.startsWith("#") ? raw : `#${raw}`;
}

// ---------------------------------------------------------------------------
// Condition layout constants
// ---------------------------------------------------------------------------
const CONDITION_LABEL_HEIGHT = 24;
const CONDITION_ITEM_HEIGHT = 28;

function computeCanvasNodeHeight(elementCount: number, conditionCount: number): number {
  let h = NODE_HEADER_HEIGHT;
  if (conditionCount > 0) {
    h += CONDITION_LABEL_HEIGHT + conditionCount * CONDITION_ITEM_HEIGHT;
  }
  if (elementCount > 0) {
    h += NODE_BODY_PADDING * 2 +
      elementCount * ELEMENT_BADGE_HEIGHT +
      Math.max(0, elementCount - 1) * ELEMENT_GAP;
  }
  return h;
}

// ---------------------------------------------------------------------------
// Resource extraction – resolves $ref: IDs to human-readable names
// via the allBlocks lookup that each node carries.
// ---------------------------------------------------------------------------

function extractResolvedElements(
  config: any,
  allBlocks: BuildingBlock[],
): ResolvedElement[] {
  if (!config || typeof config !== "object") return [];
  const elements: ResolvedElement[] = [];
  const seen = new Set<string>();

  const blockById = new Map<string, BuildingBlock>();
  for (const b of allBlocks) {
    blockById.set(b.id, b);
    if (b.workspaceData?.rid) blockById.set(b.workspaceData.rid, b);
  }

  const TYPE_MAP: Record<string, ResolvedElement["type"]> = {
    llm: "llm", llms: "llm",
    tool: "tool", tools: "tool",
    retriever: "retriever", retrievers: "retriever",
    provider: "provider", providers: "provider",
  };

  const traverse = (obj: any, key?: string) => {
    if (typeof obj === "string" && obj.startsWith("$ref:")) {
      const refId = obj.substring(5);
      if (!seen.has(refId)) {
        seen.add(refId);
        const block = blockById.get(refId);
        const matchedType = key ? TYPE_MAP[key.toLowerCase()] : undefined;
        const guessedType = block?.workspaceData?.category
          ? TYPE_MAP[block.workspaceData.category]
          : undefined;
        const blockConfig = block?.workspaceData?.config;
        elements.push({
          id: refId,
          name: block?.label ?? block?.workspaceData?.name ?? refId,
          type: matchedType || guessedType || "tool",
          config: blockConfig && typeof blockConfig === "object" ? blockConfig as Record<string, unknown> : undefined,
        });
      }
      return;
    }
    if (Array.isArray(obj)) {
      for (const item of obj) {
        traverse(item, key);
      }
      return;
    }
    if (typeof obj === "object" && obj !== null) {
      for (const [k, v] of Object.entries(obj)) {
        traverse(v, k);
      }
    }
  };

  traverse(config);
  return elements;
}

// ---------------------------------------------------------------------------
// Bidirectional edge detection
// ---------------------------------------------------------------------------

function detectBidirectionalEdges(edges: CanvasEdge[]): {
  bidirectionalIds: Set<string>;
  secondaryIds: Set<string>;
} {
  const bidirectionalIds = new Set<string>();
  const secondaryIds = new Set<string>();

  const directedPairs = new Set<string>();
  for (const e of edges) {
    directedPairs.add(`${e.source}::${e.target}`);
  }

  const seenPairs = new Set<string>();
  for (const e of edges) {
    if (directedPairs.has(`${e.target}::${e.source}`)) {
      bidirectionalIds.add(e.id);
    }

    const reverseKey = `${e.target}::${e.source}`;
    if (seenPairs.has(reverseKey)) {
      secondaryIds.add(e.id);
    }
    seenPairs.add(`${e.source}::${e.target}`);
  }

  return { bidirectionalIds, secondaryIds };
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useGraphCreationCanvas({
  nodes,
  edges,
  primaryHex,
  onNodeClick,
  onPaneClick,
  onNodePositionChange,
}: UseGraphCreationCanvasOptions): UseGraphCreationCanvasReturn {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<dia.Graph | null>(null);
  const paperRef = useRef<dia.Paper | null>(null);

  const [overlayHeaders, setOverlayHeaders] = useState<OverlayHeader[]>([]);
  const [overlayBadges, setOverlayBadges] = useState<OverlayBadge[]>([]);
  const [paperTransform, setPaperTransform] = useState({ sx: 1, sy: 1, tx: 0, ty: 0 });

  const primaryHexRef = useRef(primaryHex);
  primaryHexRef.current = primaryHex;

  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const edgesRef = useRef(edges);
  edgesRef.current = edges;

  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;
  const onPaneClickRef = useRef(onPaneClick);
  onPaneClickRef.current = onPaneClick;
  const onNodePositionChangeRef = useRef(onNodePositionChange);
  onNodePositionChangeRef.current = onNodePositionChange;

  const suppressPositionSyncRef = useRef(false);

  // ── Rebuild overlay positions from JointJS element positions ──
  const rebuildOverlays = useCallback(() => {
    const graph = graphRef.current;
    const currentNodes = nodesRef.current;
    if (!graph || currentNodes.length === 0) {
      setOverlayHeaders([]);
      setOverlayBadges([]);
      return;
    }

    const headers: OverlayHeader[] = [];
    const badges: OverlayBadge[] = [];

    for (const n of currentNodes) {
      const el = graph.getCell(n.id) as dia.Element | undefined;
      if (!el) continue;
      const pos = el.position();
      const size = el.size();
      const nodeType = n.data.workspaceData?.type || "agent_node";
      const allBlocks: BuildingBlock[] = n.data.allBlocks || [];
      const resolvedElements = extractResolvedElements(
        n.data.workspaceData?.config,
        allBlocks,
      );
      const conditionCount = n.data.referencedConditions?.length || 0;
      const hasElements = resolvedElements.length > 0 || conditionCount > 0;

      headers.push({
        nodeId: n.id,
        label: n.data.label,
        nodeType,
        hasElements,
        x: pos.x,
        y: pos.y,
        width: NODE_WIDTH,
        nodeHeight: size.height,
        nodeRid: n.data.workspaceData?.rid,
      });

      if (resolvedElements.length === 0) continue;
      const conditionsSectionHeight =
        conditionCount > 0
          ? CONDITION_LABEL_HEIGHT + conditionCount * CONDITION_ITEM_HEIGHT
          : 0;
      const bodyStartY =
        pos.y + NODE_HEADER_HEIGHT + conditionsSectionHeight + NODE_BODY_PADDING;
      const badgeInnerWidth = NODE_WIDTH - NODE_BODY_PADDING * 2;
      resolvedElements.forEach((re, i) => {
        badges.push({
          nodeId: n.id,
          element: re,
          x: pos.x + NODE_BODY_PADDING,
          y: bodyStartY + i * (ELEMENT_BADGE_HEIGHT + ELEMENT_GAP),
          width: badgeInnerWidth,
        });
      });
    }

    setOverlayHeaders(headers);
    setOverlayBadges(badges);
  }, []);

  // ── Initialise paper once ──
  useEffect(() => {
    if (!containerRef.current) return;

    const namespace = { ...shapes };
    const graph = new dia.Graph({}, { cellNamespace: namespace });
    graphRef.current = graph;

    const paper = new dia.Paper({
      model: graph,
      cellViewNamespace: namespace,
      width: "100%",
      height: "100%",
      interactive: { elementMove: true },
      background: { color: "transparent" },
      gridSize: 16,
      clickThreshold: 5,
      drawGrid: {
        name: "doubleMesh",
        args: [
          { color: "rgba(255,255,255,0.06)", thickness: 1 },
          { color: "rgba(255,255,255,0.12)", scaleFactor: 4, thickness: 1 },
        ],
      },
    });

    containerRef.current.replaceChildren(paper.el);
    paper.el.classList.add("joint-paper");
    paperRef.current = paper;

    const primaryNow = normalizePrimaryHex(primaryHexRef.current);
    injectSvgDefs(paper.el, primaryNow);
    injectStatusGlowFilters(paper.el);

    // ── Panning ──
    let isPanning = false;
    let panStartX = 0;
    let panStartY = 0;

    paper.el.style.cursor = "grab";

    paper.on("blank:pointerdown", (evt: dia.Event) => {
      isPanning = true;
      const ne = (evt as any).originalEvent ?? evt;
      panStartX = ne.clientX;
      panStartY = ne.clientY;
      paper.el.style.cursor = "grabbing";
    });

    const panMoveHandler = (evt: PointerEvent) => {
      if (!isPanning) return;
      const dx = evt.clientX - panStartX;
      const dy = evt.clientY - panStartY;
      panStartX = evt.clientX;
      panStartY = evt.clientY;
      const t = paper.translate();
      paper.translate(t.tx + dx, t.ty + dy);
      syncTransformState();
    };

    const panUpHandler = () => {
      if (!isPanning) return;
      isPanning = false;
      paper.el.style.cursor = "grab";
    };

    document.addEventListener("pointermove", panMoveHandler);
    document.addEventListener("pointerup", panUpHandler);

    // ── Mouse-wheel zoom ──
    const ZOOM_FACTOR = 1.1;
    const MIN_ZOOM = 0.1;
    const MAX_ZOOM = 4;

    const onMouseWheel = (
      _evt: dia.Event,
      ox: number,
      oy: number,
      delta: number,
    ) => {
      const oldScale = paper.scale().sx;
      const newScale = Math.min(
        MAX_ZOOM,
        Math.max(MIN_ZOOM, delta > 0 ? oldScale * ZOOM_FACTOR : oldScale / ZOOM_FACTOR),
      );
      if (newScale === oldScale) return;
      const t = paper.translate();
      const scaleDiff = newScale / oldScale;
      const tx = t.tx - ox * (scaleDiff - 1) * oldScale;
      const ty = t.ty - oy * (scaleDiff - 1) * oldScale;
      paper.scale(newScale, newScale);
      paper.translate(tx, ty);
      syncTransformState();
    };

    paper.on("blank:mousewheel", onMouseWheel);
    paper.on(
      "cell:mousewheel",
      (_cv: unknown, evt: dia.Event, ox: number, oy: number, delta: number) => {
        onMouseWheel(evt, ox, oy, delta);
      },
    );

    // ── Click events ──
    paper.on("blank:pointerclick", () => {
      onPaneClickRef.current?.();
    });

    paper.on("element:pointerclick", (cellView: dia.CellView) => {
      onNodeClickRef.current?.(cellView.model.id as string);
    });

    // ── Drag: sync position back to React state ──
    graph.on("change:position", (_el: dia.Element, _newPos: unknown, opt: any) => {
      if (suppressPositionSyncRef.current) return;
      if (opt?.skipSync) return;
      const el = _el as dia.Element;
      const pos = el.position();
      onNodePositionChangeRef.current?.(el.id as string, { x: pos.x, y: pos.y });
      safeFlushSync(() => rebuildOverlays());
    });

    function syncTransformState() {
      const s = paper.scale();
      const tr = paper.translate();
      safeFlushSync(() => {
        setPaperTransform({ sx: s.sx, sy: s.sy, tx: tr.tx, ty: tr.ty });
        rebuildOverlays();
      });
    }

    return () => {
      document.removeEventListener("pointermove", panMoveHandler);
      document.removeEventListener("pointerup", panUpHandler);
      graph.off("change:position");
      removeLinkAnimations(paper.el);
      paper.remove();
      graph.clear();
      graphRef.current = null;
      paperRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rebuildOverlays]);

  // ── Resize: keep paper dimensions in sync with container ──
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const MIN_DIMENSION = 50;
    let timerId: ReturnType<typeof setTimeout> | null = null;

    const observer = new ResizeObserver(() => {
      if (timerId) clearTimeout(timerId);
      timerId = setTimeout(() => {
        const paper = paperRef.current;
        if (!paper) return;

        const cw = container.clientWidth;
        const ch = container.clientHeight;
        if (cw < MIN_DIMENSION || ch < MIN_DIMENSION) return;

        try {
          paper.setDimensions(cw, ch);
        } catch {
          // SVGMatrix may be non-invertible during CSS transitions
        }
      }, 50);
    });

    observer.observe(container);
    return () => {
      observer.disconnect();
      if (timerId) clearTimeout(timerId);
    };
  }, []);

  // ── Sync nodes ──
  useEffect(() => {
    const graph = graphRef.current;
    const paper = paperRef.current;
    if (!graph || !paper) return;

    suppressPositionSyncRef.current = true;
    try {
      const existingElementIds = new Set(
        graph.getElements().map((el) => el.id as string),
      );
      const desiredNodeIds = new Set(nodes.map((n) => n.id));

      for (const id of existingElementIds) {
        if (!desiredNodeIds.has(id)) {
          const cell = graph.getCell(id);
          if (cell) cell.remove();
        }
      }

      for (const n of nodes) {
        const nodeType = n.data.workspaceData?.type || "agent_node";
        const allBlocks: BuildingBlock[] = n.data.allBlocks || [];
        const resolvedElements = extractResolvedElements(
          n.data.workspaceData?.config,
          allBlocks,
        );
        const conditionCount = n.data.referencedConditions?.length || 0;
        const nodeHeight = computeCanvasNodeHeight(
          resolvedElements.length,
          conditionCount,
        );
        const existing = graph.getCell(n.id) as dia.Element | undefined;

        if (existing) {
          const pos = existing.position();
          if (
            Math.abs(pos.x - n.position.x) > 1 ||
            Math.abs(pos.y - n.position.y) > 1
          ) {
            existing.position(n.position.x, n.position.y, { skipSync: true });
          }
          existing.attr("body/fill", nodeFillForType(nodeType));
          existing.resize(NODE_WIDTH, nodeHeight);

          if (n.data.isConnectionSource) {
            existing.attr("body/stroke", normalizePrimaryHex(primaryHexRef.current));
            existing.attr("body/strokeWidth", 3);
            existing.attr("body/filter", "url(#progressGlow)");
          } else if (n.data.isConnectionTarget) {
            existing.attr(
              "body/stroke",
              `${normalizePrimaryHex(primaryHexRef.current)}66`,
            );
            existing.attr("body/strokeWidth", 2);
            existing.attr("body/filter", STATUS_STYLES.IDLE.filter);
          } else {
            existing.attr("body/stroke", STATUS_STYLES.IDLE.stroke);
            existing.attr("body/strokeWidth", STATUS_STYLES.IDLE.strokeWidth);
            existing.attr("body/filter", STATUS_STYLES.IDLE.filter);
          }
        } else {
          const isSource = n.data.isConnectionSource;
          const isTarget = n.data.isConnectionTarget;
          const strokeColor = isSource
            ? normalizePrimaryHex(primaryHexRef.current)
            : isTarget
              ? `${normalizePrimaryHex(primaryHexRef.current)}66`
              : STATUS_STYLES.IDLE.stroke;
          const strokeWidth = isSource
            ? 3
            : isTarget
              ? 2
              : STATUS_STYLES.IDLE.strokeWidth;

          new shapes.standard.Rectangle({
            id: n.id,
            position: { x: n.position.x, y: n.position.y },
            size: { width: NODE_WIDTH, height: nodeHeight },
            attrs: {
              body: {
                fill: nodeFillForType(nodeType),
                stroke: strokeColor,
                strokeWidth,
                rx: 12,
                ry: 12,
                filter: isSource
                  ? "url(#progressGlow)"
                  : STATUS_STYLES.IDLE.filter,
              },
              label: { text: "" },
            },
          }).addTo(graph);
        }
      }

      rebuildOverlays();
    } finally {
      suppressPositionSyncRef.current = false;
    }
  }, [nodes, rebuildOverlays]);

  // ── Sync edges (with bidirectional pair rendering) ──
  // Bidirectional pairs (A→B and B→A) are rendered as two visually
  // separate parallel edges by offsetting their anchors horizontally.
  // The primary edge keeps the theme color; the secondary edge is grey.
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    // Rebuild all links so bidirectional pairs stay in sync
    for (const l of graph.getLinks()) {
      l.remove();
    }

    const { bidirectionalIds, secondaryIds } = detectBidirectionalEdges(edges);
    const linkColor = normalizePrimaryHex(primaryHexRef.current);
    const BIDIRECTIONAL_ANCHOR_OFFSET = 20;

    for (const e of edges) {
      if (!graph.getCell(e.source) || !graph.getCell(e.target)) continue;

      const isBidirectional = bidirectionalIds.has(e.id);
      const isSecondary = secondaryIds.has(e.id);

      const edgeColor = isSecondary ? "#94a3b8" : linkColor;
      const lineStroke = isSecondary ? "rgba(148, 163, 184, 0.8)" : linkColor;

      // For bidirectional pairs, shift anchors so the two links run side-by-side.
      // The primary (first-connected) edge goes one way, the secondary the other.
      const anchorDx = isBidirectional
        ? BIDIRECTIONAL_ANCHOR_OFFSET * (isSecondary ? -1 : 1)
        : 0;

      const sourceSpec: any = { id: e.source };
      const targetSpec: any = { id: e.target };
      if (isBidirectional) {
        sourceSpec.anchor = { name: "center", args: { dx: anchorDx } };
        targetSpec.anchor = { name: "center", args: { dx: anchorDx } };
      }

      new shapes.standard.Link({
        id: e.id,
        source: sourceSpec,
        target: targetSpec,
        attrs: {
          line: {
            stroke: lineStroke,
            strokeWidth: isSecondary ? 1.5 : 2,
            opacity: isSecondary ? 1 : 0.9,
            sourceMarker: {
              type: "circle" as const,
              r: 4,
              fill: edgeColor,
            },
            targetMarker: {
              type: "path" as const,
              size: 12,
              fill: edgeColor,
            },
          },
        },
      }).addTo(graph);
    }

    const paper = paperRef.current;
    if (paper) {
      injectLinkAnimations(paper.el);
    }
  }, [edges]);

  // ── Theme colour update ──
  useEffect(() => {
    const paper = paperRef.current;
    const graph = graphRef.current;
    if (!paper || !graph) return;

    const primaryNow = normalizePrimaryHex(primaryHex);
    injectSvgDefs(paper.el, primaryNow);

    // Update edge colours
    const { secondaryIds } = detectBidirectionalEdges(edgesRef.current);
    for (const link of graph.getLinks()) {
      if (secondaryIds.has(link.id as string)) continue;

      link.attr("line/stroke", primaryNow);
      link.attr("line/sourceMarker/fill", primaryNow);
      link.attr("line/targetMarker/fill", primaryNow);
    }

    // Update node border strokes that derive from the primary colour
    for (const n of nodesRef.current) {
      const el = graph.getCell(n.id) as dia.Element | undefined;
      if (!el) continue;

      if (n.data.isConnectionSource) {
        el.attr("body/stroke", primaryNow);
      } else if (n.data.isConnectionTarget) {
        el.attr("body/stroke", `${primaryNow}66`);
      }
    }
  }, [primaryHex]);

  // ── Zoom / fit-to-view ──
  const syncTransform = useCallback(() => {
    const paper = paperRef.current;
    if (!paper) return;
    const s = paper.scale();
    const tr = paper.translate();
    safeFlushSync(() => {
      setPaperTransform({ sx: s.sx, sy: s.sy, tx: tr.tx, ty: tr.ty });
      rebuildOverlays();
    });
  }, [rebuildOverlays]);

  const handleZoomIn = useCallback(() => {
    const paper = paperRef.current;
    if (!paper) return;
    const MAX_SCALE = 4;
    const { sx } = paper.scale();
    const newScale = Math.min(sx * 1.2, MAX_SCALE);
    paper.scale(newScale, newScale);
    syncTransform();
  }, [syncTransform]);

  const handleZoomOut = useCallback(() => {
    const paper = paperRef.current;
    if (!paper) return;
    const { sx } = paper.scale();
    const ns = Math.max(sx / 1.2, 0.1);
    paper.scale(ns, ns);
    syncTransform();
  }, [syncTransform]);

  const handleFitToView = useCallback(() => {
    const paper = paperRef.current;
    const container = containerRef.current;
    if (!paper) return;
    try {
      paper.scale(1, 1);
      paper.translate(0, 0);
      if (container) {
        const cw = container.clientWidth;
        const ch = container.clientHeight;
        if (cw > 0 && ch > 0) paper.setDimensions(cw, ch);
      }
      paper.transformToFitContent(SCALE_CONTENT_TO_FIT_OPTS);
    } catch {
      return;
    }
    syncTransform();
  }, [syncTransform]);

  // ── Auto-layout ──
  const runAutoLayout = useCallback(() => {
    const graph = graphRef.current;
    if (!graph || graph.getElements().length === 0) return;

    suppressPositionSyncRef.current = true;
    try {
      DirectedGraph.layout(graph, LAYOUT_OPTS);

      const currentNodes = nodesRef.current;
      const typeById = new Map(
        currentNodes.map((n) => [n.id, n.data.workspaceData?.type]),
      );
      let maxBottom = 0;
      graph.getElements().forEach((el) => {
        if (typeById.get(el.id as string) !== "final_answer_node") {
          const b = el.getBBox();
          maxBottom = Math.max(maxBottom, b.y + b.height);
        }
      });
      graph.getElements().forEach((el) => {
        if (typeById.get(el.id as string) === "final_answer_node") {
          const pos = el.position();
          el.position(pos.x, maxBottom + LAYOUT_OPTS.rankSep);
        }
      });

      for (const el of graph.getElements()) {
        const pos = el.position();
        onNodePositionChangeRef.current?.(el.id as string, {
          x: pos.x,
          y: pos.y,
        });
      }

      rebuildOverlays();
    } finally {
      suppressPositionSyncRef.current = false;
    }
  }, [rebuildOverlays]);

  const clientToLocalPoint = useCallback(
    (clientX: number, clientY: number) => {
      const paper = paperRef.current;
      if (!paper) return { x: clientX, y: clientY };
      try {
        const p = paper.clientToLocalPoint({ x: clientX, y: clientY });
        return { x: p.x, y: p.y };
      } catch {
        return { x: clientX, y: clientY };
      }
    },
    [],
  );

  return {
    containerRef,
    paperRef,
    graphRef,
    overlayHeaders,
    overlayBadges,
    paperTransform,
    handleZoomIn,
    handleZoomOut,
    handleFitToView,
    runAutoLayout,
    clientToLocalPoint,
  };
}
