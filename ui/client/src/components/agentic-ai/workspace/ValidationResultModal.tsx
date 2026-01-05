/**
 * ValidationResultModal Component
 * 
 * This modal displays the validation status of building blocks (resources) in the Agentic AI system.
 * It provides users with clear feedback on whether a resource is VALID or INVALID, along with
 * detailed messages indicating what needs to be fixed to make it valid.
 * 
 * Key features:
 * - Shows overall validation status (Valid/Invalid) with visual indicators
 * - Displays validation messages categorized by severity (error, warning, info)
 * - Renders dependency validation results in a hierarchical tree structure
 * - Provides a refresh button to re-validate the resource and its ancestors
 * - Shows element type, RID, and human-readable name for context
 * 
 * Used by:
 * - ReactFlowGraph nodes to show validation details when clicking on validation indicators
 * - Workspace components to display resource validation status
 * - Any component that needs to present detailed validation feedback to users
 */

import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Info,
  ChevronDown,
  ChevronRight,
  Server,
  RefreshCw
} from 'lucide-react';
import { ElementValidationResult, ValidationMessage, ValidationSeverity } from '@/types/validation';
import { useAgenticAI } from '@/contexts/AgenticAIContext';
import { useState } from 'react';

interface ValidationResultModalProps {
  validationResult: ElementValidationResult | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  showRefreshButton?: boolean;
}

// Severity icon and color mapping
const getSeverityConfig = (severity: ValidationSeverity) => {
  switch (severity) {
    case 'error':
      return {
        icon: XCircle,
        bgColor: 'bg-red-500/10',
        textColor: 'text-red-500',
        borderColor: 'border-red-500/30',
        label: 'Error',
      };
    case 'warning':
      return {
        icon: AlertTriangle,
        bgColor: 'bg-yellow-500/10',
        textColor: 'text-yellow-500',
        borderColor: 'border-yellow-500/30',
        label: 'Warning',
      };
    case 'info':
    default:
      return {
        icon: Info,
        bgColor: 'bg-blue-500/10',
        textColor: 'text-blue-500',
        borderColor: 'border-blue-500/30',
        label: 'Info',
      };
  }
};

// Single validation message component
const ValidationMessageItem: React.FC<{ message: ValidationMessage }> = ({ message }) => {
  const config = getSeverityConfig(message.severity);
  const Icon = config.icon;

  return (
    <div className={`flex items-start gap-3 p-3 rounded-md ${config.bgColor} border ${config.borderColor}`}>
      <Icon className={`h-5 w-5 ${config.textColor} flex-shrink-0 mt-0.5`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className={`text-xs ${config.textColor} border-current`}>
            {message.code}
          </Badge>
          {message.field && (
            <Badge variant="outline" className="text-xs text-gray-400">
              field: {message.field}
            </Badge>
          )}
        </div>
        <p className="text-sm text-gray-300 mt-1">{message.message}</p>
      </div>
    </div>
  );
};

// Dependency result component (recursive)
const DependencyResultItem: React.FC<{ 
  result: ElementValidationResult;
  depth?: number;
}> = ({ result, depth = 0 }) => {
  const [isExpanded, setIsExpanded] = useState(depth === 0);
  const { getResourceName } = useAgenticAI();
  const hasDependencies = Object.keys(result.dependency_results).length > 0;
  
  const displayName = result.name || getResourceName(result.element_rid) || result.element_rid;

  return (
    <div className={`${depth > 0 ? 'ml-4 border-l border-gray-700 pl-4' : ''}`}>
      <div 
        className={`flex items-center gap-2 py-2 ${hasDependencies ? 'cursor-pointer hover:bg-gray-800/50 rounded-md px-2 -mx-2' : ''}`}
        onClick={() => hasDependencies && setIsExpanded(!isExpanded)}
      >
        {hasDependencies ? (
          isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-500" />
          )
        ) : (
          <div className="w-4" />
        )}
        
        {result.is_valid ? (
          <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
        ) : (
          <XCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
        )}
        
        <Server className="h-4 w-4 text-gray-500" />
        
        <span className="text-sm font-medium text-gray-200 truncate">
          {displayName}
        </span>
        
        <Badge variant="outline" className="text-xs text-gray-400">
          {result.element_type}
        </Badge>
      </div>

      {isExpanded && (
        <div className="mt-2 space-y-2">
          {/* Messages for this dependency */}
          {result.messages.length > 0 && (
            <div className="space-y-2 ml-6">
              {result.messages.map((message, idx) => (
                <ValidationMessageItem key={idx} message={message} />
              ))}
            </div>
          )}

          {/* Nested dependencies */}
          {hasDependencies && (
            <div className="mt-3">
              {Object.entries(result.dependency_results).map(([rid, depResult]) => (
                <DependencyResultItem key={rid} result={depResult} depth={depth + 1} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const ValidationResultModal: React.FC<ValidationResultModalProps> = ({
  validationResult,
  isOpen,
  onOpenChange,
  showRefreshButton = true,
}) => {
  const { getResourceName, revalidateResourceAndAncestors } = useAgenticAI();

  if (!validationResult) return null;

  const displayName = validationResult.name || 
    getResourceName(validationResult.element_rid) || 
    validationResult.element_rid;

  const hasDependencies = Object.keys(validationResult.dependency_results).length > 0;

  // Count messages by severity
  const errorCount = validationResult.messages.filter(m => m.severity === 'error').length;
  const warningCount = validationResult.messages.filter(m => m.severity === 'warning').length;
  const infoCount = validationResult.messages.filter(m => m.severity === 'info').length;

  // Handle refresh validation
  const handleRefreshValidation = () => {
    revalidateResourceAndAncestors(validationResult.element_rid);
    onOpenChange(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="bg-background-card border-gray-800 text-foreground max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            {validationResult.is_valid ? (
              <CheckCircle2 className="h-6 w-6 text-green-500" />
            ) : (
              <XCircle className="h-6 w-6 text-red-500" />
            )}
            <span>Validation Result: {displayName}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Summary Section */}
          <div className="flex items-center gap-4 p-4 rounded-lg bg-gray-900/50 border border-gray-800">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium text-gray-400">Status:</span>
                {validationResult.is_valid ? (
                  <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                    Valid
                  </Badge>
                ) : (
                  <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                    Invalid
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span>Type: {validationResult.element_type}</span>
                <span>•</span>
                <span className="font-mono">{validationResult.element_rid.slice(0, 12)}...</span>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex gap-3">
                {errorCount > 0 && (
                  <div className="flex items-center gap-1">
                    <XCircle className="h-4 w-4 text-red-500" />
                    <span className="text-sm text-red-400">{errorCount}</span>
                  </div>
                )}
                {warningCount > 0 && (
                  <div className="flex items-center gap-1">
                    <AlertTriangle className="h-4 w-4 text-yellow-500" />
                    <span className="text-sm text-yellow-400">{warningCount}</span>
                  </div>
                )}
                {infoCount > 0 && (
                  <div className="flex items-center gap-1">
                    <Info className="h-4 w-4 text-blue-500" />
                    <span className="text-sm text-blue-400">{infoCount}</span>
                  </div>
                )}
              </div>
              
              {showRefreshButton && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRefreshValidation}
                  className="h-8 px-3 hover:bg-gray-700 border-gray-700"
                  title="Re-validate resource"
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              )}
            </div>
          </div>

          {/* Messages Section */}
          {validationResult.messages.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-3">Messages</h3>
              <div className="space-y-2">
                {validationResult.messages.map((message, idx) => (
                  <ValidationMessageItem key={idx} message={message} />
                ))}
              </div>
            </div>
          )}

          {/* Dependencies Section */}
          {hasDependencies && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-3">
                Dependencies ({Object.keys(validationResult.dependency_results).length})
              </h3>
              <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/30">
                <div className="space-y-1">
                  {Object.entries(validationResult.dependency_results).map(([rid, depResult]) => (
                    <DependencyResultItem key={rid} result={depResult} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Empty state for no messages */}
          {validationResult.messages.length === 0 && !hasDependencies && (
            <div className="text-center py-8 text-gray-500">
              <CheckCircle2 className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No validation messages or dependencies to display.</p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};



