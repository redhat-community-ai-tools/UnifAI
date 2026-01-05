interface PaginationProps {
  pageIndex: number;
  pageCount: number;
  pageSize: number;
  totalItems: number;
  onPreviousPage: () => void;
  onNextPage: () => void;
  canPreviousPage: boolean;
  canNextPage: boolean;
  itemName?: string;
}

export function Pagination({
  pageIndex,
  pageCount,
  pageSize,
  totalItems,
  onPreviousPage,
  onNextPage,
  canPreviousPage,
  canNextPage,
  itemName = "items",
}: PaginationProps) {
  const startItem = pageIndex * pageSize + 1;
  const endItem = Math.min((pageIndex + 1) * pageSize, totalItems);

  return (
    <div className="flex items-center justify-between py-4">
      <span className="text-sm text-muted-foreground">
        Page <strong>{pageIndex + 1} of {pageCount || 1}</strong>
        {totalItems > 0 && (
          <>
            {' '}({itemName}{' '}
            {startItem}-{endItem}
            {' '}out of {totalItems})
          </>
        )}
      </span>
      <div className="flex items-center space-x-2">
        <button
          className="btn-animated px-3 py-1 border border-border text-muted-foreground rounded-lg hover:bg-muted hover:text-foreground transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={onPreviousPage}
          disabled={!canPreviousPage}
        >
          Previous
        </button>
        <button
          className="btn-animated px-3 py-1 border border-border text-foreground rounded-lg hover:bg-muted transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={onNextPage}
          disabled={!canNextPage}
        >
          Next
        </button>
      </div>
    </div>
  );
}

