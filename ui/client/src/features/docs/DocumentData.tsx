import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getFileIcon } from "../helpers";
import { Document } from "@/types";
import { Loader2 } from "lucide-react";

interface LibraryTabProps {
  doc: Document;
  details?: Document | null;
  isLoading?: boolean;
}

// the commented out fields are placeholders for future enhancements
export const DocumentData: React.FC<LibraryTabProps> = ({ doc, details, isLoading }) => {
  // Use details if available, otherwise fall back to doc for basic info
  const displayDoc = details || doc;

  const metadata = [
    { label: "Title", value: displayDoc.source_name },
    // { label: "Author", value: "Product Management Team" },
    { label: "Created", value: new Date(displayDoc.created_at).toLocaleDateString() },
    { label: "Modified", value: displayDoc.created_at ? new Date(displayDoc.created_at).toLocaleDateString() : "—" },
    { label: "File Size", value: displayDoc.type_data?.file_size },
    { label: "Pages", value: displayDoc.type_data?.page_count },
    { label: "Uploaded", value: new Date(displayDoc.created_at).toLocaleDateString() },
    { label: "Processed", value: displayDoc.created_at ? new Date(displayDoc.created_at).toLocaleDateString() : "—" },
  ];

  const statistics = [
    // { label: "Text Quality", value: "Excellent", progress: 95, color: "bg-success" },
    // { label: "Structure Preservation", value: "Good", progress: 85, color: "bg-primary" },
    { label: "Total Chunks", value: displayDoc.pipeline_stats?.chunks_generated },
    // { label: "Total Tokens", value: doc.stats?.total_tokens || "—" },
    // { label: "Avg. Chunk Size", value: doc.stats?.avg_chunk_size || "—" },
    // { label: "Images Extracted", value: doc.stats?.images_extracted || "—" },
    // { label: "Tables Extracted", value: doc.stats?.tables_extracted || "—" },
    { label: "Embeddings Created", value: displayDoc.pipeline_stats?.embeddings_created ?? "—" },
    { label: "API Calls", value: displayDoc.pipeline_stats?.api_calls ?? "—" },
    { label: "Processing Time (s)", value: displayDoc.pipeline_stats?.processing_time?.toFixed(2) ?? "—" },
  ];

  // Get full text from details (lazy loaded) or fall back to doc
  const fullText = details?.type_data?.full_text || doc.type_data?.full_text;

  return (
    <div className="grid grid-cols-1 gap-6">
      <Card className="bg-background-card shadow-card border-gray-800">
        <CardContent className="p-6">
          <h3 className="text-lg font-heading font-semibold mb-4">Document Details</h3>
          <div className="lg:flex gap-6 h-[500px]">

            {/* Left side: document content */}
            <div className="flex-1 flex flex-col">
              <div className="bg-background-dark rounded-lg border border-gray-800 overflow-hidden flex flex-col flex-1">
                <div className="p-4 bg-background-surface border-b border-gray-800">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      {getFileIcon(displayDoc.type_data?.file_type)}
                      <span className="ml-2 font-medium truncate">{displayDoc.source_name}</span>
                    </div>
                    {/* <Button variant="ghost" size="sm">
                      <FaEye className="mr-2 h-4 w-4" />
                      <span>View Original</span>
                    </Button> */}
                  </div>
                </div>
                <div
                  className="p-4 overflow-y-auto font-mono text-xs whitespace-pre-line max-w-[50vw] break-words flex-1"
                  style={{ wordBreak: "break-word" }}
                >
                  {isLoading ? (
                    <div className="flex items-center justify-center h-full">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                      <span className="ml-2 text-gray-400">Loading document content...</span>
                    </div>
                  ) : fullText ? (
                    <p>{fullText}</p>
                  ) : (
                    <p className="text-gray-400 italic">No extracted text available.</p>
                  )}
                </div>
              </div>
            </div>


            {/* Right side: metadata and stats */}
            <div className="flex-1 flex flex-col overflow-y-auto">
              <div className="bg-background-dark p-4 rounded-lg border border-gray-800 flex-1">
                <h4 className="font-medium mb-3">Document Metadata</h4>
                <div className="space-y-3">
                  {metadata.map(({ label, value }) => (
                    <div className="flex justify-between" key={label}>
                      <span className="text-sm text-gray-400">{label}:</span>
                      <span className="text-sm">{value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {displayDoc.tags && displayDoc.tags.length > 0 && (
                <div className="mt-4 bg-background-dark p-4 rounded-lg border border-gray-800">
                  <h4 className="font-medium mb-3">Tags</h4>
                  <div className="flex flex-wrap gap-2 max-h-24 overflow-y-auto">
                    {displayDoc.tags.map((tag) => (
                      <Badge key={tag} variant="secondary">{tag}</Badge>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-4 bg-background-dark p-4 rounded-lg border border-gray-800">
                <h4 className="font-medium mb-3">Extraction Statistics</h4>
                <div className="space-y-3">
                  {statistics.map(({ label, value }) => (
                    <div className="flex justify-between" key={label}>
                      <span className="text-sm text-gray-400">{label}:</span>
                      <span className="text-sm">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
