import { Button } from "@/components/ui/button";
import { FaTh, FaList, FaClone } from "react-icons/fa";
import { useState, useEffect, useMemo, useRef } from "react";
import { Document } from "@/types";
import { UploadTab } from "./UploadTab";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { useQuery } from "@tanstack/react-query";
import { usePaginationStore } from "@/stores/usePaginationStore";
import { DocumentFilters } from "./DocumentFilters";
import { DocumentTable } from "./DocumentsTable";
import { PageLoader } from "@/components/shared/PageLoader";
import { DocumentGrid } from "./DocumentGrid";
import { deleteDoc, fetchDocuments } from "@/api/docs";
import { useToast } from "@/hooks/use-toast";

// Persist seen duplicate notices across page visits
const SEEN_DUP_NOTICES_STORAGE_KEY = "seen-duplication-notices";

function loadSeenDuplicateNoticeKeys(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(SEEN_DUP_NOTICES_STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as string[];
    return new Set(parsed);
  } catch {
    return new Set();
  }
}

function persistSeenDuplicateNoticeKey(key: string): void {
  if (typeof window === "undefined") return;
  try {
    const current = loadSeenDuplicateNoticeKeys();
    current.add(key);
    window.localStorage.setItem(
      SEEN_DUP_NOTICES_STORAGE_KEY,
      JSON.stringify(Array.from(current))
    );
  } catch {
    // no-op
  }
}

export default function Documents() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [activeDoc, setActiveDoc] = useState<Document | null>(null);
  const [fileTypeFilter, setFileTypeFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [retrying, setRetrying] = useState(false);

  const { currentPage, setPage, resetPage, itemsPerPage, } = usePaginationStore();
  const { toast } = useToast();
  const shownDupNoticesRef = useRef<Set<string>>(new Set());

  const { data: documents = [], isLoading, isError, error } = useQuery<Document[]>({
    queryKey: ['documents'],
    queryFn: fetchDocuments,
    refetchInterval: 10000,
    refetchOnMount: true, 
    refetchOnWindowFocus: true, 
  });

  useEffect(() => {
    resetPage();
  }, []);

  // Initialize in-memory set from localStorage so we don't re-show on fresh visits
  useEffect(() => {
    shownDupNoticesRef.current = loadSeenDuplicateNoticeKeys();
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [showUploadModal, activeDoc])

  // Show a one-time toast if any document was updated due to a duplicate upload
  useEffect(() => {
    if (!documents?.length) return;
    for (const doc of documents) {
      const notice = doc.duplication_notice;
      if (notice) {
        const key = `${doc.pipeline_id}:${notice.duplicate_at}`;
        if (!shownDupNoticesRef.current.has(key)) {
          shownDupNoticesRef.current.add(key);
          persistSeenDuplicateNoticeKey(key);
          const duplicateUploadedName = notice.duplicate_uploaded_name || "the uploaded file";
          const existingName = notice.existing_name || doc.source_name;
          toast({
            className: "bg-white text-black border border-gray-200",
            title: (
              <span className="inline-flex items-center gap-2">
                <FaClone className="text-red-500" />
                Duplicate detected
              </span>
            ),
            description: `"${duplicateUploadedName}" is already embedded as "${existingName}" and is now available.`,
            duration: 10000,
          });
        }
      }
    }
  }, [documents, toast]);

  const filteredDocuments = documents.filter((doc) => {
    const matchesType = fileTypeFilter === "all" || doc.type_data.file_type === fileTypeFilter;
    const matchesSearch = doc.source_name?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesType && matchesSearch;
  });

  const totalPages = Math.ceil(filteredDocuments.length / itemsPerPage);
  const paginatedDocuments = filteredDocuments.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const startIndex = (currentPage - 1) * itemsPerPage + 1;
  const endIndex = Math.min(currentPage * itemsPerPage, filteredDocuments.length);
  const footer = (
    <div className="flex items-center justify-between w-full px-4">
      <span className="text-sm text-gray-400">
        Showing {startIndex}-{endIndex} of {filteredDocuments.length} documents
      </span>

      <div className="flex items-center space-x-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setPage(Math.max(currentPage - 1, 1))}
          disabled={currentPage === 1}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setPage(Math.min(currentPage + 1, totalPages))}
          disabled={currentPage === totalPages}
        >
          Next
        </Button>

      </div>
    </div>
  );

  const filters = (
    <DocumentFilters
      fileTypeFilter={fileTypeFilter}
      setFileTypeFilter={setFileTypeFilter}
      searchQuery={searchQuery}
      setSearchQuery={setSearchQuery}
    />
  );

  const viewButtons = (
    <div className="flex items-center space-x-4">
      <Button onClick={() => setShowUploadModal(true)}>Upload Document</Button>
      <div className="flex">
        <Button
          variant={viewMode === "grid" ? "default" : "outline"}
          size="icon"
          onClick={() => { setViewMode("grid"); setActiveDoc(null) }}
        >
          <FaTh />
        </Button>
        <Button
          variant={viewMode === "list" ? "default" : "outline"}
          size="icon"
          onClick={() => { setViewMode("list"); setActiveDoc(null) }}
        >
          <FaList />
        </Button>
      </div>
    </div>
  );

  const onDeleteConfirmed = async (source_id: string) => {
    try {
      setDeleteLoading(true);
      await deleteDoc(source_id);
    } catch (error) {
      console.error("Error deleting document:", error);
    } finally {
      setDeleteLoading(false);
      setActiveDoc(null);
    }
  };

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
            <UploadTab setShowUploadModal={setShowUploadModal} fetchDocuments={fetchDocuments} />
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
                      <DocumentGrid
                        paginatedDocuments={paginatedDocuments}
                        activeDoc={activeDoc}
                        setActiveDoc={setActiveDoc}
                        deleteLoading={deleteLoading}
                        onDeleteConfirmed={onDeleteConfirmed}
                        retrying={retrying}
                        handleRetry={handleRetry}
                        footer={footer}
                      />
                    ) : (
                      <>
                        <div className="w-full">
                          <DocumentTable
                            documents={documents}
                            activeDoc={activeDoc}
                            setActiveDoc={setActiveDoc}
                            deleteLoading={deleteLoading}
                            onDeleteConfirmed={onDeleteConfirmed}
                            retrying={retrying}
                            handleRetry={handleRetry}
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
    </div>
  );
}
