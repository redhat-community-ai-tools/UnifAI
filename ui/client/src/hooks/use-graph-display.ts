/**
 * useGraphDisplay – custom hook encapsulating the imperative JointJS graph
 * initialisation, data-fetching, layout, SVG injection, and sizing logic
 * for the read-only GraphDisplay component.
 *
 * Keeps GraphDisplay lean by separating React rendering from the imperative
 * JointJS/DOM manipulation.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { dia, shapes } from "@joint/core";
import { DirectedGraph } from "@joint/layout-directed-graph";
import type { GraphFlow } from "@/components/agentic-ai/graphs/interfaces";
import {
  graphFlowToLayoutData,
  type LayoutNode,
} from "@/utils/graphFlowLayout";
import { getBlueprintInfo } from "@/api/blueprints";
import type { BuildingBlock } from "@/types/graph";
import { safeFlushSync } from "@/lib/reactUtils";
import {
  NODE_WIDTH,
  NODE_HEADER_HEIGHT,
  ELEMENT_BADGE_HEIGHT,
  ELEMENT_GAP,
  NODE_BODY_PADDING,
  LAYOUT_OPTS,
  FIT_PADDING,
  SCALE_CONTENT_TO_FIT_OPTS,
  STATUS_STYLES,
  computeNodeHeight,
  nodeFillForType,
  injectSvgDefs,
  injectStatusGlowFilters,
  injectLinkAnimations,
  removeLinkAnimations,
  buildElementBlockMap,
  type OverlayBadge,
  type OverlayHeader,
} from "@/components/agentic-ai/graphs/GraphDisplayHelpers";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseGraphDisplayOptions {
  blueprintId?: string;
  primaryHex?: string;
  /** Pre-fetched spec_dict – when provided, skips the network fetch entirely. */
  specDict?: any;
  showBackground?: boolean;
  interactive?: boolean;
  centerInView?: boolean;
  animated?: boolean;
}

export interface UseGraphDisplayReturn {
  containerRef: React.RefObject<HTMLDivElement>;
  graphRef: React.MutableRefObject<dia.Graph | null>;
  paperRef: React.MutableRefObject<dia.Paper | null>;
  layoutNodesRef: React.MutableRefObject<LayoutNode[]>;
  elementBlockRef: React.MutableRefObject<Map<string, BuildingBlock>>;
  loading: boolean;
  error: string | null;
  overlayBadges: OverlayBadge[];
  overlayHeaders: OverlayHeader[];
  paperTransform: { sx: number; sy: number; tx: number; ty: number };
  setPaperTransform: React.Dispatch<React.SetStateAction<{ sx: number; sy: number; tx: number; ty: number }>>;
  rebuildOverlays: () => void;
}

/** Ensure the primary hex value is `#`-prefixed with a sensible default. */
function normalizePrimaryHex(raw: string | undefined | null): string {
  if (!raw) return "#8b5cf6";
  return raw.startsWith("#") ? raw : `#${raw}`;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useGraphDisplay({
  blueprintId,
  primaryHex,
  specDict,
  showBackground = true,
  interactive = false,
  centerInView = false,
  animated = false,
}: UseGraphDisplayOptions): UseGraphDisplayReturn {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<dia.Graph | null>(null);
  const layoutNodesRef = useRef<LayoutNode[]>([]);
  const elementBlockRef = useRef<Map<string, BuildingBlock>>(new Map());
  const paperRef = useRef<dia.Paper | null>(null);
  const conditionalLinkIdsRef = useRef<Set<string>>(new Set());

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overlayBadges, setOverlayBadges] = useState<OverlayBadge[]>([]);
  const [overlayHeaders, setOverlayHeaders] = useState<OverlayHeader[]>([]);
  const [paperTransform, setPaperTransform] = useState({
    sx: 1, sy: 1, tx: 0, ty: 0,
  });

  // Keep mutable ref so the async callback always reads the latest primary color.
  const primaryHexRef = useRef(primaryHex);
  primaryHexRef.current = primaryHex;

  // ── Rebuild overlay positions from current graph element positions ──
  const rebuildOverlays = useCallback(() => {
    const graph = graphRef.current;
    const nodes = layoutNodesRef.current;
    if (!graph || nodes.length === 0) return;

    const headers: OverlayHeader[] = [];
    const badges: OverlayBadge[] = [];

    for (const n of nodes) {
      const el = graph.getCell(n.id);
      if (!el) continue;
      const pos = (el as dia.Element).position();
      const size = (el as dia.Element).size();
      const hasElements = n.resolvedElements.length > 0;

      headers.push({
        nodeId: n.id,
        label: n.label,
        nodeType: n.type,
        hasElements,
        x: pos.x,
        y: pos.y,
        width: NODE_WIDTH,
        nodeHeight: size.height,
        nodeRid: n.nodeDefinition?.rid,
        hitlMode: n.nodeDefinition?.config?.hitl_mode as string | undefined,
      });

      if (!hasElements) continue;
      const bodyStartY = pos.y + NODE_HEADER_HEIGHT + NODE_BODY_PADDING;
      const badgeInnerWidth = NODE_WIDTH - NODE_BODY_PADDING * 2;
      n.resolvedElements.forEach((re, i) => {
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

  // ── Main effect: fetch blueprint → build JointJS graph → layout ────
  useEffect(() => {
    if ((!blueprintId && !specDict) || !containerRef.current) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setOverlayBadges([]);
    setOverlayHeaders([]);

    const namespace = { ...shapes };
    const graph = new dia.Graph({}, { cellNamespace: namespace });
    graphRef.current = graph;

    const paper = new dia.Paper({
      model: graph,
      cellViewNamespace: namespace,
      width: "100%",
      height: "100%",
      interactive: interactive ? { elementMove: true } : false,
      background: showBackground ? { color: "transparent" } : undefined,
      gridSize: 16,
      drawGrid: showBackground
        ? {
            name: "doubleMesh",
            args: [
              { color: "rgba(255,255,255,0.06)", thickness: 1 },
              { color: "rgba(255,255,255,0.12)", scaleFactor: 4, thickness: 1 },
            ],
          }
        : false,
    });

    containerRef.current.replaceChildren(paper.el);
    paper.el.classList.add("joint-paper");
    paperRef.current = paper;

    // Freeze the paper immediately so that adding nodes/edges does NOT
    // trigger SVG transform calculations.  This prevents the
    // "SVGMatrix is not invertible" error that occurs when the container
    // is inside an animating dialog (or any element with near-zero
    // dimensions at mount time).  We unfreeze once the layout is
    // complete and the container has valid dimensions.
    paper.freeze();

    // ── Panning support (drag on blank area to translate the canvas) ──
    let panMoveHandler: ((e: PointerEvent) => void) | null = null;
    let panUpHandler: (() => void) | null = null;

    if (interactive) {
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

      panMoveHandler = (evt: PointerEvent) => {
        if (!isPanning) return;
        const dx = evt.clientX - panStartX;
        const dy = evt.clientY - panStartY;
        panStartX = evt.clientX;
        panStartY = evt.clientY;
        const t = paper.translate();
        paper.translate(t.tx + dx, t.ty + dy);
        const s = paper.scale();
        const tr = paper.translate();
        safeFlushSync(() => {
          setPaperTransform({ sx: s.sx, sy: s.sy, tx: tr.tx, ty: tr.ty });
        });
      };

      panUpHandler = () => {
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

      const onMouseWheel = (_evt: dia.Event, ox: number, oy: number, delta: number) => {
        const oldScale = paper.scale().sx;
        const newScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, delta > 0 ? oldScale * ZOOM_FACTOR : oldScale / ZOOM_FACTOR));
        if (newScale === oldScale) return;

        // Zoom towards the cursor position (ox, oy are local coordinates)
        const t = paper.translate();
        const scaleDiff = newScale / oldScale;
        const tx = t.tx - ox * (scaleDiff - 1) * oldScale;
        const ty = t.ty - oy * (scaleDiff - 1) * oldScale;

        paper.scale(newScale, newScale);
        paper.translate(tx, ty);
        const s = paper.scale();
        const tr = paper.translate();
        safeFlushSync(() => {
          setPaperTransform({ sx: s.sx, sy: s.sy, tx: tr.tx, ty: tr.ty });
        });
      };

      paper.on("blank:mousewheel", onMouseWheel);
      paper.on("cell:mousewheel", (_cellView: unknown, evt: dia.Event, ox: number, oy: number, delta: number) => {
        onMouseWheel(evt, ox, oy, delta);
      });
    }

    let cancelled = false;

    /**
     * Wait until a container element has non-trivial dimensions.
     * Useful when the component is mounted inside an animating dialog
     * whose container starts at near-zero size.  Returns `true` when
     * valid dimensions are detected, `false` if cancelled or timed-out.
     */
    const waitForValidSize = (
      el: HTMLElement,
      minDim = 50,
      timeoutMs = 3000,
    ): Promise<boolean> =>
      new Promise((resolve) => {
        if (el.clientWidth >= minDim && el.clientHeight >= minDim) {
          resolve(true);
          return;
        }
        const ro = new ResizeObserver(() => {
          if (cancelled) { ro.disconnect(); resolve(false); return; }
          if (el.clientWidth >= minDim && el.clientHeight >= minDim) {
            ro.disconnect();
            clearTimeout(timer);
            resolve(true);
          }
        });
        ro.observe(el);
        const timer = setTimeout(() => {
          ro.disconnect();
          // Last-ditch check — container may be big enough now
          resolve(el.clientWidth >= minDim && el.clientHeight >= minDim);
        }, timeoutMs);
      });

    (async () => {
      try {
        // Use provided specDict directly if available, otherwise fetch single blueprint
        let spec: GraphFlow;
        if (specDict) {
          spec = specDict as GraphFlow;
        } else if (blueprintId) {
          const blueprintInfo = await getBlueprintInfo(blueprintId);
          if (cancelled) return;
          if (!blueprintInfo?.spec_dict) {
            setError("Workflow not found");
            setLoading(false);
            return;
          }
          spec = blueprintInfo.spec_dict as GraphFlow;
        } else {
          setLoading(false);
          return;
        }
        const { nodes: layoutNodes, edges: layoutEdges } =
          graphFlowToLayoutData(spec);
        layoutNodesRef.current = layoutNodes;
        elementBlockRef.current = buildElementBlockMap(layoutNodes, spec);

        if (layoutNodes.length === 0) {
          setError("No steps in workflow");
          setLoading(false);
          return;
        }

        // SVG defs: gradients + shadow + status glow filters
        const primaryNow = normalizePrimaryHex(primaryHexRef.current);
        injectSvgDefs(paper.el, primaryNow);
        injectStatusGlowFilters(paper.el);

        // Create JointJS nodes
        for (const n of layoutNodes) {
          new shapes.standard.Rectangle({
            id: n.id,
            position: { x: 0, y: 0 },
            size: {
              width: NODE_WIDTH,
              height: computeNodeHeight(n.resolvedElements.length),
            },
            attrs: {
              body: {
                fill: nodeFillForType(n.type),
                stroke: STATUS_STYLES.IDLE.stroke,
                strokeWidth: STATUS_STYLES.IDLE.strokeWidth,
                rx: 12,
                ry: 12,
                filter: STATUS_STYLES.IDLE.filter,
              },
              label: { text: "" },
            },
          }).addTo(graph);
        }

        // Create edges
        const linkColor = normalizePrimaryHex(primaryHexRef.current);

        const mkMarker = (color: string, r: number) => ({
          type: "circle" as const, r, fill: color,
        });

        conditionalLinkIdsRef.current.clear();
        for (const e of layoutEdges) {
          const isCond = e.isConditional;
          const c = isCond ? "#94a3b8" : linkColor;
          const link = new shapes.standard.Link({
            source: { id: e.source },
            target: { id: e.target },
            attrs: {
              line: {
                stroke: isCond ? "rgba(148, 163, 184, 0.8)" : c,
                strokeWidth: isCond ? 1.5 : 2,
                opacity: isCond ? 1 : 0.9,
                sourceMarker: mkMarker(c, isCond ? 3 : 4),
                targetMarker: { type: "path", size: isCond ? 10 : 12, fill: c },
              },
            },
          }).addTo(graph);
          if (isCond) conditionalLinkIdsRef.current.add(link.id as string);
        }

        // Auto-layout
        DirectedGraph.layout(graph, LAYOUT_OPTS);

        // Force final_answer_node to the bottom
        const typeById = new Map(layoutNodes.map((n) => [n.id, n.type]));
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

        // Recompute bounding box after manual repositioning of final_answer_node
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        graph.getElements().forEach((el) => {
          const b = el.getBBox();
          minX = Math.min(minX, b.x);
          minY = Math.min(minY, b.y);
          maxX = Math.max(maxX, b.x + b.width);
          maxY = Math.max(maxY, b.y + b.height);
        });
        const actualBbox = {
          width: maxX - (Number.isFinite(minX) ? minX : 0),
          height: maxY - (Number.isFinite(minY) ? minY : 0),
        };

        // ── Ensure container has real dimensions before unfreezing ──
        // When the graph lives inside an animating dialog the container
        // may still be near-zero size at this point.  We MUST wait for
        // valid dimensions before unfreezing the paper, otherwise
        // JointJS link-view routing will hit "SVGMatrix is not invertible".
        const container = containerRef.current;
        if (!container) return;

        let cw = container.clientWidth ?? 0;
        let ch = container.clientHeight ?? 0;

        if (cw < 50 || ch < 50) {
          const ok = await waitForValidSize(container);
          if (cancelled || !ok) return;
          cw = container.clientWidth;
          ch = container.clientHeight;
        }

        try {
          if (centerInView && cw > 0 && ch > 0) {
            paper.setDimensions(cw, ch);
            paper.transformToFitContent(SCALE_CONTENT_TO_FIT_OPTS);
          } else {
            paper.setDimensions(
              Math.max(actualBbox.width + FIT_PADDING * 2, cw > 0 ? cw : 400),
              Math.max(actualBbox.height + FIT_PADDING * 2, ch > 0 ? ch : 300),
            );
          }
        } catch (e) {
          console.warn("[useGraphDisplay] initial fit: container may not be visible yet", e);
        }

        // All geometry is settled — unfreeze the paper so JointJS renders
        // the SVG elements with valid transforms.
        paper.unfreeze();

        if (animated) {
          injectLinkAnimations(paper.el);
        }

        const scale = paper.scale();
        const translate = paper.translate();
        setPaperTransform({ sx: scale.sx, sy: scale.sy, tx: translate.tx, ty: translate.ty });

        rebuildOverlays();
        if (interactive) graph.on("change:position", () => { safeFlushSync(() => rebuildOverlays()); });

        setLoading(false);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load workflow");
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      if (panMoveHandler) document.removeEventListener("pointermove", panMoveHandler);
      if (panUpHandler) document.removeEventListener("pointerup", panUpHandler);
      graph.off("change:position");
      removeLinkAnimations(paper.el);
      paper.remove();
      graph.clear();
      graphRef.current = null;
      paperRef.current = null;
      layoutNodesRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blueprintId, specDict, showBackground, interactive, centerInView, animated, rebuildOverlays]);

  // ── Lightweight theme-color update (avoids full graph rebuild) ──────
  useEffect(() => {
    const paper = paperRef.current;
    const graph = graphRef.current;
    if (!paper || !graph) return;

    const primaryNow = primaryHex || "#8b5cf6";
    injectSvgDefs(paper.el, primaryNow);

    const linkColor = primaryNow.startsWith("#") ? primaryNow : `#${primaryNow}`;
    try {
      for (const link of graph.getLinks()) {
        if (conditionalLinkIdsRef.current.has(link.id as string)) continue;
        link.attr("line/stroke", linkColor);
        link.attr("line/sourceMarker/fill", linkColor);
        link.attr("line/targetMarker/fill", linkColor);
      }
    } catch (e) {
      console.warn("[useGraphDisplay] theme update: SVGMatrix non-invertible (container likely collapsed)", e);
    }
  }, [primaryHex]);

  // ── Auto-fit paper when container resizes (e.g. console open/close, carousel mode switch) ─
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !centerInView) return;

    // Minimum container size required to attempt fitting.  Prevents
    // non-invertible SVGMatrix errors when the container is mid-CSS-transition
    // or collapsed to near-zero during carousel mode switches.
    const MIN_DIMENSION = 50;
    let resizeTimerId: ReturnType<typeof setTimeout> | null = null;

    const observer = new ResizeObserver(() => {
      // Debounce resize events briefly.  The MIN_DIMENSION guard below already
      // filters out the dangerous tiny-container frames during CSS transitions,
      // so we only need a short debounce to batch rapid-fire ResizeObserver
      // callbacks without adding perceptible delay.
      if (resizeTimerId) clearTimeout(resizeTimerId);
      resizeTimerId = setTimeout(() => {
        const paper = paperRef.current;
        const graph = graphRef.current;
        if (!paper || !graph || graph.getElements().length === 0) return;

        const cw = container.clientWidth;
        const ch = container.clientHeight;
        if (cw < MIN_DIMENSION || ch < MIN_DIMENSION) return;

        try {
          // Reset to identity transform first.  If the paper was previously
          // scaled to near-zero (e.g. the panel was collapsed), the internal
          // SVGMatrix is singular and any setDimensions / transformToFitContent
          // call would throw "The matrix is not invertible".
          paper.scale(1, 1);
          paper.translate(0, 0);
          paper.setDimensions(cw, ch);
          paper.transformToFitContent(SCALE_CONTENT_TO_FIT_OPTS);
        } catch (e) {
          console.warn("[useGraphDisplay] resize refit: SVGMatrix error during CSS transition", e);
          return;
        }

        const scale = paper.scale();
        const translate = paper.translate();
        setPaperTransform({ sx: scale.sx, sy: scale.sy, tx: translate.tx, ty: translate.ty });
        rebuildOverlays();
      }, 10);
    });

    observer.observe(container);
    return () => {
      observer.disconnect();
      if (resizeTimerId) clearTimeout(resizeTimerId);
    };
  }, [centerInView, rebuildOverlays]);

  return {
    containerRef,
    graphRef,
    paperRef,
    layoutNodesRef,
    elementBlockRef,
    loading,
    error,
    overlayBadges,
    overlayHeaders,
    paperTransform,
    setPaperTransform,
    rebuildOverlays,
  };
}
