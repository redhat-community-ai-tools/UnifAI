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
  const lastSync = new Date(lastSyncAt);
  const now = new Date();
  const diffMinutes = Math.floor((now.getTime() - lastSync.getTime()) / 60000);

  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
};

/**
 * Get time ago string with more granular options
 */
export function timeAgo(dateStr: string): string {
  const now = new Date();
  const past = new Date(dateStr);
  const minutes = Math.floor((+now - +past) / 60000);

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes > 1 ? "s" : ""} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days > 1 ? "s" : ""} ago`;
};

/**
 * Format date for display
 */
export function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });
};