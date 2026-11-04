import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Info,
  GitBranch,
  Link,
  RotateCcw,
  Trash2,
  Users
} from "lucide-react";

interface ValidationMessage {
  text: string;
  severity: "error" | "warning" | "info";
  code: string;
  context: any;
}

interface ValidationReport {
  validator_name: string;
  is_valid: boolean;
  messages: ValidationMessage[];
  details: any;
}

interface FixSuggestion {
  text: string;
  fix_type: "ADD_NODE" | "REMOVE_NODE" | "MODIFY_CONNECTION" | "ADD_CHANNEL";
  code: string;
  context: any;
  priority: number;
}

interface ValidationResult {
  is_valid: boolean;
  reports: ValidationReport[];
}

interface GraphValidationPanelProps {
  validationResult: ValidationResult | null;
  fixSuggestions: FixSuggestion[];
  isValidating: boolean;
  isLoadingBlueprint?: boolean;
}

const getValidatorIcon = (validatorName: string) => {
  switch (validatorName) {
    case "channel":
      return <GitBranch className="h-4 w-4" />;
    case "dependency":
      return <Link className="h-4 w-4" />;
    case "cycle":
      return <RotateCcw className="h-4 w-4" />;
    case "orphan":
      return <Trash2 className="h-4 w-4" />;
    case "requirednodes":
      return <Users className="h-4 w-4" />;
    default:
      return <Info className="h-4 w-4" />;
  }
};

const getValidatorDisplayName = (validatorName: string) => {
  switch (validatorName) {
    case "channel":
      return "Channel Validation";
    case "dependency":
      return "Dependency Validation";
    case "cycle":
      return "Cycle Validation";
    case "orphan":
      return "Orphan Validation";
    case "requirednodes":
      return "Required Nodes Validation";
    default:
      return validatorName;
  }
};

const getSeverityIcon = (severity: string) => {
  switch (severity) {
    case "error":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case "info":
      return <Info className="h-4 w-4 text-blue-500" />;
    default:
      return <Info className="h-4 w-4 text-gray-500" />;
  }
};

const getPriorityBadge = (priority: number) => {
  if (priority >= 4) {
    return <Badge variant="destructive" className="text-xs">Critical</Badge>;
  } else if (priority >= 2) {
    return <Badge variant="outline" className="text-xs border-yellow-500 text-yellow-600">Medium</Badge>;
  } else {
    return <Badge variant="secondary" className="text-xs">Low</Badge>;
  }
};

const GraphValidationPanel: React.FC<GraphValidationPanelProps> = ({
  validationResult,
  fixSuggestions,
  isValidating,
  isLoadingBlueprint = false,
}) => {
  if (isLoadingBlueprint) {
    return (
      <Card className="bg-background-card border-gray-800">
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
            Loading Workflow...
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <p className="text-sm text-gray-500">
            Validation will run once the workflow is loaded.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (isValidating) {
    return (
      <Card className="bg-background-card border-gray-800">
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
            Validating Workflow...
          </CardTitle>
        </CardHeader>
      </Card>
    );
  }

  if (!validationResult) {
    return (
      <Card className="bg-background-card border-gray-800">
        <CardHeader className="py-3">
          <CardTitle className="text-sm text-gray-400">Workflow Validation</CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <p className="text-sm text-gray-500">
            Add nodes and connections to see validation status.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Sort fix suggestions by priority (highest first)
  const sortedSuggestions = [...fixSuggestions].sort((a, b) => b.priority - a.priority);

  return (
    <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col">
      <CardHeader className="py-2 px-4 border-b border-gray-800">
        <CardTitle className="text-base font-heading flex items-center gap-2">
          {validationResult.is_valid ? (
            <CheckCircle className="h-4 w-4 text-green-500" />
          ) : (
            <XCircle className="h-4 w-4 text-red-500" />
          )}
          Workflow Validation
          <Badge 
            variant={validationResult.is_valid ? "default" : "destructive"}
            className="text-xs"
          >
            {validationResult.is_valid ? "Valid" : "Invalid"}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3 flex-1 overflow-hidden flex flex-col">
        {/* Validation Reports - Fixed height section */}
        <div className="space-y-3 flex-shrink-0">
          <h4 className="text-xs font-medium text-gray-300 uppercase tracking-wide">
            Validation Reports
          </h4>
          {validationResult.reports.map((report, index) => (
            <div key={index} className="flex items-center justify-between p-2 rounded-lg bg-gray-800">
              <div className="flex items-center gap-2">
                {getValidatorIcon(report.validator_name)}
                <span className="text-sm text-gray-300">
                  {getValidatorDisplayName(report.validator_name)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {report.is_valid ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-500" />
                )}
                {report.messages.length > 0 && (
                  <Badge variant="outline" className="text-xs">
                    {report.messages.length} issues
                  </Badge>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Scrollable sections container - Takes remaining space */}
        {(validationResult.reports.some(r => r.messages.length > 0) || sortedSuggestions.length > 0) && (
          <div className="flex-1 flex flex-col mt-6 min-h-0 space-y-3">
            {/* Issues Found Section - Always takes 50% of remaining space if both sections exist */}
            {validationResult.reports.some(r => r.messages.length > 0) && (
              <div className={`flex flex-col space-y-2 min-h-0 ${sortedSuggestions.length > 0 ? 'flex-1' : 'flex-[2]'}`}>
                <h4 className="text-xs font-medium text-gray-300 uppercase tracking-wide flex-shrink-0">
                  Issues Found
                </h4>
                <div className="flex-1 space-y-2 overflow-y-auto min-h-0 pr-1">
                  {validationResult.reports.map((report) =>
                    report.messages.map((message, msgIndex) => (
                      <Alert key={`${report.validator_name}-${msgIndex}`} className="p-2 bg-gray-800 border-gray-700 flex-shrink-0">
                        <div className="flex items-start gap-2">
                          {getSeverityIcon(message.severity)}
                          <div className="flex-1">
                            <AlertDescription className="text-xs text-gray-300">
                              <span className="font-medium text-gray-200">
                                [{getValidatorDisplayName(report.validator_name)}]
                              </span>{" "}
                              {message.text}
                            </AlertDescription>
                          </div>
                        </div>
                      </Alert>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Fix Suggestions Section - Always takes 50% of remaining space if both sections exist */}
            {sortedSuggestions.length > 0 && (
              <div className={`flex flex-col space-y-2 min-h-0 ${validationResult.reports.some(r => r.messages.length > 0) ? 'flex-1' : 'flex-[2]'}`}>
                <h4 className="text-xs font-medium text-gray-300 uppercase tracking-wide flex-shrink-0">
                  Fix Suggestions
                </h4>
                <div className="flex-1 space-y-2 overflow-y-auto min-h-0 pr-1">
                  {sortedSuggestions.map((suggestion, index) => (
                    <div key={index} className="p-3 rounded-lg bg-gray-800 border border-gray-700 flex-shrink-0">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        {getPriorityBadge(suggestion.priority)}
                        <Badge variant="outline" className="text-xs">
                          {suggestion.fix_type.replace(/_/g, " ").toLowerCase()}
                        </Badge>
                      </div>
                      <p className="text-xs text-gray-300 leading-relaxed">
                        {suggestion.text}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default GraphValidationPanel;