import { FaEye, FaSync, FaTrash } from "react-icons/fa";
import { DataCard } from "@/components/shared/DataCard";
import { fileByColors, getDataToDisplay, getFileIcon, isEmbeddingActivelyProcessing } from "@/features/helpers";
import { InlineLoader } from "@/components/shared/InlineLoader";
import { Document } from "@/types";
 
import { DocumentData } from "./DocumentData";
import { PIPELINE_STATUS } from "@/constants/pipelineStatus";

interface DocumentGridProps {
  paginatedDocuments: Document[];
  activeDoc: Document | null;
  setActiveDoc: (doc: Document | null) => void;
  deleteLoading: boolean;
  onDeleteConfirmed: (id: string) => void;
  retrying: boolean;
  handleRetry: (id: string) => void;
  footer?: React.ReactNode;
}

const getFooterText = (doc: Document) => {
  if (isEmbeddingActivelyProcessing(doc)) return <InlineLoader />;
  if (!doc.status || doc.status === PIPELINE_STATUS.PENDING || doc.status === PIPELINE_STATUS.FAILED) return "-";
  return `${doc.pipeline_stats?.chunks_generated} chunks`;
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
  deleteLoading: boolean,
  onDeleteConfirmed: (id: string) => void
) => [
  {
    icon: <FaEye />,
    onClick: () => setActiveDoc(doc === activeDoc ? null : doc),
  },
  {
    icon: <FaTrash className="h-3 w-3" />,
    onClick: () => {},
    confirm: {
      title: "Delete Document",
      message: `Are you sure you want to delete "${doc.source_name}"?`,
      onConfirm: () => onDeleteConfirmed(doc.source_id),
      loading: deleteLoading,
      confirmLabel: "Yes, Delete",
    },
  },
];

export const DocumentGrid = ({paginatedDocuments, activeDoc, setActiveDoc, deleteLoading, onDeleteConfirmed, retrying, handleRetry, footer}: DocumentGridProps) => {
  return (
    <>
      <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {paginatedDocuments.map((doc) => (
              <DataCard
                key={doc.pipeline_id}
                iconRenderer={() => getFileIcon(doc.type_data.file_type)}
                iconBgClass={fileByColors[doc.type_data.file_type]}
                title={doc.source_name}
                status={doc.status}
                subtitle={getDataToDisplay(doc) || `${doc.type_data.page_count} pages | ${doc.type_data.file_type} | ${doc.type_data.file_size}`}
                metadata={`Uploaded ${new Date(doc.created_at).toLocaleString("en-GB")} by ${doc.upload_by}`}
                footer={
                  doc.status === PIPELINE_STATUS.FAILED && doc.type_data?.last_error
                    ? <span className="text-red-400">{doc.type_data.last_error}</span>
                    : (getDataToDisplay(doc) || `${doc.pipeline_stats?.chunks_generated} chunks`)
                }
                selected={doc === activeDoc}
                onClick={() => setActiveDoc(doc === activeDoc ? null : doc)}
                // extraTopRight={getExtraTopRight(doc, handleRetry, retrying)}
                actions={getActions(doc, activeDoc, setActiveDoc, deleteLoading, onDeleteConfirmed)}
              />
            ))}
          </div>

          {footer && (
            <div className="mt-6 flex justify-between items-center">
              {footer}
            </div>
          )}
      </div>

      {activeDoc && (
        <div className="mt-6">
          <DocumentData doc={activeDoc} />
        </div>
      )}
    </>
  );
};
