import React from "react";
import { motion } from "framer-motion";
import type { CarouselMode } from "@/components/shared/ViewModeToggle";

const SPRING_TRANSITION = {
  type: "spring" as const,
  stiffness: 300,
  damping: 30,
  duration: 0.4,
};

const EXPAND_TRANSITION =
  "width 0.7s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.3s ease-out";
const COLLAPSE_TRANSITION = "width 0.4s ease-out, opacity 0.3s ease-out";

export interface AnimatedPanelLayoutProps {
  carouselMode: CarouselMode;
  chatWidth: number;
  graphWidth: number;
  isResizing: boolean;
  resizerProps: { onMouseDown: (e: React.MouseEvent) => void };
  chatPanel: React.ReactNode;
  graphPanel: React.ReactNode;
  /** Extra class names on the outer flex container. */
  containerClassName?: string;
  /** When true the resizer is visible but not interactive (e.g. chat-only sessions). */
  resizerDisabled?: boolean;
}

export function AnimatedPanelLayout({
  carouselMode,
  chatWidth,
  graphWidth,
  isResizing,
  resizerProps,
  chatPanel,
  graphPanel,
  containerClassName = "",
  resizerDisabled = false,
}: AnimatedPanelLayoutProps) {
  const isChatHidden = carouselMode === "graph";
  const isGraphHidden = carouselMode === "chat";

  return (
    <div className={`flex flex-1 min-w-0 ${containerClassName}`}>
      {/* ── Chat panel ──────────────────────────────────────────────── */}
      <motion.div
        key="chat-panel"
        initial={false}
        animate={{
          opacity: isChatHidden ? 0 : 1,
          x: isChatHidden ? -30 : 0,
          scale: isChatHidden ? 0.98 : 1,
        }}
        transition={SPRING_TRANSITION}
        className="flex-shrink-0 h-full flex flex-col"
        style={{
          width: isChatHidden ? 0 : `${chatWidth}%`,
          overflow: isChatHidden ? "hidden" : "visible",
          pointerEvents: isChatHidden ? "none" : "auto",
          transition:
            carouselMode === "chat" ? EXPAND_TRANSITION : COLLAPSE_TRANSITION,
        }}
      >
        {chatPanel}
      </motion.div>

      {/* ── Resizable divider ───────────────────────────────────────── */}
      {(carouselMode === "normal" || resizerDisabled) && (
        <div
          className={`w-1 transition-colors duration-200 flex-shrink-0 ${
            resizerDisabled ? "cursor-default" : "cursor-col-resize"
          } ${isResizing ? "opacity-100" : "opacity-50"}`}
          style={{ backgroundColor: "hsl(var(--primary))" }}
          onMouseDown={resizerDisabled ? undefined : resizerProps.onMouseDown}
          title={
            resizerDisabled
              ? "Resize unavailable"
              : "Drag to resize panels"
          }
        />
      )}

      {/* ── Graph panel ─────────────────────────────────────────────── */}
      <motion.div
        key="graph-panel"
        initial={false}
        animate={{
          opacity: isGraphHidden ? 0 : 1,
          x: isGraphHidden ? 30 : 0,
          scale: isGraphHidden ? 0.98 : 1,
        }}
        transition={SPRING_TRANSITION}
        className="flex-shrink-0 h-full"
        style={{
          width: isGraphHidden ? 0 : `${graphWidth}%`,
          overflow: isGraphHidden ? "hidden" : "visible",
          pointerEvents: isGraphHidden ? "none" : "auto",
          transition:
            carouselMode === "graph" ? EXPAND_TRANSITION : COLLAPSE_TRANSITION,
        }}
      >
        {graphPanel}
      </motion.div>
    </div>
  );
}
