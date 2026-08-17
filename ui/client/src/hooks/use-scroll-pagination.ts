import { usePaginationTrigger } from "@/hooks/use-pagination-trigger";

interface ScrollPaginationSource {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
}

export function useScrollPagination(source: ScrollPaginationSource) {
  return usePaginationTrigger({
    mode: "scroll",
    hasNextPage: source.hasNextPage,
    isFetchingNextPage: source.isFetchingNextPage,
    fetchNextPage: source.fetchNextPage,
  });
}
