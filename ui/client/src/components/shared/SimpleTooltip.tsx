import React from "react";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

type TooltipContentPositionProps = Pick<
  React.ComponentPropsWithoutRef<typeof TooltipContent>,
  "side" | "align" | "sideOffset" | "collisionPadding"
>;

interface SimpleTooltipProps extends TooltipContentPositionProps {
  content: React.ReactNode;
  children: React.ReactNode;
  delayDuration?: number;
  skipProvider?: boolean;
}

export default function SimpleTooltip({
  content,
  children,
  delayDuration = 300,
  skipProvider = false,
  side = "top",
  align = "start",
  sideOffset = 4,
  collisionPadding = 8,
}: SimpleTooltipProps) {

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
        side={side}
        align={align}
        sideOffset={sideOffset}
        collisionPadding={collisionPadding}
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