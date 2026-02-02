import React from "react";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

interface SimpleTooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  delayDuration?: number;
  skipProvider?: boolean;
}

export default function SimpleTooltip({content, children, delayDuration = 300, skipProvider = false}: SimpleTooltipProps) {

  if (!content) {
    return <>{children}</>;
  }

  const tooltip = (
    <Tooltip>
      <TooltipTrigger asChild>
        {children}
      </TooltipTrigger>
      <TooltipContent 
        className="z-[9999] max-w-xs"
        side="top"
        align="start"
      >
        {content}
      </TooltipContent>
    </Tooltip>
  );

  if (skipProvider) {
    return (
      <TooltipProvider delayDuration={delayDuration}>
        {tooltip}
      </TooltipProvider>
    );
  }

  return tooltip;
}