import { Card } from "@/components/ui/card";
import { FaExclamationCircle } from "react-icons/fa";

interface ErrorDisplayProps {
  errorMessage: string;
  onRetry: () => void;
}

export function ErrorDisplay({ errorMessage, onRetry }: ErrorDisplayProps) {
  return (
    <div className="p-6 flex items-center justify-center h-full">
      <Card className="bg-background-card shadow-card border-gray-800 p-6 max-w-md">
        <div className="text-center">
          <FaExclamationCircle className="text-4xl text-error mx-auto mb-4" />
          <h3 className="text-lg font-heading font-semibold mb-2">Failed to Load Analytics</h3>
          <p className="text-sm text-gray-400 mb-4">{errorMessage}</p>
          <button 
            onClick={onRetry} 
            className="px-4 py-2 bg-primary hover:bg-opacity-80 rounded-md text-sm font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      </Card>
    </div>
  );
}

