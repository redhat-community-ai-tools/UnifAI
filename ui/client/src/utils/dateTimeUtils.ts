/**
 * Date/time helpers – local-time display & timezone-safe ISO parsing.
 *
 * All absolute date/time display in this file renders in a single fixed
 * locale/style (day-month-year order, 24-hour clock, no AM/PM) so timestamps
 * look the same everywhere regardless of the viewer's browser locale.
 */

const CANONICAL_LOCALE = "en-GB";

/**
 * Parse an ISO-8601 timestamp string ensuring it is treated as **UTC** even if
 * the server omits the trailing "Z" or "+00:00" offset.
 *
 * Without this fix `new Date("2024-07-22T09:00:00")` is interpreted as *local*
 * time, making every displayed time look like "same time" and throwing off the
 * relative "X ago" calculations by the user's UTC offset.
 */
export function parseUtcDate(iso: string): Date {
  if (
    !iso.endsWith("Z") &&
    !iso.includes("+") &&
    !/T\d{2}:\d{2}(:\d{2})?-/.test(iso)
  ) {
    return new Date(iso + "Z");
  }
  return new Date(iso);
}

/**
 * Convert a cron hour:minute expressed in `scheduleTz` (IANA, e.g. "UTC",
 * "America/New_York") to a `"HH:MM"` string in the user's **local** timezone.
 */
export function cronTimeToLocal(
  cronHour: number,
  cronMin: number,
  scheduleTz: string = "UTC",
): string {
  // 1. Create a probe date at cronHour:cronMin UTC
  const probe = new Date();
  probe.setUTCHours(cronHour, cronMin, 0, 0);

  // 2. See what that same instant looks like in scheduleTz
  const inTz = new Intl.DateTimeFormat("en-GB", {
    timeZone: scheduleTz,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(probe);

  const [tzH, tzM] = inTz.split(":").map(Number);

  // 3. Derive offset of scheduleTz from UTC (minutes)
  let offsetMin = (tzH * 60 + tzM) - (cronHour * 60 + cronMin);
  if (offsetMin > 720) offsetMin -= 1440;
  if (offsetMin < -720) offsetMin += 1440;

  // 4. The real UTC instant when it's cronHour:cronMin in scheduleTz
  const actualUtc = new Date(probe.getTime() - offsetMin * 60_000);

  // 5. Display in the user's local timezone
  return actualUtc.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/**
 * Format an ISO timestamp as an absolute date + time string, e.g. "27 Jul 2026, 14:32".
 */
export function formatDateTime(iso: string): string {
  const d = parseUtcDate(iso);
  return d.toLocaleString(CANONICAL_LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/**
 * Format an ISO timestamp as an absolute date only (no time), e.g. "27 Jul 2026".
 */
export function formatDateOnly(iso: string): string {
  const d = parseUtcDate(iso);
  return d.toLocaleDateString(CANONICAL_LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * Format an ISO timestamp for compact display: just the time if it's today,
 * otherwise a short date + time, e.g. "14:32" or "27 Jul, 14:32".
 */
export function formatTime(iso: string): string {
  const d = parseUtcDate(iso);
  const now = new Date();
  const isToday =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();

  const timePart = d.toLocaleTimeString(CANONICAL_LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  if (isToday) return timePart;

  const datePart = d.toLocaleDateString(CANONICAL_LOCALE, { month: "short", day: "numeric" });
  return `${datePart}, ${timePart}`;
}

export interface RelativeTimeOptions {
  /** Use verbose plural wording, e.g. "5 minutes ago" instead of "5m ago". */
  verbose?: boolean;
  /** Label shown for sub-minute timestamps. Defaults to "just now". */
  justNowLabel?: string;
  /** After this many days, fall back to an absolute date (`formatDateOnly`) instead of "Xd ago". */
  capDays?: number;
}

/**
 * Format an ISO timestamp as a relative "time ago" string, e.g. "5m ago",
 * "2h ago", "3d ago". See `RelativeTimeOptions` for verbosity/cap tweaks.
 */
export function formatRelativeTime(iso: string, options: RelativeTimeOptions = {}): string {
  const { verbose = false, justNowLabel = "just now", capDays } = options;
  const diffMs = Date.now() - parseUtcDate(iso).getTime();
  const mins = Math.floor(diffMs / 60_000);

  if (mins < 1) return justNowLabel;

  if (mins < 60) {
    return verbose ? `${mins} minute${mins > 1 ? "s" : ""} ago` : `${mins}m ago`;
  }

  const hours = Math.floor(mins / 60);
  if (hours < 24) {
    return verbose ? `${hours} hour${hours > 1 ? "s" : ""} ago` : `${hours}h ago`;
  }

  const days = Math.floor(hours / 24);
  if (capDays !== undefined && days >= capDays) {
    return formatDateOnly(iso);
  }
  return verbose ? `${days} day${days > 1 ? "s" : ""} ago` : `${days}d ago`;
}

/**
 * Parse a simple ISO-8601 duration string used for scheduling intervals,
 * e.g. `"PT15M"` -> `{ value: 15, unit: "minute" }`.
 */
export function parseISODuration(iso: string): { value: number; unit: "minute" | "hour" | "day" } | null {
  const match = iso.match(/^PT(\d+)([MH])$/);
  if (!match) return null;
  const value = parseInt(match[1], 10);
  const u = match[2];
  if (u === "M") return { value, unit: "minute" };
  if (u === "H") {
    if (value % 24 === 0 && value > 24) return { value: value / 24, unit: "day" };
    return { value, unit: "hour" };
  }
  return null;
}
