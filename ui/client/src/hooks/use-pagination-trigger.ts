import { useCallback, useEffect, useRef, RefObject } from "react";

type TriggerMode = "scroll" | "manual";

interface UsePaginationTriggerOptions {
  mode: TriggerMode;
  scrollRef?: RefObject<HTMLElement | null>;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
  threshold?: number;
}

export function usePaginationTrigger({
  mode,
  scrollRef,
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  threshold = 100,
}: UsePaginationTriggerOptions) {
  const canFetch = hasNextPage && !isFetchingNextPage;

  // This function can be called to manually (with a button) trigger fetching the next page
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

  return { next, canFetch };
}
