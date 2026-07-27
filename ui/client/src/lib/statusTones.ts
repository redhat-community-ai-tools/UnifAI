/**
 * Shared semantic color palette for status pills across the app.
 *
 * Single source of truth for what "success"/"warning"/etc. looks like.
 * Feature code should map domain-specific status values to one of
 * these tones (e.g. a "completed" schedule vs. a "completed" run may map to
 * different tones) and render via `StatusPill`.
 */
export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

export const STATUS_TONE_CLASSES: Record<StatusTone, string> = {
  success: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  warning: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  danger: "bg-red-500/15 text-red-400 border-red-500/30",
  info: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  neutral: "bg-gray-500/15 text-gray-400 border-gray-500/30",
};
