import { useState, useEffect } from "react";
import { FaEye, FaEdit } from "react-icons/fa";
import { DataCard } from "@/components/shared/DataCard";
import { fileByColors, getDataToDisplay, getFileIcon } from "@/features/helpers";
import { Document } from "@/types";
import { RowSelectionState } from "@tanstack/react-table";
import { DocumentData } from "./DocumentData";
import { PIPELINE_STATUS } from "@/constants/pipelineStatus";
import { EditDocumentModal } from "./EditDocumentModal";

interface DocumentGridProps {
  documents: Document[];
  activeDoc: Document | null;
  setActiveDoc: (doc: Document | null) => void;
  onActiveDocChange: () => void;
  deleteLoading: boolean;
  onDeleteConfirmed: (id: string) => void;
  retrying: boolean;
  handleRetry: (id: string) => void;
  rowSelection?: RowSelectionState;
  onRowSelectionChange?: (selection: RowSelectionState) => void;
  onRefresh?: () => void;
  expandedDocDetails: Document | null;
  isLoadingDetails: boolean;
}

const getFooterText = (doc: Document) => {
  if (!doc.status || doc.status === PIPELINE_STATUS.PENDING || doc.status === PIPELINE_STATUS.FAILED) return "-";
  return getDataToDisplay(doc) || `${doc.pipeline_stats?.chunks_generated} chunks`;
};

// const getExtraTopRight = (
//   doc: Document,
//   handleRetry: (id: string) => void,
//   retrying: boolean
// ) =>
//   doc.status === PIPELINE_STATUS.FAILED ? (
//     <Button
//       variant="ghost"
//       size="icon"
//       className="h-5 w-5 p-0"
//       onClick={(e) => {
//         e.stopPropagation();
//         handleRetry(doc.pipeline_id);
//       }}
//       disabled={retrying}
//     >
//       <FaSync className={`animate-spin ${retrying ? "" : "hidden"}`} />
//       {!retrying && <FaSync />}
//     </Button>
//   ) : null;

const getActions = (
  doc: Document,
  activeDoc: Document | null,
  setActiveDoc: (doc: Document | null) => void,
  setEditDoc: (doc: Document | null) => void,
  rowSelection: RowSelectionState,
  onRowSelectionChange?: (selection: RowSelectionState) => void
) => {
  const actions: any[] = [
    {
      icon: <FaEye />,
      onClick: () => setActiveDoc(doc === activeDoc ? null : doc),
    },
    {
      icon: <FaEdit className="h-3 w-3" />,
      onClick: () => setEditDoc(doc),
    },
  ];

  // Add checkbox action if selection is enabled - always last
  if (onRowSelectionChange) {
    const isSelected = rowSelection[doc.source_id] === true;
    actions.push({
      icon: null, // Will be replaced with checkbox
      onClick: () => {},
      isCheckbox: true,
      checked: isSelected,
      onCheckboxChange: (checked: boolean) => {
        const newSelection = { ...rowSelection };
        if (checked) {
          newSelection[doc.source_id] = true;
        } else {
          delete newSelection[doc.source_id];
        }
        onRowSelectionChange(newSelection);
      },
    });
  }

  return actions;
};

export const DocumentGrid = ({
  documents, 
  activeDoc, 
  setActiveDoc, 
  onActiveDocChange,
  rowSelection = {},
  onRowSelectionChange,
  onRefresh,
  expandedDocDetails,
  isLoadingDetails,
}: DocumentGridProps) => {
  const [editDoc, setEditDoc] = useState<Document | null>(null);

  // Fetch document details when activeDoc changes
  useEffect(() => {
    onActiveDocChange()
  }, [activeDoc?.source_id]);

  return (
    <>
      <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {documents.map((doc) => (
              <DataCard
                key={doc.pipeline_id}
                iconRenderer={() => getFileIcon(doc.type_data.file_type)}
                iconBgClass={fileByColors[doc.type_data.file_type]}
                title={doc.source_name}
                status={doc.status}
                statusErrorMessage={doc.type_data?.last_error}
                subtitle={getDataToDisplay(doc) || `${doc.type_data.page_count} pages | ${doc.type_data.file_type} | ${doc.type_data.file_size}`}
                metadata={`Uploaded ${new Date(doc.created_at).toLocaleString("en-GB")} by ${doc.upload_by}`}
                footer={getFooterText(doc)}
                selected={doc === activeDoc}
                onClick={() => setActiveDoc(doc === activeDoc ? null : doc)}
                actions={getActions(doc, activeDoc, setActiveDoc, setEditDoc, rowSelection, onRowSelectionChange)}
              />
            ))}
          </div>
      </div>

      {activeDoc && (
        <div className="mt-6">
          <DocumentData doc={activeDoc} details={expandedDocDetails} isLoading={isLoadingDetails}/>
        </div>
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
    </>
  );
};
