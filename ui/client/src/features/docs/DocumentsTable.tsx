import React, { useState } from "react";
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
import { EditDocumentModal } from "./EditDocumentModal";

interface DocumentTableProps {
  documents: Document[];
  activeDoc?: Document | null;
  setActiveDoc?: (doc: Document | null) => void;
  deleteLoading?: boolean; // Optional: legacy
  onDeleteConfirmed?: (id: string) => void;
  retrying?: boolean;
  handleRetry?: (id: string) => void;
  onRefresh?: () => void;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({documents, activeDoc, setActiveDoc, deleteLoading, onDeleteConfirmed, retrying, handleRetry, onRefresh}) => {
  const [confirmDoc, setConfirmDoc] = useState<Document | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [editDoc, setEditDoc] = useState<Document | null>(null);

  const columns: DataTableColumn<Document>[] = [
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
        filterOptions: ["PDF", "DOCX", "TXT", "XLSX", "OTHER"],
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
          <StatusBadge status={doc.status} />
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
      header: "",
      cell: ({ row }) => {
        const doc = row.original;
        const isActive = activeDoc?.pipeline_id === doc.pipeline_id;
        return (
          <div className="flex items-center space-x-2 justify-end">
            {/* {doc.status === PIPELINE_STATUS.FAILED && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 p-0"
                onClick={() => handleRetry?.(doc.pipeline_id)}
                disabled={retrying}
              >
                <FaSync />
              </Button>
            )} */}
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
          </div>
        );
      },
      meta: { align: "right" },
    },
  ];

  return (
    <div className="w-full">
      <DataTable
        columns={columns}
        data={documents}
        enableGlobalFilter={false}
        enableColumnFilters={true}
        enablePagination={true}
        initialState={{
          pagination: { pageIndex: 0, pageSize: 15 }
        }}
        expendedRow={activeDoc}
        renderExpandedRow={(doc) => <DocumentData doc={doc} />}
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
