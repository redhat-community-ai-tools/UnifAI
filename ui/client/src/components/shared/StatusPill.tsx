import React from "react";
import { cn } from "@/lib/utils";
import { STATUS_TONE_CLASSES, StatusTone } from "@/lib/statusTones";

interface StatusPillProps {
  tone: StatusTone;
  children: React.ReactNode;
  className?: string;
}

/**
 * Generic status badge. Owns the shared markup/sizing; callers pick a
 * semantic `tone` (see `lib/statusTones`) rather than passing raw colors,
 * so every status pill in the app stays visually consistent.
 */
export default function StatusPill({ tone, children, className }: StatusPillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border",
        STATUS_TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
