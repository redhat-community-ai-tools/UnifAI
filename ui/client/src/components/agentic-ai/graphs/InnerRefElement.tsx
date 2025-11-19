
import React, { useState } from "react";
import { Eye } from "lucide-react";
import { getCategoryDisplay } from "@/components/shared/helpers";
import ResourceDetailsModal from "@/workspace/ResourceDetailsModal";
import { BuildingBlock } from "@/types/graph";

interface InnerRefElementProps {
  refId: string;
  refData: any;
  allBlocks: BuildingBlock[];
}

const InnerRefElement: React.FC<InnerRefElementProps> = ({
  refId,
  refData,
  allBlocks,
}) => {
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
  
  // Find the referenced element in all available blocks
  const referencedElement = allBlocks.find(block => 
    block.id === refId || block.workspaceData?.rid === refId
  );
  
  if (!referencedElement) {
    return null;
  }

  const categoryDisplay = getCategoryDisplay(referencedElement.workspaceData?.category || "default");

  const handleViewDetails = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsDetailsModalOpen(true);
  };

  return (
    <>
      <div className="bg-gray-700 border border-gray-600 rounded px-2 py-1 flex items-center gap-1 text-xs">
        <div className="w-4 h-4 flex items-center justify-center text-white">
          {categoryDisplay.icon}
        </div>
        <span className="text-gray-200 truncate max-w-16">
          {referencedElement.label}
        </span>
        <button
          onClick={handleViewDetails}
          className="w-3 h-3 text-gray-400 hover:text-white transition-colors"
        >
          <Eye className="w-3 h-3" />
        </button>
      </div>
      
      <ResourceDetailsModal
        isOpen={isDetailsModalOpen}
        onClose={() => setIsDetailsModalOpen(false)}
        element={referencedElement}
      />
    </>
  );
};

export default InnerRefElement;
