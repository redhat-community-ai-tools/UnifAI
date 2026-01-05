import { cn } from "@/lib/utils";
import { EmbedChannel, Document } from "@/types";
import { useMemo } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function StatusBadge({ 
  status,
  errorMessage,
}: { 
  status: EmbedChannel["status"] | Document["status"] | undefined;
  errorMessage?: string;
}) {
  const { bgColor, textColor, label, isActive } = useMemo(() => {
    // Show "Pending" if there's no real pipeline status yet, even if actively embedding
    if (!status) {
      return {
        bgColor: "bg-grey-500/15",
        textColor: "text-grey-400",
        label: "Pending",
        isActive: true,
      };
    }

    switch (status) {
      case "ACTIVE":
        return {
          bgColor: "bg-emerald-500/15",
          textColor: "text-emerald-400",
          label: "In Progress",
          isActive: true,
        };
      case "PAUSED":
        return {
          bgColor: "bg-amber-500/15",
          textColor: "text-amber-400",
          label: "Paused",
          isActive: false,
        };
      case "DONE":
        return {
          bgColor: "bg-[hsl(var(--success))]/15",
          textColor: "text-[hsl(var(--success))]",
          label: "Done",
          isActive: false,
        };
      case "FAILED":
        return {
          bgColor: "bg-red-500/15",
          textColor: "text-red-400",
          label: "Failed",
          isActive: false,
        };
      case "ARCHIVED":
        return {
          bgColor: "bg-slate-600/10",
          textColor: "text-slate-400",
          label: "Archived",
          isActive: false,
        };
      case "PENDING":
        return {
          bgColor: "bg-blue-500/15",
          textColor: "text-blue-400",
          label: "Pending",
          isActive: true,
        };
      // Handle all the processing statuses as active states
      case "CHUNKING_AND_EMBEDDING":
        return {
          bgColor: "bg-blue-500/15",
          textColor: "text-blue-400",
          label: "Chunking & Embedding",
          isActive: true,
        };
      case "STORING":
        return {
          bgColor: "bg-purple-500/15",
          textColor: "text-purple-400",
          label: "Storing",
          isActive: true,
        };
      case "COLLECTING":
        return {
          bgColor: "bg-cyan-500/15",
          textColor: "text-cyan-400",
          label: "Collecting",
          isActive: true,
        };
      case "PROCESSING":
        return {
          bgColor: "bg-indigo-500/15",
          textColor: "text-indigo-400",
          label: "Processing",
          isActive: true,
        };
      case "ORCHESTRATING":
        return {
          bgColor: "bg-pink-500/15",
          textColor: "text-pink-400",
          label: "Orchestrating",
          isActive: true,
        };
      default:
        // If actively embedding but no status, show pending
        if (!status) {
          return {
            bgColor: "bg-blue-500/15",
            textColor: "text-blue-400",
            label: "Pending",
            isActive: true,
          };
        }
        // For any other status, show it as-is or default to Pending
        return {
          bgColor: "bg-blue-500/15",
          textColor: "text-blue-400",
          label: status || "Pending",
          isActive: true,
        };
    }
  }, [status]);

  const badge = (
    <span
      className={cn(
        "inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border",
        bgColor,
        textColor,
        isActive && "animate-pulse-glow border-emerald-400/30",
        !isActive && "border-current/20",
        status === "FAILED" && errorMessage && "cursor-help",
      )}
    >
      <span
        className={cn(
          "w-2 h-2 rounded-full mr-2",
          isActive ? "bg-emerald-400 animate-pulse" : "bg-current",
        )}
      ></span>
      {label}
    </span>
  );

  // Show tooltip with error message for failed status
  if (status === "FAILED" && errorMessage) {
    return (
      <TooltipProvider>
        <Tooltip delayDuration={200}>
          <TooltipTrigger asChild>
            {badge}
          </TooltipTrigger>
          <TooltipContent 
            side="top" 
            className="max-w-xs bg-red-950 border-red-800 text-red-200"
          >
            <p className="text-xs">{errorMessage}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return badge;
}