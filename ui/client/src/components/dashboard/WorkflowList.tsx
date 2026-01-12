import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { FaProjectDiagram } from "react-icons/fa";
import { WorkflowCard } from "./WorkflowCard";
import { WorkflowBlueprint } from "@/api/blueprints";

interface WorkflowListProps {
  title: string;
  workflows: (WorkflowBlueprint & { usageCount?: number })[];
  isLoading: boolean;
  onWorkflowClick: (workflow: WorkflowBlueprint) => void;
  emptyMessage: string;
  showUsageCount?: boolean;
  maxItems?: number;
  countBadge?: number;
}

export function WorkflowList({
  title,
  workflows,
  isLoading,
  onWorkflowClick,
  emptyMessage,
  showUsageCount = false,
  maxItems,
  countBadge,
}: WorkflowListProps) {
  const displayWorkflows = maxItems ? workflows.slice(0, maxItems) : workflows;

  return (
    <Card className="shadow-card border-gray-800 bg-transparent border-0 flex flex-col h-full">
      <CardHeader className="py-4 px-6 flex-shrink-0">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xl flex items-center gap-2">
            <FaProjectDiagram className="text-primary" />
            {title}
          </CardTitle>
          {countBadge !== undefined && (
            <span className="text-sm text-gray-400">{countBadge}</span>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col min-h-0 px-6 pb-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : displayWorkflows.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            {emptyMessage}
          </div>
        ) : (
          <div className="space-y-3 pr-2">
            {displayWorkflows.map((workflow, idx) => (
              <WorkflowCard
                key={workflow.blueprint_id}
                workflow={workflow}
                index={idx}
                onClick={() => onWorkflowClick(workflow)}
                showUsageCount={showUsageCount}
                animationDelay={showUsageCount ? 0.1 : 0.05}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}