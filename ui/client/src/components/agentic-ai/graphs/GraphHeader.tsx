import React from 'react';
import { CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Trash2, Save, ArrowLeft } from 'lucide-react';

interface GraphHeaderProps {
  onClearGraph: () => void;
  onSaveGraph: () => void;
  onBack?: () => void;
  isGraphValid?: boolean;
}

const GraphHeader: React.FC<GraphHeaderProps> = ({
  onClearGraph,
  onSaveGraph,
  onBack,
  isGraphValid = false,
}) => {
  return (
    <CardHeader className="py-3 px-6 border-b border-gray-800">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          {onBack && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onBack}
              className="flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Button>
          )}
          <CardTitle className="text-lg font-heading">Workflow Canvas</CardTitle>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onClearGraph}
            className="flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            Clear
          </Button>
          <Button
              onClick={onSaveGraph}
              disabled={!isGraphValid}
              className="bg-primary hover:bg-primary/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save className="h-4 w-4 mr-2" />
              Save Workflow
            </Button>
        </div>
      </div>
    </CardHeader>
  );
};

export default GraphHeader;