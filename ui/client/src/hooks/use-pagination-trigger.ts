import { useCallback, useEffect, useRef, RefObject } from "react";

type TriggerMode = "scroll" | "manual" | "intersection" | "button";

interface UsePaginationTriggerOptions {
  mode: TriggerMode;
  scrollRef?: RefObject<HTMLElement | null>;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
  threshold?: number;
}

interface UsePaginationTriggerReturn {
  scrollRef: RefObject<HTMLDivElement>;
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

  // Create internal ref if none provided (for convenience)
  const internalScrollRef = useRef<HTMLDivElement>(null);
  const scrollRef = externalScrollRef || internalScrollRef;

  // Manual trigger function (for button mode)
  const next = useCallback(() => {
    if (canFetch) {
      fetchNextPage();
    }
  }, [canFetch, fetchNextPage]);

  const handleScroll = useCallback(() => {
    if (!scrollRef?.current || !canFetch) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    if (scrollHeight - scrollTop - clientHeight < threshold) {
      fetchNextPage(); // React Query deduplicates internally
    }
  }, [scrollRef, canFetch, fetchNextPage, threshold]);

  useEffect(() => {
    if (mode !== "scroll") return;

    const container = scrollRef?.current;
    if (!container) return;

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, [mode, scrollRef, handleScroll]);

  return {
    scrollRef: scrollRef as RefObject<HTMLDivElement>,
    next,
    canFetch,
    isFetchingNextPage,
  };
}
