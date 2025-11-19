import { cn } from "@/lib/utils";
import { HTMLAttributes } from "react";

type Props = HTMLAttributes<HTMLDivElement> & {
  strong?: boolean;
};

export default function GlassPanel({ strong, className, children, ...rest }: Props) {
  return (
    <div
      {...rest}
      className={cn(
        strong ? "overlay-12" : "overlay-08",
        "relative overflow-hidden rounded-2xl p-5 sm:p-6 isolation-isolate bg-card text-card-foreground shadow-sm overlay-elevation",
        className
      )}
    >
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}


