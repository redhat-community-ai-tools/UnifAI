/**
 * Pure helpers and constants for GraphDisplay.
 *
 * Keeps the main component lean – all layout constants, SVG DOM logic, and
 * element-block-map building live here. Nothing in this file depends on React
 * state or hooks.
 */

import type { GraphFlow } from "./interfaces";
import type { LayoutNode, ResolvedElement } from "@/utils/graphFlowLayout";
import { extractUidFromRef } from "@/utils/graphFlowLayout";
import { getCategoryDisplay } from "@/components/shared/helpers";
import type { BuildingBlock } from "@/types/graph";

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

export const NODE_WIDTH = 320;
export const NODE_HEADER_HEIGHT = 52;
export const ELEMENT_BADGE_HEIGHT = 26;
export const ELEMENT_GAP = 4;
export const NODE_BODY_PADDING = 8;

export const LAYOUT_OPTS = {
  rankDir: "TB" as const,
  nodeSep: 60,
  edgeSep: 40,
  rankSep: 80,
  marginX: 32,
  marginY: 32,
  setVertices: true,
  disableOptimalOrderHeuristic: false,
};

/** Shared padding used when fitting the graph into the viewport. */
export const FIT_PADDING = 40;

/** Shared options passed to `paper.transformToFitContent()`. */
export const SCALE_CONTENT_TO_FIT_OPTS = {
  padding: FIT_PADDING,
  preserveAspectRatio: true,
  verticalAlign: "middle" as const,
  horizontalAlign: "middle" as const,
  useModelGeometry: true,
};

// ---------------------------------------------------------------------------
// Badge styling constants (frosted-glass look on dark nodes)
// ---------------------------------------------------------------------------

export const BADGE_BG = "rgba(0,0,0,0.28)";
export const BADGE_BORDER = "rgba(255,255,255,0.10)";
export const BADGE_HOVER_BG = "rgba(255,255,255,0.10)";

// ---------------------------------------------------------------------------
// Overlay data interfaces
// ---------------------------------------------------------------------------

/** Positioned element badge data for overlay rendering. */
export interface OverlayBadge {
  nodeId: string;
  element: ResolvedElement;
  x: number;
  y: number;
  width: number;
}

/** Header overlay data (title text + icon + separator). */
export interface OverlayHeader {
  nodeId: string;
  label: string;
  nodeType: string;
  hasElements: boolean;
  x: number;
  y: number;
  width: number;
  /** Full node height so we know the rendered size. */
  nodeHeight: number;
  /** Node RID from its definition – used for validation result lookups. */
  nodeRid: string | undefined;
}

// ---------------------------------------------------------------------------
// Category type → plural key mapping (used by overlay badges & block map)
// ---------------------------------------------------------------------------

export const CATEGORY_TYPE_TO_PLURAL: Record<string, string> = {
  llm: "llms",
  tool: "tools",
  retriever: "retrievers",
  provider: "providers",
};

// ---------------------------------------------------------------------------
// Node helpers
// ---------------------------------------------------------------------------

/** Returns an emoji icon matching the node type. */
export function nodeIconForType(nodeType: string): string {
  if (nodeType === "user_question_node") return "\uD83D\uDCAC"; // 💬
  if (nodeType === "final_answer_node") return "\uD83E\uDD16"; // 🤖
  // Deterministic pick from a set based on type-name hash
  const icons = [
    "\uD83D\uDD0D", // 🔍
    "\uD83D\uDCDA", // 📚
    "\uD83E\uDDE0", // 🧠
    "\uD83D\uDD0E", // 🔎
    "\uD83D\uDD27", // 🔧
    "\u270D\uFE0F", // ✍️
  ];
  const hash = nodeType
    .split("")
    .reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return icons[hash % icons.length];
}

/** Compute the total pixel height of a node given its element count. */
export function computeNodeHeight(elementCount: number): number {
  if (elementCount === 0) return NODE_HEADER_HEIGHT;
  const bodyHeight =
    NODE_BODY_PADDING * 2 +
    elementCount * ELEMENT_BADGE_HEIGHT +
    Math.max(0, elementCount - 1) * ELEMENT_GAP;
  return NODE_HEADER_HEIGHT + bodyHeight;
}

/** Returns the SVG gradient fill reference for a node type. */
export function nodeFillForType(type: string): string {
  if (type === "user_question_node" || type === "final_answer_node") {
    return "url(#agentGradientSpecial)";
  }
  return "url(#agentGradient)";
}

// ---------------------------------------------------------------------------
// SVG defs injection (gradients + shadow filter)
// ---------------------------------------------------------------------------

/**
 * Inject SVG `<defs>` (gradients + drop-shadow filter) into the JointJS
 * paper SVG element.  Idempotent – safe to call on the same element twice.
 *
 * **Why direct SVG DOM manipulation is necessary here:**
 *
 * SVG `fill` with gradients (`url(#agentGradient)`) requires a
 * `<linearGradient>` definition inside the same SVG's `<defs>`.  There is
 * no CSS-only alternative for SVG gradient fills.  JointJS does not expose
 * a public API for injecting custom `<defs>`, so we add them directly.
 *
 * This is safe because:
 * 1. We only *append* to `<defs>` – never remove or modify existing JointJS
 *    elements.
 * 2. All injected elements use stable IDs that JointJS does not use
 *    (`agentGradient`, `agentGradientSpecial`, `nodeShadow`).
 * 3. The function is idempotent (upsert pattern) so repeated calls are
 *    harmless (e.g. on theme change).
 */
export function injectSvgDefs(
  paperEl: HTMLElement,
  primaryHex: string,
  darkSlate = "#1a1f2e",
): void {
  const svg =
    paperEl.tagName === "svg" ? paperEl : paperEl.querySelector("svg");
  if (!svg) return;

  let defs = svg.querySelector("defs");
  if (!defs) {
    defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    svg.insertBefore(defs, svg.firstChild);
  }

  // Helper to upsert a linear gradient (uses DOM APIs instead of innerHTML)
  const upsertGradient = (id: string, stopColors: [string, string]) => {
    const existing = defs!.querySelector(`#${id}`);
    if (existing) existing.remove();
    const g = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "linearGradient",
    );
    g.setAttribute("id", id);
    g.setAttribute("x1", "0%");
    g.setAttribute("y1", "0%");
    g.setAttribute("x2", "100%");
    g.setAttribute("y2", "100%");

    const offsets = ["0%", "100%"];
    stopColors.forEach((color, i) => {
      const stop = document.createElementNS("http://www.w3.org/2000/svg", "stop");
      stop.setAttribute("offset", offsets[i]);
      stop.setAttribute("stop-color", color);
      g.appendChild(stop);
    });

    defs!.appendChild(g);
  };

  // Main gradient: dark slate → primary
  upsertGradient("agentGradient", [darkSlate, primaryHex]);
  // Special gradient: dark slate → dark teal (user_question / final_answer)
  upsertGradient("agentGradientSpecial", [darkSlate, "#003f5c"]);

  // Drop-shadow filter (only added once)
  if (!defs.querySelector("#nodeShadow")) {
    const filter = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "filter",
    );
    filter.setAttribute("id", "nodeShadow");
    filter.setAttribute("x", "-20%");
    filter.setAttribute("y", "-20%");
    filter.setAttribute("width", "140%");
    filter.setAttribute("height", "140%");
    const feDrop = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "feDropShadow",
    );
    feDrop.setAttribute("dx", "0");
    feDrop.setAttribute("dy", "4");
    feDrop.setAttribute("stdDeviation", "8");
    feDrop.setAttribute("flood-color", "#000");
    feDrop.setAttribute("flood-opacity", "0.35");
    filter.appendChild(feDrop);
    defs.appendChild(filter);
  }
}

// ---------------------------------------------------------------------------
// Live-status visual constants
// ---------------------------------------------------------------------------

export const STATUS_STYLES = {
  PROGRESS: {
    stroke: "rgba(59, 130, 246, 0.85)",
    strokeWidth: 2.5,
    filter: "url(#progressGlow)",
    dotColor: "rgb(59, 130, 246)",
    bgColor: "rgba(59, 130, 246, 0.2)",
    label: "Processing",
    /** CSS box-shadow for the HTML overlay border glow. */
    boxShadow: "0 0 12px rgba(59,130,246,0.5), 0 0 4px rgba(59,130,246,0.3)",
  },
  DONE: {
    stroke: "rgba(34, 197, 94, 0.7)",
    strokeWidth: 2,
    filter: "url(#doneGlow)",
    dotColor: "rgb(34, 197, 94)",
    bgColor: "rgba(34, 197, 94, 0.2)",
    label: "Complete",
    boxShadow: "0 0 8px rgba(34,197,94,0.4), 0 0 3px rgba(34,197,94,0.25)",
  },
  CANCELLED: {
    stroke: "rgba(156, 163, 175, 0.7)",
    strokeWidth: 2,
    filter: "url(#cancelledGlow)",
    dotColor: "rgb(156, 163, 175)",
    bgColor: "rgba(156, 163, 175, 0.2)",
    label: "Stopped",
    boxShadow: "0 0 8px rgba(156,163,175,0.4), 0 0 3px rgba(156,163,175,0.25)",
  },
  IDLE: {
    stroke: "rgba(255,255,255,0.12)",
    strokeWidth: 1,
    filter: "url(#nodeShadow)",
    dotColor: "",
    bgColor: "",
    label: "",
    boxShadow: "none",
  },
} as const;

// ---------------------------------------------------------------------------
// Live-status SVG glow filter injection
// ---------------------------------------------------------------------------

/**
 * Inject `progressGlow` and `doneGlow` SVG filter defs into the paper.
 * Idempotent – safe to call multiple times.
 *
 * **Why SVG filters instead of CSS `filter`:**
 *
 * JointJS sets the SVG `filter` *attribute* on `<rect>` elements (via
 * `el.attr("body/filter", …)`).  The SVG `filter` attribute only accepts
 * `url(#…)` references to SVG `<filter>` elements – it cannot take CSS
 * filter functions like `drop-shadow(…)`.  (CSS `filter` is a *property*
 * that can be set via `style`, but JointJS attrs target SVG attributes.)
 *
 * As with gradients, we only append to `<defs>` and use stable IDs that
 * don't collide with JointJS internals, so this is safe for upgrades.
 */
export function injectStatusGlowFilters(paperEl: HTMLElement): void {
  const svg =
    paperEl.tagName === "svg" ? paperEl : paperEl.querySelector("svg");
  if (!svg) return;

  const defs = svg.querySelector("defs");
  if (!defs) return;

  // Helper to create an SVG feDropShadow element via DOM APIs
  const mkDropShadow = (attrs: Record<string, string>) => {
    const fe = document.createElementNS("http://www.w3.org/2000/svg", "feDropShadow");
    for (const [k, v] of Object.entries(attrs)) fe.setAttribute(k, v);
    return fe;
  };

  const upsertFilter = (
    id: string,
    bounds: { x: string; y: string; w: string; h: string },
    shadows: Record<string, string>[],
  ) => {
    if (defs.querySelector(`#${id}`)) return;
    const f = document.createElementNS("http://www.w3.org/2000/svg", "filter");
    f.setAttribute("id", id);
    f.setAttribute("x", bounds.x);
    f.setAttribute("y", bounds.y);
    f.setAttribute("width", bounds.w);
    f.setAttribute("height", bounds.h);
    shadows.forEach((s) => f.appendChild(mkDropShadow(s)));
    defs.appendChild(f);
  };

  upsertFilter(
    "progressGlow",
    { x: "-30%", y: "-30%", w: "160%", h: "160%" },
    [
      { dx: "0", dy: "0", stdDeviation: "6", "flood-color": "rgba(59,130,246,0.5)", "flood-opacity": "0.8" },
      { dx: "0", dy: "2", stdDeviation: "4", "flood-color": "#000", "flood-opacity": "0.25" },
    ],
  );

  upsertFilter(
    "doneGlow",
    { x: "-20%", y: "-20%", w: "140%", h: "140%" },
    [
      { dx: "0", dy: "0", stdDeviation: "4", "flood-color": "rgba(34,197,94,0.4)", "flood-opacity": "0.6" },
      { dx: "0", dy: "2", stdDeviation: "4", "flood-color": "#000", "flood-opacity": "0.25" },
    ],
  );

  upsertFilter(
    "cancelledGlow",
    { x: "-20%", y: "-20%", w: "140%", h: "140%" },
    [
      { dx: "0", dy: "0", stdDeviation: "4", "flood-color": "rgba(156,163,175,0.4)", "flood-opacity": "0.6" },
      { dx: "0", dy: "2", stdDeviation: "4", "flood-color": "#000", "flood-opacity": "0.25" },
    ],
  );
}

// ---------------------------------------------------------------------------
// Link animation injection
// ---------------------------------------------------------------------------

/**
 * Add a flowing stroke-dasharray animation to every link path in the SVG.
 * Idempotent – existing `<animate>` children are removed before appending new
 * ones so that calling this function multiple times on the same SVG does not
 * stack duplicate animations.
 */
export function injectLinkAnimations(paperEl: HTMLElement): void {
  const svgEl = paperEl.querySelector("svg");
  if (!svgEl) return;

  const linkPaths = svgEl.querySelectorAll("[joint-selector='line']");
  linkPaths.forEach((path) => {
    // Remove any existing <animate> elements to prevent duplication
    path.querySelectorAll("animate").forEach((a) => a.remove());

    path.setAttribute("stroke-dasharray", "8 4");
    const animate = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "animate",
    );
    animate.setAttribute("attributeName", "stroke-dashoffset");
    animate.setAttribute("from", "0");
    animate.setAttribute("to", "-12"); // 8+4 = 12 → one pattern cycle
    animate.setAttribute("dur", "0.8s");
    animate.setAttribute("repeatCount", "indefinite");
    path.appendChild(animate);
  });
}

/** Remove link animations previously injected by injectLinkAnimations. */
export function removeLinkAnimations(paperEl: HTMLElement): void {
  const svgEl = paperEl.querySelector("svg");
  if (!svgEl) return;

  const linkPaths = svgEl.querySelectorAll("[joint-selector='line']");
  linkPaths.forEach((path) => {
    path.removeAttribute("stroke-dasharray");
    // Remove all <animate> children
    const animates = path.querySelectorAll("animate");
    animates.forEach((a) => a.remove());
  });
}

// ---------------------------------------------------------------------------
// Element block map builder
// ---------------------------------------------------------------------------

/**
 * Build a `Map<elementId, BuildingBlock>` from the layout nodes and the
 * original GraphFlow spec. Used by overlay badges to show resource details.
 */
export function buildElementBlockMap(
  layoutNodes: LayoutNode[],
  spec: GraphFlow,
): Map<string, BuildingBlock> {
  const map = new Map<string, BuildingBlock>();

  layoutNodes.forEach((n) => {
    n.resolvedElements.forEach((el) => {
      const category = CATEGORY_TYPE_TO_PLURAL[el.type];
      if (!category) return;
      const catList = (spec as unknown as Record<string, unknown[]>)[category];
      const def = catList?.find((d: unknown) => {
        const entry = d as { rid?: string };
        return (
          extractUidFromRef(entry.rid || "") === el.id || entry.rid === el.id
        );
      });
      if (!def) return;

      const d = def as {
        rid: string;
        name: string;
        type: string;
        config?: unknown;
        nested_refs?: string[];
      };
      const display = getCategoryDisplay(category);
      map.set(el.id, {
        id: d.rid,
        type: d.type,
        label: d.name,
        color: display.color,
        description: `${category}/${d.type} - ${d.name}`,
        workspaceData: {
          rid: d.rid,
          name: d.name,
          category,
          type: d.type,
          config: d.config ?? {},
          version: 1,
          created: "",
          updated: "",
          nested_refs: d.nested_refs ?? [],
        },
      });
    });
  });

  return map;
}

// ---------------------------------------------------------------------------
// Badge grouping utility
// ---------------------------------------------------------------------------

/** Group overlay badges by their parent node ID for O(1) lookup. */
export function groupBadgesByNode(
  badges: OverlayBadge[],
): Map<string, OverlayBadge[]> {
  const map = new Map<string, OverlayBadge[]>();
  for (const b of badges) {
    const list = map.get(b.nodeId);
    if (list) list.push(b);
    else map.set(b.nodeId, [b]);
  }
  return map;
}
