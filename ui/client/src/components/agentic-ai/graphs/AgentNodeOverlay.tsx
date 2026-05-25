import { ElementValidationResult } from "@/types/validation";
import { BADGE_BG, BADGE_BORDER, CATEGORY_TYPE_TO_PLURAL, ELEMENT_BADGE_HEIGHT, NODE_HEADER_HEIGHT, nodeIconForType, OverlayBadge, OverlayHeader, STATUS_STYLES } from "./GraphDisplayHelpers";
import { motion } from "framer-motion";
import { Eye } from "lucide-react";
import { getCategoryDisplay } from "@/components/shared/helpers";
import NodeValidationIndicator from "./NodeValidationIndicator";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type NodeStatus = "IDLE" | "PROGRESS" | "DONE" | "CANCELLED";

/**
 * Per-node overlay: status border ring, header (icon + label + status pill),
 * validation indicator, and element badges.
 *
 * Mirrors the role of the original ReactFlow `AgentNode` custom component –
 * encapsulates all visual rendering for a single graph node.
 */
export function AgentNodeOverlay({
  hdr,
  badges,
  nodeStatus,
  sx,
  validationResult,
  isValidating,
  interactive,
  previewMode = false,
  onValidationClick,
  onBadgeClick,
}: {
  hdr: OverlayHeader;
  badges: OverlayBadge[];
  nodeStatus: NodeStatus | undefined;
  sx: number;
  validationResult?: ElementValidationResult;
  isValidating: boolean;
  interactive: boolean;
  /** When true, badges are non-interactive (clicks pass through) except for
   *  a preview button that triggers onBadgeClick. Used in the creation canvas. */
  previewMode?: boolean;
  onValidationClick: (result: ElementValidationResult) => void;
  onBadgeClick: (elementId: string) => void;
}) {
  const hasStatus = nodeStatus === "PROGRESS" || nodeStatus === "DONE" || nodeStatus === "CANCELLED";
  const hdrHeight = hdr.hasElements ? NODE_HEADER_HEIGHT : hdr.nodeHeight;
  const icon = nodeIconForType(hdr.nodeType);
  const circleSize = Math.max(20 / sx, 26);
  const iconFontSize = Math.max(12 / sx, 14);

  // Inline status pill ("Processing" / "Complete") for the header
  const statusPill = (() => {
    if (!hasStatus) return null;
    const s = STATUS_STYLES[nodeStatus!];
    const dotSize = Math.max(4 / sx, 6);
    const fontSize = Math.max(8 / sx, 10);
    return (
      <div
        className="flex items-center rounded-full"
        style={{
          gap: 3,
          padding: `${Math.max(1 / sx, 2)}px ${Math.max(4 / sx, 6)}px`,
          background: s.bgColor,
          flexShrink: 0,
        }}
      >
        {nodeStatus === "PROGRESS" ? (
          <motion.div
            style={{ width: dotSize, height: dotSize, borderRadius: "50%", background: s.dotColor }}
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1, repeat: Infinity, ease: "easeInOut" }}
          />
        ) : (
          <div style={{ width: dotSize, height: dotSize, borderRadius: "50%", background: s.dotColor }} />
        )}
        <span style={{ fontSize, fontWeight: 500, color: "rgba(255,255,255,0.85)", whiteSpace: "nowrap" }}>
          {s.label}
        </span>
      </div>
    );
  })();

  // Validation indicator positioning
  const showValidation = isValidating || !!validationResult;
  const indicatorSize = Math.max(24 / sx, 28);

  return (
    <>
      {/* Status border (colored ring + glow around active nodes) */}
      {hasStatus && (() => {
        const s = STATUS_STYLES[nodeStatus!];
        const borderStyle = {
          left: hdr.x,
          top: hdr.y,
          width: hdr.width,
          height: hdr.nodeHeight,
          borderRadius: 12,
          border: `${s.strokeWidth}px solid ${s.stroke}`,
          boxShadow: s.boxShadow,
        };
        return nodeStatus === "PROGRESS" ? (
          <motion.div
            className="absolute"
            style={borderStyle}
            animate={{ opacity: [1, 0.6, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          />
        ) : (
          <div
            className="absolute"
            style={{ ...borderStyle, transition: "border-color 300ms, box-shadow 300ms" }}
          />
        );
      })()}

      {/* Header (icon + title + status pill) */}
      <div
        className="absolute"
        style={{
          left: hdr.x, top: hdr.y, width: hdr.width, height: hdrHeight,
          display: "flex", alignItems: "center", justifyContent: "center",
          gap: 6,
          borderBottom: hdr.hasElements ? "1px solid rgba(255,255,255,0.12)" : "none",
        }}
      >
        <span
          style={{
            width: circleSize, height: circleSize, borderRadius: "50%",
            background: "rgba(255,255,255,0.25)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: iconFontSize, lineHeight: 1, flexShrink: 0,
          }}
          aria-hidden="true"
        >
          {icon}
        </span>
        <span
          style={{
            color: "rgba(255,255,255,0.95)",
            fontSize: Math.max(9 / sx, 12),
            fontWeight: 600,
            fontFamily: "system-ui, -apple-system, sans-serif",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
            maxWidth: hasStatus ? hdr.width - 120 : hdr.width - 40,
          }}
        >
          {hdr.label}
        </span>
        {statusPill}
      </div>

      {/* Validation indicator (top-right corner) */}
      {showValidation && (
        <div
          className="absolute z-10 pointer-events-auto"
          style={{
            left: hdr.x + hdr.width - indicatorSize * 0.45,
            top: hdr.y - indicatorSize * 0.35,
          }}
        >
          <NodeValidationIndicator
            validationResult={validationResult}
            isValidating={isValidating}
            onClick={() => {
              if (validationResult) onValidationClick(validationResult);
            }}
            displayValid={false}
          />
        </div>
      )}

      {/* Element badges */}
      {badges.map((badge, i) => {
        const category = CATEGORY_TYPE_TO_PLURAL[badge.element.type] || "default";
        const display = getCategoryDisplay(category);
        const badgeStyle = {
          left: badge.x, top: badge.y, width: badge.width, height: ELEMENT_BADGE_HEIGHT,
          background: BADGE_BG, borderColor: BADGE_BORDER,
          backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)",
          fontSize: Math.max(9 / sx, 11),
          paddingLeft: 4,
          paddingRight: previewMode ? 4 : 8,
          gap: 5,
        };
        const iconSpan = (
          <span
            style={{ flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }}
            className="[&>svg]:w-3.5 [&>svg]:h-3.5"
          >
            {display.icon}
          </span>
        );
        const nameSpan = (
          <span
            className="truncate"
            style={{
              color: "rgba(255,255,255,0.88)", fontWeight: 500,
              letterSpacing: "0.01em", maxWidth: badge.width - (previewMode ? 56 : 40),
            }}
          >
            {badge.element.name}
          </span>
        );

        if (previewMode) {
          return (
            <div
              key={`${badge.nodeId}-${badge.element.id}-${i}`}
              className="absolute flex items-center rounded-full border pointer-events-none"
              style={badgeStyle}
            >
              {iconSpan}
              {nameSpan}
              <button
                type="button"
                className="pointer-events-auto ml-auto flex-shrink-0 text-gray-400 hover:text-white transition-colors p-0.5 rounded"
                onClick={(e) => { e.stopPropagation(); onBadgeClick(badge.element.id); }}
                aria-label="View details"
              >
                <Eye className="w-3 h-3" />
              </button>
            </div>
          );
        }

        return (
          <button
            key={`${badge.nodeId}-${badge.element.id}-${i}`}
            type="button"
            className={`absolute flex items-center rounded-full border transition-colors duration-150 pointer-events-auto ${
              interactive ? "graph-badge-interactive" : ""
            }`}
            style={{ ...badgeStyle, cursor: interactive ? "pointer" : "default" }}
            onClick={(e) => { e.stopPropagation(); if (interactive) onBadgeClick(badge.element.id); }}
            tabIndex={interactive ? 0 : -1}
          >
            {iconSpan}
            {nameSpan}
          </button>
        );
      })}
    </>
  );
}