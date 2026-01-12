import { motion } from "framer-motion";
import { FaChevronRight } from "react-icons/fa";
import { Workflow } from "lucide-react";
import { WorkflowBlueprint } from "@/api/blueprints";

interface WorkflowCardProps {
  workflow: WorkflowBlueprint & { usageCount?: number };
  index: number;
  onClick: () => void;
  showUsageCount?: boolean;
  animationDelay?: number;
}

export function WorkflowCard({
  workflow,
  index,
  onClick,
  showUsageCount = false,
  animationDelay = 0.1,
}: WorkflowCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * animationDelay }}
      onClick={onClick}
      className="p-3 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-primary/50 transition-colors cursor-pointer group flex-shrink-0"
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      aria-label={`Workflow: ${workflow.spec_dict?.name || workflow.blueprint_id}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-primary/20 text-primary flex items-center justify-center shrink-0">
            <Workflow className="w-4 h-4" />
          </div>
          <div className="min-w-0 flex-1 overflow-hidden">
            <p className="text-sm font-medium text-white truncate">
              {workflow.spec_dict?.name || workflow.blueprint_id}
            </p>
            <p className="text-xs text-gray-400 truncate">
              {workflow.blueprint_id}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {showUsageCount && workflow.usageCount !== undefined && (
            <span className="text-xs text-gray-400">{workflow.usageCount}x</span>
          )}
          <FaChevronRight className="w-4 h-4 text-gray-500 group-hover:text-primary transition-colors" />
        </div>
      </div>
    </motion.div>
  );
}