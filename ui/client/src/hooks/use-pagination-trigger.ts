import { useCallback, useEffect, useRef, RefObject } from "react";

type TriggerMode = "scroll" | "manual";

interface UsePaginationTriggerOptions {
  mode: TriggerMode;
  scrollRef?: RefObject<HTMLDivElement | null>;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
  threshold?: number;
}

interface UsePaginationTriggerReturn {
  scrollRef: RefObject<HTMLDivElement | null>;
  next: () => void;
  canFetch: boolean;
  isFetchingNextPage: boolean;
}

/**
 * Hook for managing pagination triggers (scroll, manual button, intersection observer, etc.)
 *
 * For scroll mode, you can either:
 * 1. Pass your own scrollRef
 * 2. Use the returned scrollRef (hook creates it for you)
 *
 * @example Scroll mode (auto-managed ref):
 * ```tsx
 * const { scrollRef, isFetchingNextPage } = usePaginationTrigger({
 *   mode: "scroll",
 *   hasNextPage: query.hasNextPage,
 *   isFetchingNextPage: query.isFetchingNextPage,
 *   fetchNextPage: query.fetchNextPage,
 * });
 *
 * return <div ref={scrollRef}>...</div>;
 * ```
 *
 * @example Manual mode (button):
 * ```tsx
 * const { next, canFetch } = usePaginationTrigger({
 *   mode: "manual",
 *   hasNextPage: query.hasNextPage,
 *   isFetchingNextPage: query.isFetchingNextPage,
 *   fetchNextPage: query.fetchNextPage,
 * });
 *
 * return <Button onClick={next} disabled={!canFetch}>Load More</Button>;
 * ```
 */
export function usePaginationTrigger({
  mode,
  scrollRef: externalScrollRef,
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  threshold = 200, //early trigger when 200px from bottom for more seamless experience
}: UsePaginationTriggerOptions): UsePaginationTriggerReturn {
  const canFetch = hasNextPage && !isFetchingNextPage;
  const canFetchRef = useRef(canFetch);
  canFetchRef.current = canFetch;

  // Create internal ref if none provided (for convenience)
  const internalScrollRef = useRef<HTMLDivElement>(null);
  const scrollRef = externalScrollRef || internalScrollRef;

  // Manual trigger function (for button mode)
  const next = useCallback(() => {
    if (canFetchRef.current) {
      fetchNextPage();
    }
  }, [fetchNextPage]);

  const handleScroll = useCallback(() => {
    if (!scrollRef?.current || !canFetchRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    if (scrollHeight - scrollTop - clientHeight < threshold) {
      fetchNextPage();
    }
  }, [scrollRef, fetchNextPage, threshold]);

  useEffect(() => {
    if (mode !== "scroll") return;

    const container = scrollRef?.current;
    if (!container) return;

    container.addEventListener("scroll", handleScroll, { passive: true });
    // Run once on bind: covers post-load mount and content shorter than the viewport.
    handleScroll();

    return () => container.removeEventListener("scroll", handleScroll);
    // hasNextPage: rebind after first page loads and the scroll node mounts.
    // isFetchingNextPage: after a page lands, re-check in case the list still
    // doesn't fill the viewport (no scroll event would fire otherwise).
  }, [mode, scrollRef, handleScroll, hasNextPage, isFetchingNextPage]);

  return {
    scrollRef,
    next,
    canFetch,
    isFetchingNextPage,
  };
}
