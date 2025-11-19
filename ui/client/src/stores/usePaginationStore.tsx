import create from 'zustand';

interface PaginationState {
  currentPage: number;
  itemsPerPage: number;
  setPage: (page: number) => void;
  resetPage: () => void;
  setItemsPerPage: (itemsPerPage: number) => void;
  resetPagination: () => void;
}

interface PaginationConfig {
  initialItemsPerPage?: number;
  initialPage?: number;
}

export const createPaginationStore = (config: PaginationConfig = {}) => {
  const { initialItemsPerPage = 10, initialPage = 1 } = config;
  
  return create<PaginationState>((set) => ({
    currentPage: initialPage,
    itemsPerPage: initialItemsPerPage,
    setPage: (page) => set({ currentPage: page }),
    resetPage: () => set({ currentPage: initialPage }),
    setItemsPerPage: (itemsPerPage) => set({ itemsPerPage, currentPage: initialPage }),
    resetPagination: () => set({ currentPage: initialPage, itemsPerPage: initialItemsPerPage }),
  }));
};

export const usePaginationStore = createPaginationStore({ initialItemsPerPage: 12 });
