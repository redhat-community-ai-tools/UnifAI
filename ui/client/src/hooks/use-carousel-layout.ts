import { useState, useCallback, useEffect } from "react";
import type { CarouselMode } from "@/components/shared/ViewModeToggle";

export interface UseCarouselLayoutOptions {
  /** Default chat panel width as percentage of the container (0–100). */
  defaultChatPercent?: number;
  /** CSS selector for the resize container (used to calculate relative mouse position). */
  containerSelector: string;
  /** Minimum chat panel width when dragging the resizer (default 25). */
  minPercent?: number;
  /** Maximum chat panel width when dragging the resizer (default 80). */
  maxPercent?: number;
  /** When true, mode changes are blocked and mode resets to 'normal'. */
  disabled?: boolean;
}

export function useCarouselLayout({
  defaultChatPercent = 65,
  containerSelector,
  minPercent = 25,
  maxPercent = 80,
  disabled = false,
}: UseCarouselLayoutOptions) {
  const defaultGraphPercent = 100 - defaultChatPercent;

  const [carouselMode, setCarouselModeState] = useState<CarouselMode>("normal");
  const [chatWidth, setChatWidth] = useState(defaultChatPercent);
  const [graphWidth, setGraphWidth] = useState(defaultGraphPercent);
  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    if (disabled) {
      if (carouselMode !== "normal") {
        setCarouselModeState("normal");
        setChatWidth(defaultChatPercent);
        setGraphWidth(defaultGraphPercent);
      }
      setIsResizing(false);
    }
  }, [disabled]);

  const setCarouselMode = useCallback(
    (mode: CarouselMode) => {
      if (disabled) return;
      switch (mode) {
        case "normal":
          setCarouselModeState("normal");
          setChatWidth(defaultChatPercent);
          setGraphWidth(defaultGraphPercent);
          break;
        case "chat":
          setCarouselModeState("chat");
          setChatWidth(100);
          setGraphWidth(0);
          break;
        case "graph":
          setCarouselModeState("graph");
          setChatWidth(0);
          setGraphWidth(100);
          break;
      }
    },
    [disabled, defaultChatPercent, defaultGraphPercent],
  );

  // ── Resize handlers ─────────────────────────────────────────────────────
  const handleResizeMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const handleResizeMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing || disabled) return;
      const container = document.querySelector(containerSelector);
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const relativeX = ((e.clientX - rect.left) / rect.width) * 100;
      const clamped = Math.min(Math.max(relativeX, minPercent), maxPercent);
      setChatWidth(clamped);
      setGraphWidth(100 - clamped);
    },
    [isResizing, disabled, containerSelector, minPercent, maxPercent],
  );

  const handleResizeMouseUp = useCallback(() => {
    setIsResizing(false);
  }, []);

  useEffect(() => {
    if (isResizing) {
      document.addEventListener("mousemove", handleResizeMouseMove);
      document.addEventListener("mouseup", handleResizeMouseUp);
      document.body.style.cursor = "col-resize";
    } else {
      document.removeEventListener("mousemove", handleResizeMouseMove);
      document.removeEventListener("mouseup", handleResizeMouseUp);
      document.body.style.cursor = "";
    }
    return () => {
      document.removeEventListener("mousemove", handleResizeMouseMove);
      document.removeEventListener("mouseup", handleResizeMouseUp);
      document.body.style.cursor = "";
    };
  }, [isResizing, handleResizeMouseMove, handleResizeMouseUp]);

  return {
    carouselMode,
    chatWidth,
    graphWidth,
    isResizing,
    setCarouselMode,
    resizerProps: { onMouseDown: handleResizeMouseDown },
  };
}
