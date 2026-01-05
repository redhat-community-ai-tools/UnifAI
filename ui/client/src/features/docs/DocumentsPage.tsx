import { Button } from "@/components/ui/button";
import { FaTh, FaList } from "react-icons/fa";
import { useState, useEffect } from "react";
import { Document } from "@/types";
import { UploadTab } from "./UploadTab";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DocumentFilters } from "./DocumentFilters";
import { DocumentTable } from "./DocumentsTable";
import { PageLoader } from "@/components/shared/PageLoader";
import { DocumentGrid } from "./DocumentGrid";
import { deleteDocs, fetchDocumentDetails, fetchDocuments } from "@/api/docs";
import { RowSelectionState } from "@tanstack/react-table";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { useToast } from "@/hooks/use-toast";
import { isEmbeddingActivelyProcessing } from "@/features/helpers";
import { BulkDeleteButton } from "@/components/shared/BulkDeleteButton";
import { useBulkDelete } from "@/hooks/use-bulk-delete";
import { Pagination } from "@/components/shared/Pagination";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';

export default function Documents() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "list">("list");
  const [activeDoc, setActiveDoc] = useState<Document | null>(null);
  const [fileTypeFilter, setFileTypeFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [expandedDocDetails, setExpandedDocDetails] = useState<Document | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  
  // Grid pagination state
  const [gridPageIndex, setGridPageIndex] = useState(0);
  const gridPageSize = 15;

  const queryClient = useQueryClient();
  const { toast } = useToast();

  const {
    bulkDeleteConfirm,
    setBulkDeleteConfirm,
    bulkDeleteLoading,
    handleDeleteSelected: handleDeleteSelectedBase,
    confirmBulkDelete: confirmBulkDeleteBase,
  } = useBulkDelete({
    deleteFunction: deleteDocs,
    queryKeys: ['documents'],
    itemName: 'document',
    onSuccess: () => setRowSelection({}),
  });

  const hasActiveOperations = (docs: Document[] | undefined) => {
    if (!docs || !Array.isArray(docs)) return false;
    return docs.some(doc => isEmbeddingActivelyProcessing(doc));
  };

  const { data: documents = [], isLoading, isError, error, refetch } = useQuery<Document[]>({
    queryKey: ['documents'],
    queryFn: fetchDocuments,
    staleTime: 15 * 1000,
    refetchOnMount: true,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const data = query.state.data as Document[] | undefined;
      const hasActive = hasActiveOperations(data);
      return hasActive ? 5000 : false;
    },
  });

  // Refetch documents immediately when upload modal closes to show new documents
  useEffect(() => {
    if (!showUploadModal) {
      queryClient.refetchQueries({ queryKey: ['documents'] });
      setViewMode("list");
    }
  }, [showUploadModal]);

  const filteredDocuments = documents.filter((doc) => {
    const matchesType = fileTypeFilter === "all" || doc.type_data.file_type === fileTypeFilter;
    const matchesSearch = doc.source_name?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesType && matchesSearch;
  });

  // Reset grid page when filters change
  useEffect(() => {
    setGridPageIndex(0);
  }, [fileTypeFilter, searchQuery, documents.length]);

  // Grid pagination calculations
  const gridPageCount = Math.ceil(filteredDocuments.length / gridPageSize);
  const paginatedGridDocuments = filteredDocuments.slice(
    gridPageIndex * gridPageSize,
    (gridPageIndex + 1) * gridPageSize
  );

  const filters = (
    <DocumentFilters
      fileTypeFilter={fileTypeFilter}
      setFileTypeFilter={setFileTypeFilter}
      searchQuery={searchQuery}
      setSearchQuery={setSearchQuery}
    />
  );

  const selectedCount = Object.keys(rowSelection).length;

  const viewButtons = (
    <div className="flex items-center space-x-4">
        <UmamiTrack 
          event={UmamiEvents.UPLOAD_DOCUMENT_BUTTON}
        >
      <Button onClick={() => setShowUploadModal(true)}>Upload Document</Button>
      </UmamiTrack>
      <div className="flex">
        <UmamiTrack 
          event={UmamiEvents.VIEW_DOCUMENT_LIST_BUTTON}
        >
        <Button
          variant={viewMode === "list" ? "default" : "outline"}
          size="icon"
          onClick={() => { setViewMode("list"); setActiveDoc(null) }}
        >
          <FaList />
        </Button>
        </UmamiTrack>
        <UmamiTrack 
          event={UmamiEvents.VIEW_DOCUMENT_GRID_BUTTON}
        >
        <Button
          variant={viewMode === "grid" ? "default" : "outline"}
          size="icon"
          onClick={() => { setViewMode("grid"); setActiveDoc(null) }}
        >
          <FaTh />
        </Button>
        </UmamiTrack>
      </div>
    </div>
  );

  const onDeleteConfirmed = async (source_id: string) => {
    try {
      setDeleteLoading(true);
      await deleteDocs([source_id]);
      // Invalidate queries to refresh the list after successful deletion
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      toast({
        title: "✅ Document Deleted",
        description: "The document has been successfully deleted.",
        variant: "default",
      });
    } catch (error) {
      console.error("Error deleting document:", error);
      toast({
        title: "❌ Deletion Failed",
        description: error instanceof Error ? error.message : "Failed to delete document.",
        variant: "destructive",
      });
      throw error; // Re-throw to let the modal handle the error state
    } finally {
      setDeleteLoading(false);
      setActiveDoc(null);
    }
  };

  const confirmBulkDelete = async () => {
    await confirmBulkDeleteBase(rowSelection);
  };

  const onActiveDocChange = () => {
    if (activeDoc) {
          setIsLoadingDetails(true);
          setExpandedDocDetails(null);
          fetchDocumentDetails(activeDoc.source_id)
            .then((details) => {
              setExpandedDocDetails(details);
            })
            .catch((err) => {
              console.error("Failed to fetch document details:", err);
            })
            .finally(() => {
              setIsLoadingDetails(false);
            });
    } else {
      setExpandedDocDetails(null);
    }
}

  const handleRetry = async (id: string) => {
    try {
      setRetrying(true);
      // await axiosInstance.put("/api/docs/retry.embedding", { "pipelineId": id });
    } catch (error) {
      console.error("Error retrying embedding:", error);
    } finally {
      setRetrying(false);
    }
  };
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Document Library"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <div className="flex-1 overflow-auto px-6 pb-6">
          {showUploadModal ? (
            <UploadTab setShowUploadModal={setShowUploadModal} fetchDocuments={refetch} />
          ) : (
            <div className="mt-6">
              {isLoading ? (
                <PageLoader />
              ) : isError ? (
                <p className="text-sm text-red-500">Error: {(error as Error).message}</p>
              ) : (
                <>
                  {/* Top controls: filters only in grid view, view buttons and upload always */}
                  <div className="flex items-center justify-between mb-4">
                    {viewMode === "grid" ? (<div className="flex-1">{filters}</div>) : (<div className="flex-1" />)}
                    {viewButtons}
                  </div>

                  {documents.length ? (
                    viewMode === "grid" ? (
                      <>
                        <DocumentGrid
                          documents={paginatedGridDocuments}
                          activeDoc={activeDoc}
                          setActiveDoc={setActiveDoc}
                          onActiveDocChange={onActiveDocChange}
                          deleteLoading={deleteLoading}
                          onDeleteConfirmed={onDeleteConfirmed}
                          retrying={retrying}
                          handleRetry={handleRetry}
                          rowSelection={rowSelection}
                          onRowSelectionChange={setRowSelection}
                          onRefresh={refetch}
                          expandedDocDetails={expandedDocDetails}
                          isLoadingDetails={isLoadingDetails}
                        />
                        {filteredDocuments.length > gridPageSize && (
                          <div className="px-6">
                            <Pagination
                              pageIndex={gridPageIndex}
                              pageCount={gridPageCount}
                              pageSize={gridPageSize}
                              totalItems={filteredDocuments.length}
                              onPreviousPage={() => setGridPageIndex(prev => prev - 1)}
                              onNextPage={() => setGridPageIndex(prev => prev + 1)}
                              canPreviousPage={gridPageIndex > 0}
                              canNextPage={gridPageIndex < gridPageCount - 1}
                              itemName="documents"
                            />
                          </div>
                        )}
                      </>
                    ) : (
                      <>
                        <div className="w-full">
                          <DocumentTable
                            documents={filteredDocuments}
                            activeDoc={activeDoc}
                            setActiveDoc={setActiveDoc}
                            onActiveDocChange={onActiveDocChange}
                            deleteLoading={deleteLoading}
                            onDeleteConfirmed={onDeleteConfirmed}
                            retrying={retrying}
                            handleRetry={handleRetry}
                            rowSelection={rowSelection}
                            onRowSelectionChange={setRowSelection}
                            onRefresh={refetch}
                            expandedDocDetails={expandedDocDetails}
                            isLoadingDetails={isLoadingDetails}
                          />
                        </div>
                      </>
                    )
                  ) : (
                    <p>No documents available.</p>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bulk Delete Confirmation Dialog */}
      <ConfirmDialog
        open={bulkDeleteConfirm.open}
        title="Delete Selected Documents"
        message={`Are you sure you want to delete ${bulkDeleteConfirm.count} selected document${bulkDeleteConfirm.count > 1 ? 's' : ''}? This action cannot be undone.`}
        confirmLabel="Yes, Delete"
        cancelLabel="Cancel"
        loading={bulkDeleteLoading}
        onCancel={() => {
          if (!bulkDeleteLoading) {
            setBulkDeleteConfirm({ open: false, count: 0 });
          }
        }}
        onConfirm={confirmBulkDelete}
      />
    </div>
  );
}
