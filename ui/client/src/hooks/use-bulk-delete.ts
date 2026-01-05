import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";
import { RowSelectionState } from "@tanstack/react-table";

interface UseBulkDeleteOptions<T> {
  deleteFunction: (ids: string[]) => Promise<any>;
  queryKeys: string[];
  itemName: string; // e.g., "document" or "channel"
  onSuccess?: () => void;
  getError?: (error: any) => string;
}

export function useBulkDelete<T>({
  deleteFunction,
  queryKeys,
  itemName,
  onSuccess,
  getError,
}: UseBulkDeleteOptions<T>) {
  const [bulkDeleteConfirm, setBulkDeleteConfirm] = useState<{ open: boolean; count: number }>({ 
    open: false, 
    count: 0 
  });
  const [bulkDeleteLoading, setBulkDeleteLoading] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const handleBulkDelete = async (ids: string[]) => {
    try {
      setBulkDeleteLoading(true);
      // Delete all selected items in a single API call
      await deleteFunction(ids);
      
      // Invalidate queries to refresh the list
      queryKeys.forEach(key => {
        queryClient.invalidateQueries({ queryKey: [key] });
      });
      
      toast({
        title: `✅ ${itemName.charAt(0).toUpperCase() + itemName.slice(1)}s Deleted`,
        description: `Successfully deleted ${ids.length} ${itemName}${ids.length > 1 ? 's' : ''}.`,
        variant: "default",
      });
      
      onSuccess?.();
    } catch (error) {
      console.error(`Error deleting ${itemName}s:`, error);
      const errorMessage = getError 
        ? getError(error)
        : (error instanceof Error ? error.message : `Failed to delete some ${itemName}s.`);
      
      const apiError = (error as any)?.response?.data?.error;
      toast({
        title: `❌ Bulk Deletion Failed`,
        description: apiError || errorMessage,
        variant: "destructive",
      });
      throw error;
    } finally {
      setBulkDeleteLoading(false);
    }
  };

  const handleDeleteSelected = (rowSelection: RowSelectionState) => {
    const selectedIds = Object.keys(rowSelection);
    if (selectedIds.length === 0) return;
    setBulkDeleteConfirm({ 
      open: true, 
      count: selectedIds.length
    });
  };

  const confirmBulkDelete = async (rowSelection: RowSelectionState) => {
    try {
      setBulkDeleteLoading(true);
      const idsToDelete = Object.keys(rowSelection);
      await handleBulkDelete(idsToDelete);
      // Only close modal after successful deletion
      setBulkDeleteConfirm({ open: false, count: 0 });
    } catch (error) {
      // Error already handled in handleBulkDelete - keep modal open on error
      console.error("Bulk delete failed:", error);
    } finally {
      setBulkDeleteLoading(false);
    }
  };

  return {
    bulkDeleteConfirm,
    setBulkDeleteConfirm,
    bulkDeleteLoading,
    handleBulkDelete,
    handleDeleteSelected,
    confirmBulkDelete,
  };
}