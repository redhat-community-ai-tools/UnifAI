import { formatDateTime, formatRelativeTime } from "./dateTimeUtils";

/**
 * Format numbers with K suffix for large numbers
 */
export function formatNumber(num: number | string): string {
  const n = typeof num === "string" ? parseFloat(num) : num;
  if (!isNaN(n) && n >= 1000) {
    return (n / 1000).toFixed(1) + 'K';
  }
  return !isNaN(n) ? n.toLocaleString() : String(num);
};

/**
 * Get relative time string (e.g., "2h ago", "just now")
 */
export function getLastSyncTime(lastSyncAt?: string): string {
  if (!lastSyncAt) return "Never";
  return formatRelativeTime(lastSyncAt);
};

/**
 * Get time ago string with more granular options
 */
export function timeAgo(dateStr: string): string {
  return formatRelativeTime(dateStr, { verbose: true });
};

/**
 * Format date for display
 */
export function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  return formatDateTime(dateStr);
};

/**
 * Format timestamp as relative time (e.g., "Just now", "5m ago", "2h ago", "3d ago")
 * Falls back to date string for timestamps older than 7 days
 */
export function formatRelativeTimestamp(timestamp: string): string {
  return formatRelativeTime(timestamp, { justNowLabel: "Just now", capDays: 7 });
};
