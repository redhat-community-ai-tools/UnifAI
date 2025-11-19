import { FaFileAlt, FaFileWord, FaFilePdf, FaFileExcel, FaFilePowerpoint, FaMarkdown, FaHtml5, FaFileCsv } from "react-icons/fa";
import { PIPELINE_STATUS, PipelineStatus } from "@/constants/pipelineStatus";
import { EmbedChannel, Document } from "@/types";
import { InlineLoader } from "@/components/shared/InlineLoader";

export const getFileIcon = (type: string) => {
    switch (type) {
      case 'pdf':
        return <FaFilePdf />;
      case 'docx':
        return <FaFileWord />;
      case 'xlsx':
        return <FaFileExcel />;
      case 'pptx':
        return <FaFilePowerpoint />;
      case 'md':
        return <FaMarkdown />;
      case "html": 
      return <FaHtml5 />;
    case "csv":
      return <FaFileCsv />;
      default:
        return <FaFileAlt />;
    }
  };

export const fileByColors: Record<string, string> = {
  pdf: "bg-red-500 dark:bg-red-600",
  docx: "bg-blue-500 dark:bg-blue-600",
  pptx: "bg-orange-500 dark:bg-orange-600",
  xlsx: "bg-green-500 dark:bg-green-600",
  txt: "bg-gray-500 dark:bg-gray-600",
  md: "bg-slate-500 dark:bg-slate-600",
  html: "bg-pink-500 dark:bg-pink-600",
  csv: "bg-teal-500 dark:bg-teal-600"
};

export function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });
}

// Helper function to check if a pipeline is actively processing
export function isEmbeddingActivelyProcessing(source: EmbedChannel | Document): boolean {
  const activeStatuses = [
    PIPELINE_STATUS.PENDING,
    PIPELINE_STATUS.ACTIVE,
    PIPELINE_STATUS.COLLECTING,
    PIPELINE_STATUS.PROCESSING,
    PIPELINE_STATUS.CHUNKING_AND_EMBEDDING,
    PIPELINE_STATUS.STORING,
    PIPELINE_STATUS.ORCHESTRATING,
  ];
  
  return activeStatuses.includes(source.status as any);
}

export const getDataToDisplay = (doc: Document) => {
  if (isEmbeddingActivelyProcessing(doc)) return <InlineLoader />;
  if (!doc.status || doc.status === PIPELINE_STATUS.PENDING || doc.status === PIPELINE_STATUS.FAILED) return "-";
  return null;
};