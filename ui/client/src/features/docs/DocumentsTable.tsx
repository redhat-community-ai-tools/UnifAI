import React, { useState, useEffect } from "react";
import { FaEye, FaTrash, FaEdit } from "react-icons/fa";
import { Button } from "@/components/ui/button";
import { InlineLoader } from "@/components/shared/InlineLoader";
import { Document } from "@/types";
import { getFileIcon, fileByColors, isEmbeddingActivelyProcessing, getDataToDisplay } from "../helpers";
import { DataTable, DataTableColumn } from "@/components/shared/DataTable";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { DocumentData } from "./DocumentData";
import { PIPELINE_STATUS } from "@/constants/pipelineStatus";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { RowSelectionState } from "@tanstack/react-table";
import { SelectionCheckbox } from "@/components/shared/SelectionCheckbox";
import { getSupportedFileExtensions } from "@/api/docs";
import { EditDocumentModal } from "./EditDocumentModal";
import { useQuery } from "@tanstack/react-query";

interface DocumentTableProps {
  documents: Document[];
  activeDoc?: Document | null;
  setActiveDoc?: (doc: Document | null) => void;
  onActiveDocChange: () => void;
  deleteLoading?: boolean; // Optional: legacy
  onDeleteConfirmed?: (id: string) => void;
  retrying?: boolean;
  handleRetry?: (id: string) => void;
  rowSelection?: RowSelectionState;
  onRowSelectionChange?: (selection: RowSelectionState) => void;
  onRefresh?: () => void;
  expandedDocDetails: Document | null;
  isLoadingDetails: boolean;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  documents, 
  activeDoc, 
  setActiveDoc, 
  onActiveDocChange,
  deleteLoading, 
  onDeleteConfirmed, 
  retrying, 
  handleRetry,
  rowSelection,
  onRowSelectionChange,
  onRefresh,
  expandedDocDetails,
  isLoadingDetails,
  
}) => {
  const [confirmDoc, setConfirmDoc] = useState<Document | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [editDoc, setEditDoc] = useState<Document | null>(null);

  // Fetch document details when activeDoc changes
  useEffect(() => {
    onActiveDocChange()
  }, [activeDoc?.source_id]);

  // Use TanStack Query for caching supported extensions across pages/refetches
  // Extensions are static data, so we use staleTime: Infinity to prevent refetching
  const { data: fileTypeFilterOptions = [] } = useQuery({
    queryKey: ['supportedFileExtensions'],
    queryFn: getSupportedFileExtensions,
    staleTime: Infinity, // Extensions never change during a session
    select: (extensions) => extensions.map(ext => ext.substring(1).toUpperCase()),
  });

  const columns: DataTableColumn<Document>[] = React.useMemo(() => [
    {
      accessorKey: "source_name",
      header: "Name",
      cell: ({ row }) => {
        const doc = row.original;
        return (
          <div className="flex items-center space-x-2">
            <div className={`p-1.5 rounded ${fileByColors[doc.type_data.file_type]}`}>
              {getFileIcon(doc.type_data.file_type)}
            </div>
            <div className="truncate max-w-[200px]">{doc.source_name}</div>
          </div>
        );
      },
      meta: { align: "left", filterType: "text" },
    },
    {
      accessorKey: "created_at",
      header: "Uploaded At",
      cell: ({ row }) =>
        new Date(row.original.created_at).toLocaleString("en-GB"),
      meta: { align: "left" },
    },
    {
      accessorKey: "upload_by",
      header: "Uploaded By",
      cell: ({ row }) => row.original.upload_by,
      meta: { align: "left" },
    },
    {
      accessorKey: "type_data.page_count",
      header: "Pages",
      cell: ({ row }) => {
        const doc = row.original;
        return getDataToDisplay(doc) || doc.type_data.page_count;
      },
      meta: { align: "center" },
    },
    {
      accessorKey: "type_data.file_size",
      header: "Size (MB)",
      cell: ({ row }) => {
        const doc = row.original;
        if (isEmbeddingActivelyProcessing(doc)) return <InlineLoader />;
        if (doc.status === PIPELINE_STATUS.PENDING) return "-";
        return doc.type_data.file_size
      },
      meta: { align: "center" },
    },
    {
      accessorKey: "type_data.file_type",
      header: "File Type",
      cell: ({ row }) => row.original.type_data.file_type?.toUpperCase(),
      meta: {
        align: "center",
        filterType: "select",
        filterOptions: fileTypeFilterOptions,
      },
    },
    {
      accessorKey: "pipeline_stats.chunks_generated",
      header: "Chunks",
      cell: ({ row }) => {
        const doc = row.original;
        return getDataToDisplay(doc) || `${doc.pipeline_stats.chunks_generated}`
      },
      meta: { align: "center" },
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => {
        const doc = row.original;
        return (
          <StatusBadge 
            status={doc.status} 
            errorMessage={doc.type_data?.last_error}
          />
        );
      },
      meta: {
        align: "center",
        filterType: "select",
        filterOptions: [
          "Pending",
          "In Progress", 
          "Collecting",
          "Processing",
          "Chunking & Embedding",
          "Storing",
          "Orchestrating",
          "Done",
          "Paused",
          "Failed",
          "Archived"
        ],
      },
    },
    {
      id: "actions",
      header: ({ table }) => {
        if (!onRowSelectionChange || !rowSelection) return "";
        
        // Calculate if all filtered rows are selected
        const filteredRows = table.getFilteredRowModel().rows;
        const isAllFilteredSelected = filteredRows.length > 0 && filteredRows.every(row => {
          return rowSelection[row.original.source_id];
        });
        
        // Handle select all toggle for filtered rows
        const handleSelectAllChange = (checked: boolean) => {
          const newSelection = { ...rowSelection };
          if (checked) {
            filteredRows.forEach(row => {
              newSelection[row.original.source_id] = true;
            });
          } else {
            filteredRows.forEach(row => {
              delete newSelection[row.original.source_id];
            });
          }
          onRowSelectionChange(newSelection);
        };
        
        return (
          <SelectionCheckbox
            checked={isAllFilteredSelected}
            onCheckedChange={handleSelectAllChange}
            ariaLabel="Select all filtered rows"
            align="right"
          />
        );
      },
      cell: ({ row }) => {
        const doc = row.original;
        const isActive = activeDoc?.pipeline_id === doc.pipeline_id;
        
        // Handle individual row selection toggle
        const handleRowSelect = (checked: boolean) => {
          if (!onRowSelectionChange || !rowSelection) return;
          const newSelection = { ...rowSelection };
          if (checked) {
            newSelection[doc.source_id] = true;
          } else {
            delete newSelection[doc.source_id];
          }
          onRowSelectionChange(newSelection);
        };
        
        return (
          <div className="flex items-center space-x-2 justify-end">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 p-0"
              onClick={() => setActiveDoc?.(isActive ? null : doc)}
            >
              <FaEye className={isActive ? "text-primary" : ""} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 p-0"
              onClick={() => setEditDoc(doc)}
            >
              <FaEdit className="h-3 w-3" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 p-0"
              onClick={() => {
                setConfirmDoc(doc);
                setConfirmLoading(false);
              }}
              disabled={deleteLoading || confirmLoading}
            >
              <FaTrash className="h-3 w-3" />
            </Button>
            {onRowSelectionChange && rowSelection && (
              <SelectionCheckbox
                checked={rowSelection[doc.source_id] === true}
                onCheckedChange={handleRowSelect}
                ariaLabel={`Select document ${doc.source_name}`}
              />
            )}
          </div>
        );
      },
      meta: { align: "right" },
    },
  ], [activeDoc, setActiveDoc, rowSelection, onRowSelectionChange, fileTypeFilterOptions]);

  return (
    <div className="w-full">
      <DataTable
        columns={columns}
        data={documents}
        enableGlobalFilter={false}
        enableColumnFilters={true}
        enablePagination={true}
        enableRowSelection={false}
        getRowId={(row) => row.source_id}
        initialState={{
          pagination: { pageIndex: 0, pageSize: 15 }
        }}
        expendedRow={activeDoc}
        expandedRowDetails={expandedDocDetails}
        isLoadingExpanded={isLoadingDetails}
        renderExpandedRow={(doc, details, isLoading) => (
          <DocumentData doc={doc} details={details} isLoading={isLoading} />
        )}
      />

      {confirmDoc && (
        <ConfirmDialog
          open={true}
          title="Delete Document"
          message={`Are you sure you want to delete "${confirmDoc.source_name}"?`}
          confirmLabel="Yes, Delete"
          loading={confirmLoading}
          onCancel={() => {
            if (!confirmLoading) setConfirmDoc(null);
          }}
          onConfirm={async () => {
            try {
              setConfirmLoading(true);
              await onDeleteConfirmed?.(confirmDoc.source_id);
              setConfirmDoc(null);
            } catch (err) {
              console.error("Delete failed:", err);
            } finally {
              setConfirmLoading(false);
            }
          }}
        />
      )}

      {editDoc && (
        <EditDocumentModal
          key={editDoc.source_id}
          document={editDoc}
          open={true}
          onClose={() => setEditDoc(null)}
          onUpdated={() => onRefresh?.()}
        />
      )}
    </div>
  );
};
