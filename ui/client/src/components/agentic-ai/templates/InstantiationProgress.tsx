import React, { useEffect, useState } from 'react';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle 
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  CheckCircle, 
  XCircle, 
  LoaderCircle, 
  ArrowRight,
  RefreshCw,
  FileText,
  Zap,
  MessageSquare,
  Eye
} from 'lucide-react';
import { InstantiationStatus, MaterializeResponse } from '@/types/templates';
import { ElementValidationResult } from '@/types/validation';
import { ValidationResultModal } from '../workspace/validation/ValidationResultModal';

interface InstantiationProgressProps {
  status: InstantiationStatus;
  result: MaterializeResponse | null;
  error?: string | null;
  validationResults?: ElementValidationResult[];
  onClose: () => void;
  onRetry: () => void;
  onNavigateToWorkflow: () => void;
  onNavigateToChat: () => Promise<void>;
  isCreatingSession?: boolean;
}

interface StepConfig {
  key: InstantiationStatus;
  label: string;
  icon: React.ReactNode;
}

const STEPS: StepConfig[] = [
  { key: 'validating', label: 'Validating inputs', icon: <FileText className="h-5 w-5" /> },
  { key: 'submitting', label: 'Creating blueprint', icon: <Zap className="h-5 w-5" /> },
];

const getStepIndex = (status: InstantiationStatus): number => {
  const index = STEPS.findIndex(s => s.key === status);
  if (status === 'completed') return STEPS.length;
  if (status === 'failed') return -1;
  return index;
};

const getProgressValue = (status: InstantiationStatus): number => {
  switch (status) {
    case 'idle': return 0;
    case 'validating': return 30;
    case 'submitting': return 70;
    case 'completed': return 100;
    case 'failed': return 0;
    default: return 0;
  }
};

export const InstantiationProgress: React.FC<InstantiationProgressProps> = ({
  status,
  result,
  error,
  validationResults = [],
  onClose,
  onRetry,
  onNavigateToWorkflow,
  onNavigateToChat,
  isCreatingSession = false
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isNavigatingToChat, setIsNavigatingToChat] = useState(false);
  const [selectedValidationResult, setSelectedValidationResult] = useState<ElementValidationResult | null>(null);
  const [lastActiveStepIndex, setLastActiveStepIndex] = useState(0);
  const currentStepIndex = status === 'failed' ? lastActiveStepIndex : getStepIndex(status);
  const progressValue = getProgressValue(status);

  useEffect(() => {
    if (status === 'validating' || status === 'submitting') {
      setLastActiveStepIndex(getStepIndex(status));
    }
  }, [status]);
  const handleOpenChat = async () => {
    setIsNavigatingToChat(true);
    try {
      await onNavigateToChat();
    } finally {
      setIsNavigatingToChat(false);
    }
  };

  useEffect(() => {
    if (status !== 'idle') {
      setIsOpen(true);
    }
  }, [status]);

  const handleClose = () => {
    setIsOpen(false);
    onClose();
  };

  const handleRetry = () => {
    setIsOpen(false);
    onRetry();
  };

  const handleViewDetails = (result: ElementValidationResult) => {
    setSelectedValidationResult(result);
  };

  const failedResults = validationResults.filter(r => !r.is_valid);
  const hasValidationErrors = failedResults.length > 0;
  const totalErrorCount = failedResults.reduce(
    (sum, r) => sum + r.messages.filter(m => m.severity === 'error').length,
    0
  );

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="bg-background-card border-gray-800 text-foreground max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-heading">
            {status === 'completed' 
              ? 'Workflow Created!' 
              : status === 'failed' 
                ? 'Creation Failed' 
                : 'Creating Workflow...'}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <Progress value={progressValue} className="h-2" />

          <div className="space-y-3">
            {STEPS.map((step, index) => {
              const isCompleted = currentStepIndex > index || status === 'completed';
              const isActive = currentStepIndex === index && status !== 'failed';
              const isFailed = status === 'failed' && currentStepIndex === index;

              return (
                <motion.div
                  key={step.key}
                  initial={{ opacity: 0.5 }}
                  animate={{ 
                    opacity: isCompleted || isActive ? 1 : 0.5 
                  }}
                  className={`flex items-center gap-3 p-3 rounded-lg border ${
                    isCompleted 
                      ? 'bg-green-500/10 border-green-500/30' 
                      : isActive 
                        ? 'bg-primary/10 border-primary/30' 
                        : isFailed
                          ? 'bg-red-500/10 border-red-500/30'
                          : 'bg-background-dark border-gray-800'
                  }`}
                >
                  <div className={`${
                    isCompleted 
                      ? 'text-green-500' 
                      : isActive 
                        ? 'text-primary' 
                        : isFailed
                          ? 'text-red-500'
                          : 'text-gray-500'
                  }`}>
                    {isCompleted ? (
                      <CheckCircle className="h-5 w-5" />
                    ) : isActive ? (
                      <LoaderCircle className="h-5 w-5 animate-spin" />
                    ) : isFailed ? (
                      <XCircle className="h-5 w-5" />
                    ) : (
                      step.icon
                    )}
                  </div>
                  <span className={`text-sm ${
                    isCompleted || isActive ? 'text-gray-200' : 'text-gray-500'
                  }`}>
                    {step.label}
                  </span>
                </motion.div>
              );
            })}
          </div>

          <AnimatePresence mode="wait">
            {status === 'completed' && result && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-4"
              >
                <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                  <div className="flex items-center gap-2 text-green-500 mb-2">
                    <CheckCircle className="h-5 w-5" />
                    <span className="font-medium">Success!</span>
                  </div>
                  <p className="text-sm text-gray-400">
                    Workflow "<span className="text-gray-200">{result.name}</span>" has been created and is ready to use.
                  </p>
                  {result.fields_filled > 0 && (
                    <div className="mt-2 text-xs text-gray-500">
                      Configured {result.fields_filled} field{result.fields_filled !== 1 ? 's' : ''}
                    </div>
                  )}
                  {result.resource_ids && result.resource_ids.length > 0 && (
                    <div className="mt-1 text-xs text-gray-500">
                      Created {result.resource_ids.length} resource{result.resource_ids.length !== 1 ? 's' : ''}
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  <Button 
                    onClick={onNavigateToWorkflow}
                    className="flex-1 bg-primary hover:bg-primary/90"
                    disabled={isNavigatingToChat || isCreatingSession}
                  >
                    View Workflow
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </Button>
                  <Button 
                    onClick={handleOpenChat}
                    variant="outline"
                    className="flex-1 border-gray-700"
                    disabled={isNavigatingToChat || isCreatingSession}
                  >
                    {isNavigatingToChat || isCreatingSession ? (
                      <>
                        <LoaderCircle className="h-4 w-4 mr-2 animate-spin" />
                        Creating Chat...
                      </>
                    ) : (
                      <>
                        Open Chat
                        <MessageSquare className="h-4 w-4 ml-2" />
                      </>
                    )}
                  </Button>
                </div>
              </motion.div>
            )}

            {status === 'failed' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-4"
              >
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <div className="flex items-center gap-2 text-red-500 mb-2">
                    <XCircle className="h-5 w-5" />
                    <span className="font-medium">Creation Failed</span>
                    {hasValidationErrors && (
                      <span className="text-xs text-red-400 ml-auto">
                        {totalErrorCount} error{totalErrorCount !== 1 ? 's' : ''} in {validationResults.length} element{validationResults.length !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-400 mb-3">
                    {error || 'An unexpected error occurred while creating the workflow.'}
                  </p>

                  {/* Element Errors List */}
                  {hasValidationErrors && (
                    <div className="mt-3 space-y-2 max-h-40 overflow-y-auto">
                      <p className="text-xs text-gray-500 font-medium mb-2">Failed Elements:</p>
                      {failedResults.map((result, idx) => (
                        <div 
                          key={result.element_rid || idx}
                          className="flex items-center justify-between p-2 bg-gray-900/50 rounded border border-gray-800 hover:border-red-500/30 transition-colors"
                        >
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <XCircle className="h-4 w-4 text-red-500 shrink-0" />
                            <div className="min-w-0">
                              <p className="text-sm text-gray-200 truncate">
                                {result.name || result.element_rid}
                              </p>
                              <p className="text-xs text-gray-500">
                              {result.element_type} • {result.messages.filter(m => m.severity === 'error').length} error{result.messages.filter(m => m.severity === 'error').length !== 1 ? 's' : ''}
                              </p>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleViewDetails(result)}
                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10 h-7 px-2 shrink-0"
                          >
                            <Eye className="h-3 w-3 mr-1" />
                            Details
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  <Button 
                    onClick={handleRetry}
                    className="flex-1 bg-primary hover:bg-primary/90"
                  >
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Reset & Retry
                  </Button>
                  <Button 
                    onClick={handleClose}
                    variant="outline"
                    className="flex-1 border-gray-700"
                  >
                    Close
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </DialogContent>

      <ValidationResultModal
        validationResult={selectedValidationResult}
        isOpen={!!selectedValidationResult}
        onOpenChange={(open) => !open && setSelectedValidationResult(null)}
        showRefreshButton={false}
      />
    </Dialog>
  );
};

export default InstantiationProgress;